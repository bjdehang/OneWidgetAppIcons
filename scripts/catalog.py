#!/usr/bin/env python3
"""Refresh and validate the App Store based icon catalog."""

import argparse
import csv
import json
import re
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
COUNTRIES = "cn us jp kr in gb de fr br mx ca au id tr sa ae es it nl se pl sg th vn tw hk my ph za ng eg".split()
TARGET = 1000
ID_PATTERN = re.compile(r"app-[0-9]+\Z")
STYLE_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_url(country):
    return f"https://itunes.apple.com/{country}/rss/topfreeapplications/limit=100/json"


def fetch_chart(country):
    url = source_url(country)
    error = None
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "OneWidgetAppIcons-catalog/1.0"})
            with urlopen(request, timeout=30) as response:
                return json.load(response)["feed"]["entry"]
        except Exception as exc:
            error = exc
            time.sleep(attempt + 1)
    raise RuntimeError(f"Could not fetch {country}: {error}")


def load_chart(country, chart_dir):
    if chart_dir is None:
        return fetch_chart(country)
    return json.loads((chart_dir / f"ow-chart-{country}.json").read_text(encoding="utf-8"))


def normalize(country, entries):
    result = []
    for rank, entry in enumerate(entries, start=1):
        attributes = entry["id"]["attributes"]
        category = entry["category"]["attributes"]
        app_store_id = attributes["im:id"]
        bundle_id = attributes["im:bundleId"]
        if not app_store_id.isdecimal() or not bundle_id:
            raise ValueError(f"Invalid Apple identifiers in {country} rank {rank}")
        result.append({
            "rank": rank,
            "appStoreId": app_store_id,
            "bundleId": bundle_id,
            "name": entry["im:name"]["label"],
            "developer": entry["im:artist"]["label"],
            "genreId": category["im:id"],
            "genre": category["term"],
        })
    return result


def build(chart_dir, date):
    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    previous_path = ROOT / "metadata/apps.json"
    previous = {}
    if previous_path.exists():
        previous = {app["id"]: app for app in json.loads(previous_path.read_text(encoding="utf-8"))["apps"]}
    asset_path = ROOT / "metadata/assets.json"
    published_ids = set()
    if asset_path.exists():
        published_ids = {asset["appId"] for asset in json.loads(asset_path.read_text(encoding="utf-8"))["assets"]}
    charts = {}
    grouped = {}
    for country in COUNTRIES:
        entries = normalize(country, load_chart(country, chart_dir))
        charts[country] = {"source": source_url(country), "entries": entries}
        for entry in entries:
            grouped.setdefault(entry["appStoreId"], []).append((country, entry))
    if len(grouped) < TARGET:
        raise ValueError(f"Only {len(grouped)} unique apps; need {TARGET}")

    for app_store_id, placements in grouped.items():
        if len({entry["bundleId"] for _, entry in placements}) != 1:
            raise ValueError(f"Conflicting bundle IDs for {app_store_id}")

    mandatory = {
        entry["appStoreId"]
        for country, chart in charts.items()
        for entry in chart["entries"]
        if country in ("cn", "us") or entry["rank"] <= 20
    }
    manually_mapped_ids = {
        app_id for app_id, app in previous.items()
        if app["platforms"]["android"]["packageName"] is not None
        or app["platforms"]["harmony"]["bundleName"] is not None
    }
    pinned_ids = published_ids | manually_mapped_ids
    missing_pinned = pinned_ids - {f"app-{app_store_id}" for app_store_id in grouped}
    if missing_pinned:
        raise ValueError(f"Mapped or published apps absent from current charts: {sorted(missing_pinned)[:10]}")
    mandatory.update(app_id.removeprefix("app-") for app_id in pinned_ids)
    if len(mandatory) > TARGET:
        raise ValueError(f"Mandatory regional coverage exceeds {TARGET} apps")

    def score(app_store_id):
        placements = grouped[app_store_id]
        return sum((2 if country in ("cn", "us") else 1) * (101 - entry["rank"]) / 100
                   for country, entry in placements)

    ordered = sorted(grouped, key=lambda app_store_id: (
        -score(app_store_id),
        -len(grouped[app_store_id]),
        min(entry["rank"] for _, entry in grouped[app_store_id]),
        int(app_store_id),
    ))
    selected = set(mandatory)
    for app_store_id in ordered:
        if len(selected) == TARGET:
            break
        selected.add(app_store_id)
    selected_order = [app_store_id for app_store_id in ordered if app_store_id in selected]

    apps = []
    for app_store_id in selected_order:
        placements = grouped[app_store_id]
        old = previous.get(f"app-{app_store_id}")
        preferred = next((entry for country, entry in placements if country == "cn"), None)
        preferred = preferred or next((entry for country, entry in placements if country == "us"), None)
        preferred = preferred or placements[0][1]
        apps.append({
            "id": f"app-{app_store_id}",
            "name": preferred["name"],
            "developer": preferred["developer"],
            "genre": {"id": preferred["genreId"], "name": preferred["genre"]},
            "platforms": {
                "apple": {
                    "appStoreId": app_store_id,
                    "bundleId": preferred["bundleId"],
                    "url": f"https://apps.apple.com/app/id{app_store_id}",
                },
                "android": old["platforms"]["android"] if old else {"packageName": None},
                "harmony": old["platforms"]["harmony"] if old else {"bundleName": None},
            },
            "charts": [{"country": country, "rank": entry["rank"]} for country, entry in placements],
        })

    snapshot = {
        "schemaVersion": 1,
        "capturedAt": captured_at,
        "chartType": "top-free-applications",
        "charts": charts,
    }
    catalog = {
        "schemaVersion": 1,
        "generatedAt": captured_at,
        "snapshot": f"data/app-store-snapshot-{date}.json",
        "selection": {
            "target": TARGET,
            "rule": "All CN and US top 100, all other regional top 20, then weighted cross-market chart score",
            "candidateCount": len(grouped),
            "marketCount": len(charts),
        },
        "apps": apps,
    }
    write_json(ROOT / f"data/app-store-snapshot-{date}.json", snapshot)
    write_json(ROOT / "metadata/apps.json", catalog)
    with (ROOT / "metadata/apps.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(("id", "name", "developer", "appleAppStoreId", "appleBundleId",
                         "androidPackageName", "harmonyBundleName", "marketCount"))
        for app in apps:
            platforms = app["platforms"]
            writer.writerow((app["id"], app["name"], app["developer"],
                             platforms["apple"]["appStoreId"], platforms["apple"]["bundleId"],
                             platforms["android"]["packageName"], platforms["harmony"]["bundleName"],
                             len(app["charts"])))
    print(f"Captured {sum(len(c['entries']) for c in charts.values())} placements, "
          f"{len(grouped)} unique apps, selected {len(apps)}")


def validate():
    catalog = json.loads((ROOT / "metadata/apps.json").read_text(encoding="utf-8"))
    styles = json.loads((ROOT / "metadata/styles.json").read_text(encoding="utf-8"))
    assets = json.loads((ROOT / "metadata/assets.json").read_text(encoding="utf-8"))
    snapshot = json.loads((ROOT / catalog["snapshot"]).read_text(encoding="utf-8"))
    apps = catalog["apps"]
    if len(apps) != TARGET or catalog["selection"]["target"] != TARGET:
        raise ValueError(f"Catalog must have exactly {TARGET} apps")
    with (ROOT / "metadata/apps.csv").open(encoding="utf-8", newline="") as file:
        csv_rows = list(csv.DictReader(file))
    if len(csv_rows) != TARGET or [row["id"] for row in csv_rows] != [app["id"] for app in apps]:
        raise ValueError("CSV application list differs from apps.json")
    if set(snapshot["charts"]) != set(COUNTRIES):
        raise ValueError("Snapshot storefronts do not match the supported countries")
    ids = set()
    apple_ids = set()
    for app in apps:
        app_id = app["id"]
        apple = app["platforms"]["apple"]
        if not ID_PATTERN.fullmatch(app_id) or app_id != f"app-{apple['appStoreId']}":
            raise ValueError(f"Invalid unified ID: {app_id}")
        if app_id in ids or apple["appStoreId"] in apple_ids or not apple["bundleId"]:
            raise ValueError(f"Duplicate or missing Apple identity: {app_id}")
        ids.add(app_id)
        apple_ids.add(apple["appStoreId"])
        if not app["charts"]:
            raise ValueError(f"No chart provenance: {app_id}")
        for position in app["charts"]:
            if position["country"] not in snapshot["charts"] or not 1 <= position["rank"] <= 100:
                raise ValueError(f"Invalid chart position: {app_id}")
            source_entry = snapshot["charts"][position["country"]]["entries"][position["rank"] - 1]
            if source_entry["appStoreId"] != apple["appStoreId"]:
                raise ValueError(f"Chart provenance mismatch: {app_id}")

    style_ids = set()
    for style in styles["styles"]:
        style_id = style["id"]
        if not STYLE_PATTERN.fullmatch(style_id) or style_id in style_ids:
            raise ValueError(f"Invalid style ID: {style_id}")
        style_ids.add(style_id)
        if not (ROOT / "styles" / style_id).is_dir():
            raise ValueError(f"Missing style directory: {style_id}")

    asset_paths = set()
    for asset in assets["assets"]:
        path = asset["path"]
        if path in asset_paths or asset["appId"] not in ids or asset["styleId"] not in style_ids:
            raise ValueError(f"Invalid asset record: {path}")
        if path != f"styles/{asset['styleId']}/{asset['appId']}.png":
            raise ValueError(f"Asset path does not follow the unified ID: {path}")
        if not asset.get("license") or not asset.get("source") or not asset.get("prompt"):
            raise ValueError(f"Missing asset provenance: {path}")
        if asset["prompt"] != f"prompts/{asset['styleId']}/{asset['appId']}.md":
            raise ValueError(f"Prompt path does not follow the unified ID: {path}")
        if not (ROOT / path).is_file() or not (ROOT / asset["prompt"]).is_file():
            raise ValueError(f"Missing asset or prompt file: {path}")
        asset_paths.add(path)

    for image in (ROOT / "styles").glob("*/*.png"):
        relative = image.relative_to(ROOT).as_posix()
        if relative not in asset_paths:
            raise ValueError(f"Unregistered image: {relative}")
        with image.open("rb") as file:
            header = file.read(24)
        if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"Invalid PNG: {relative}")
        if struct.unpack(">II", header[16:24]) != (1024, 1024):
            raise ValueError(f"PNG must be 1024x1024: {relative}")
    print(f"Validated {len(apps)} apps, {len(style_ids)} styles, {len(asset_paths)} assets")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    refresh = subparsers.add_parser("refresh", help="Fetch and rebuild the App Store catalog")
    refresh.add_argument("--chart-dir", type=Path, help="Read saved ow-chart-<country>.json entries")
    refresh.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    subparsers.add_parser("validate", help="Check catalog and asset invariants")
    args = parser.parse_args()
    if args.command == "refresh":
        build(args.chart_dir, args.date)
    else:
        validate()


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
