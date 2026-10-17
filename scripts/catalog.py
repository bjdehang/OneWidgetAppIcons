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

from unified_id import legacy_id, unified_id_from_bundle


ROOT = Path(__file__).resolve().parents[1]
COUNTRIES = (
    "cn us jp kr in gb de fr br mx ca au id tr sa ae es it nl se pl sg th vn tw hk my ph za ng eg "
    "ar cl co pe uy pt be ch at dk no fi ie nz il pk lk np ke gh ma tn dz ua ro cz hu gr"
).split()
TARGET = 2000
AUTHOR_ID = "1250290964"
STYLE_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
CSV_HEADER = (
    "id", "legacyId", "name", "developer", "appleAppStoreId", "appleBundleId",
    "androidPackageName", "harmonyBundleName", "huaweiAppGalleryId",
    "marketCount", "authorApp", "officialIconPath", "iconWidth", "iconHeight",
    "iconFormat", "iconSha256",
)


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


def load_author_apps(author_file):
    if author_file is not None:
        return json.loads(author_file.read_text(encoding="utf-8"))
    apps = {}
    sources = {}
    for country in ("us", "cn"):
        url = f"https://itunes.apple.com/lookup?id={AUTHOR_ID}&entity=software&limit=200&country={country}"
        request = Request(url, headers={"User-Agent": "OneWidgetAppIcons-catalog/1.0"})
        with urlopen(request, timeout=30) as response:
            results = json.load(response)["results"]
        sources[country] = url
        for result in results:
            if result.get("wrapperType") != "software" or str(result.get("artistId")) != AUTHOR_ID:
                continue
            app_store_id = str(result["trackId"])
            if app_store_id not in apps:
                apps[app_store_id] = {
                    "trackId": result["trackId"],
                    "trackName": result["trackName"],
                    "bundleId": result["bundleId"],
                    "artistId": result["artistId"],
                    "artistName": result["artistName"],
                    "kind": result["kind"],
                    "primaryGenreName": result["primaryGenreName"],
                    "primaryGenreId": result["primaryGenreId"],
                    "trackViewUrl": result["trackViewUrl"],
                    "regions": [],
                }
            if country not in apps[app_store_id]["regions"]:
                apps[app_store_id]["regions"].append(country)
    return {
        "artistId": AUTHOR_ID,
        "artistName": "Chengdu Reinvent Technology Co., Ltd.",
        "sources": sources,
        "apps": sorted(apps.values(), key=lambda app: (app["trackId"] != 1527355884, app["trackName"])),
    }


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


def store_id_of(app):
    return str(app["platforms"]["apple"]["appStoreId"])


def has_manual_platform_id(app):
    platforms = app["platforms"]
    huawei = (platforms.get("huawei") or {}).get("appGalleryId")
    return (
        platforms["android"]["packageName"] is not None
        or platforms["harmony"]["bundleName"] is not None
        or huawei is not None
    )


def carried_platform(old, override, platform, empty):
    if platform in override:
        return override[platform]
    if old and platform in old["platforms"]:
        return old["platforms"][platform]
    return empty


def build(chart_dir, author_file, date):
    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    previous_path = ROOT / "metadata/apps.json"
    previous = {}
    if previous_path.exists():
        previous = {app["id"]: app for app in json.loads(previous_path.read_text(encoding="utf-8"))["apps"]}
    asset_path = ROOT / "metadata/assets.json"
    published_assets = []
    if asset_path.exists():
        published_assets = json.loads(asset_path.read_text(encoding="utf-8"))["assets"]
    charts = {}
    grouped = {}
    for country in COUNTRIES:
        entries = normalize(country, load_chart(country, chart_dir))
        charts[country] = {"source": source_url(country), "entries": entries}
        for entry in entries:
            grouped.setdefault(entry["appStoreId"], []).append((country, entry))
    author_snapshot = load_author_apps(author_file)
    if str(author_snapshot["artistId"]) != AUTHOR_ID:
        raise ValueError("Author snapshot has the wrong Apple artist ID")
    author_apps = {str(app["trackId"]): app for app in author_snapshot["apps"]}
    if "1527355884" not in author_apps or any(str(app["artistId"]) != AUTHOR_ID for app in author_apps.values()):
        raise ValueError("Author snapshot is missing OneWidget or has another developer")
    if len(set(grouped) | set(author_apps)) < TARGET:
        raise ValueError(f"Only {len(set(grouped) | set(author_apps))} unique apps; need {TARGET}")

    for app_store_id, placements in grouped.items():
        if len({entry["bundleId"] for _, entry in placements}) != 1:
            raise ValueError(f"Conflicting bundle IDs for {app_store_id}")

    mandatory = {
        entry["appStoreId"]
        for country, chart in charts.items()
        for entry in chart["entries"]
        if country in ("cn", "us") or entry["rank"] <= 20
    }
    published_store_ids = set()
    for asset in published_assets:
        match = previous.get(asset["appId"])
        if match is None:
            match = next((app for app in previous.values()
                          if app.get("legacyId") == asset["appId"] or app["id"] == asset["appId"]), None)
        if match is None:
            raise ValueError(f"Published asset has unknown app id {asset['appId']}")
        published_store_ids.add(store_id_of(match))
    manually_mapped_store_ids = {
        store_id_of(app) for app in previous.values() if has_manual_platform_id(app)
    }
    pinned_store_ids = published_store_ids | manually_mapped_store_ids
    available = set(grouped) | set(author_apps)
    missing_pinned = pinned_store_ids - available
    if missing_pinned:
        raise ValueError(f"Mapped or published apps absent from current charts: {sorted(missing_pinned)[:10]}")
    mandatory.update(pinned_store_ids)
    mandatory.update(author_apps)
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
    author_order = [str(app["trackId"]) for app in author_snapshot["apps"]]
    selected_order = author_order + [app_store_id for app_store_id in ordered
                                     if app_store_id in selected and app_store_id not in author_apps]

    overrides = json.loads((ROOT / "metadata/platform-overrides.json").read_text(encoding="utf-8"))["apps"]

    apps = []
    for app_store_id in selected_order:
        placements = grouped.get(app_store_id, [])
        preferred = next((entry for country, entry in placements if country == "cn"), None)
        preferred = preferred or next((entry for country, entry in placements if country == "us"), None)
        preferred = preferred or (placements[0][1] if placements else None)
        author = author_apps.get(app_store_id)
        name = preferred["name"] if preferred else author["trackName"]
        developer = preferred["developer"] if preferred else author["artistName"]
        genre_id = preferred["genreId"] if preferred else str(author["primaryGenreId"])
        genre_name = preferred["genre"] if preferred else author["primaryGenreName"]
        bundle_id = preferred["bundleId"] if preferred else author["bundleId"]
        app_id = unified_id_from_bundle(bundle_id)
        alias = legacy_id(app_store_id)
        old = previous.get(app_id) or previous.get(alias)
        platform_override = overrides.get(app_id) or overrides.get(alias) or {}
        apps.append({
            "id": app_id,
            "legacyId": alias,
            "name": name,
            "developer": developer,
            "genre": {"id": genre_id, "name": genre_name},
            "platforms": {
                "apple": {
                    "appStoreId": app_store_id,
                    "bundleId": bundle_id,
                    "url": f"https://apps.apple.com/app/id{app_store_id}",
                },
                "android": carried_platform(
                    old, platform_override, "android", {"packageName": None}),
                "harmony": carried_platform(
                    old, platform_override, "harmony", {"bundleName": None}),
                "huawei": carried_platform(
                    old, platform_override, "huawei", {"appGalleryId": None}),
            },
            "charts": [{"country": country, "rank": entry["rank"]} for country, entry in placements],
            "authorApp": author is not None,
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
        "authorSnapshot": f"data/author-apps-{date}.json",
        "selection": {
            "target": TARGET,
            "rule": "All author apps, CN and US top 100, other regional top 20, then weighted cross-market chart score",
            "candidateCount": len(set(grouped) | set(author_apps)),
            "marketCount": len(charts),
            "authorAppCount": len(author_apps),
        },
        "apps": apps,
    }
    write_json(ROOT / f"data/app-store-snapshot-{date}.json", snapshot)
    author_snapshot["capturedAt"] = captured_at
    write_json(ROOT / f"data/author-apps-{date}.json", author_snapshot)
    write_json(ROOT / "metadata/apps.json", catalog)
    from official_icons import load_official_icons, write_apps_csv
    write_apps_csv(ROOT, apps, {icon["id"]: icon for icon in load_official_icons(ROOT)})
    print(f"Captured {sum(len(c['entries']) for c in charts.values())} placements, "
          f"{len(set(grouped) | set(author_apps))} unique apps, selected {len(apps)}")


def validate():
    catalog = json.loads((ROOT / "metadata/apps.json").read_text(encoding="utf-8"))
    styles = json.loads((ROOT / "metadata/styles.json").read_text(encoding="utf-8"))
    assets = json.loads((ROOT / "metadata/assets.json").read_text(encoding="utf-8"))
    snapshot = json.loads((ROOT / catalog["snapshot"]).read_text(encoding="utf-8"))
    author_snapshot = json.loads((ROOT / catalog["authorSnapshot"]).read_text(encoding="utf-8"))
    author_apps = {str(app["trackId"]): app for app in author_snapshot["apps"]}
    overrides = json.loads((ROOT / "metadata/platform-overrides.json").read_text(encoding="utf-8"))["apps"]
    apps = catalog["apps"]
    if len(apps) != TARGET or catalog["selection"]["target"] != TARGET:
        raise ValueError(f"Catalog must have exactly {TARGET} apps")
    with (ROOT / "metadata/apps.csv").open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if tuple(reader.fieldnames or ()) != CSV_HEADER:
            raise ValueError(f"CSV header mismatch: {reader.fieldnames}")
        csv_rows = list(reader)
    if len(csv_rows) != TARGET or [row["id"] for row in csv_rows] != [app["id"] for app in apps]:
        raise ValueError("CSV application list differs from apps.json")
    if set(snapshot["charts"]) != set(COUNTRIES):
        raise ValueError("Snapshot storefronts do not match the supported countries")
    if str(author_snapshot["artistId"]) != AUTHOR_ID or len(author_apps) != catalog["selection"]["authorAppCount"]:
        raise ValueError("Author app snapshot mismatch")
    ids = set()
    legacy_ids = set()
    apple_ids = set()
    bundle_ids = set()
    platform_ids = {"android": {}, "harmony": {}, "huawei": {}}
    platform_fields = {
        "android": "packageName",
        "harmony": "bundleName",
        "huawei": "appGalleryId",
    }
    for app, row in zip(apps, csv_rows):
        app_id = app["id"]
        apple = app["platforms"]["apple"]
        if app_id != unified_id_from_bundle(apple["bundleId"]) or app.get("legacyId") != legacy_id(apple["appStoreId"]):
            raise ValueError(f"Invalid unified ID: {app_id}")
        if app_id in ids or app["legacyId"] in legacy_ids or apple["appStoreId"] in apple_ids or not apple["bundleId"]:
            raise ValueError(f"Duplicate or missing Apple identity: {app_id}")
        if apple["bundleId"] in bundle_ids:
            raise ValueError(f"Duplicate bundle ID: {apple['bundleId']}")
        ids.add(app_id)
        legacy_ids.add(app["legacyId"])
        apple_ids.add(apple["appStoreId"])
        bundle_ids.add(apple["bundleId"])
        huawei = app["platforms"].get("huawei")
        if not huawei or set(huawei) != {"appGalleryId"}:
            raise ValueError(f"Missing Huawei field: {app_id}")
        for platform, field in platform_fields.items():
            value = app["platforms"][platform][field]
            if value is None:
                continue
            if value in platform_ids[platform]:
                raise ValueError(f"Duplicate {platform} mapping: {value}")
            platform_ids[platform][value] = app_id
            recorded = (overrides.get(app_id) or {}).get(platform)
            if not recorded or recorded.get(field) != value:
                raise ValueError(f"Unverified {platform} id on {app_id}: {value}")
        author = author_apps.get(apple["appStoreId"])
        if app["authorApp"] != (author is not None):
            raise ValueError(f"Author app flag mismatch: {app_id}")
        if author and (str(author["artistId"]) != AUTHOR_ID or author["bundleId"] != apple["bundleId"]):
            raise ValueError(f"Author identity mismatch: {app_id}")
        if not app["charts"] and not author:
            raise ValueError(f"No chart or author provenance: {app_id}")
        for position in app["charts"]:
            if position["country"] not in snapshot["charts"] or not 1 <= position["rank"] <= 100:
                raise ValueError(f"Invalid chart position: {app_id}")
            source_entry = snapshot["charts"][position["country"]]["entries"][position["rank"] - 1]
            if source_entry["appStoreId"] != apple["appStoreId"]:
                raise ValueError(f"Chart provenance mismatch: {app_id}")
        if app["legacyId"] in overrides:
            raise ValueError(f"Platform override is still keyed by the legacy ID: {app['legacyId']}")
        if app_id in overrides:
            for platform, identity in overrides[app_id].items():
                if platform == "legacyId":
                    if identity != app["legacyId"]:
                        raise ValueError(f"Platform override legacy ID mismatch: {app_id}")
                    continue
                if app["platforms"].get(platform) != identity:
                    raise ValueError(f"Platform override mismatch: {app_id}")
        if row["legacyId"] != app["legacyId"] or row["name"] != app["name"] or row["developer"] != app["developer"]:
            raise ValueError(f"CSV identity mismatch: {app_id}")
        if row["appleAppStoreId"] != apple["appStoreId"] or row["appleBundleId"] != apple["bundleId"]:
            raise ValueError(f"CSV Apple identity mismatch: {app_id}")
        if row["marketCount"] != str(len(app["charts"])) or row["authorApp"] != str(app["authorApp"]):
            raise ValueError(f"CSV chart summary mismatch: {app_id}")
        for platform, field, column in (
            ("android", "packageName", "androidPackageName"),
            ("harmony", "bundleName", "harmonyBundleName"),
            ("huawei", "appGalleryId", "huaweiAppGalleryId"),
        ):
            value = app["platforms"][platform][field]
            if row[column] != ("" if value is None else str(value)):
                raise ValueError(f"CSV {platform} mismatch: {app_id}")
    if not {f"app-{app_store_id}" for app_store_id in author_apps}.issubset(legacy_ids):
        raise ValueError("Not all author apps are included")

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
    refresh.add_argument("--author-file", type=Path, help="Read a saved Apple artist lookup snapshot")
    refresh.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    subparsers.add_parser("validate", help="Check catalog and asset invariants")
    args = parser.parse_args()
    if args.command == "refresh":
        build(args.chart_dir, args.author_file, args.date)
    else:
        validate()


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
