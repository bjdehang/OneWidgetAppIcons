#!/usr/bin/env python3
"""Validate the icon catalog and rebuild the China and US chart lists."""

import argparse
import csv
import json
import re
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

from mapping import ORIGINAL_STYLE
from official_icons import CSV_HEADER
from store_charts import APPS_DEPTH, ENTRY_FIELDS, GAMES_DEPTH, capture_lists
from unified_id import legacy_id, unified_id_from_bundle


ROOT = Path(__file__).resolve().parents[1]
STYLE_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
STYLE_EXTENSION = re.compile(r"\.[a-z0-9]+\Z")
STYLE_DIMENSIONS = re.compile(r"[0-9]+x[0-9]+\Z")
STYLE_MEDIA = {"raster", "vector"}
STYLE_TRANSPARENCY = {"as-delivered", "opaque", "alpha"}
STYLE_MASK = {"none", "unspecified"}
STYLE_STATUS = {"planned", "published"}
ALPHA_EXTENSIONS = {".png", ".webp", ".svg"}
STYLE_CSV_HEADER = (
    "id", "name", "status", "extensions", "definition", "media", "transparency",
    "dimensions", "mask", "summary",
)
SHARED_FIELDS = ("id", "legacyId", "name", "developer", "kind", "authorApp")


def check_style_record(style):
    """Check one style-table row. The row records suffix, definition, and traits."""
    style_id = style.get("id")
    if not isinstance(style_id, str) or not STYLE_PATTERN.fullmatch(style_id):
        raise ValueError(f"Invalid style ID: {style_id}")
    if style.get("status") not in STYLE_STATUS:
        raise ValueError(f"Invalid style status: {style_id}")
    if not style.get("name") or not style.get("definition"):
        raise ValueError(f"Style {style_id} is missing a name or definition")
    extensions = style.get("extensions")
    if not isinstance(extensions, list) or not extensions:
        raise ValueError(f"Style {style_id} needs at least one file suffix")
    if len(set(extensions)) != len(extensions):
        raise ValueError(f"Style {style_id} repeats a file suffix")
    for extension in extensions:
        if not isinstance(extension, str) or not STYLE_EXTENSION.fullmatch(extension):
            raise ValueError(f"Invalid file suffix for {style_id}: {extension}")
    traits = style.get("characteristics")
    if not isinstance(traits, dict):
        raise ValueError(f"Style {style_id} is missing characteristics")
    media = traits.get("media")
    transparency = traits.get("transparency")
    dimensions = traits.get("dimensions")
    mask = traits.get("mask")
    if media not in STYLE_MEDIA:
        raise ValueError(f"Invalid media for {style_id}: {media}")
    if transparency not in STYLE_TRANSPARENCY:
        raise ValueError(f"Invalid transparency for {style_id}: {transparency}")
    if mask not in STYLE_MASK:
        raise ValueError(f"Invalid mask for {style_id}: {mask}")
    if dimensions not in {"source", "scalable"} and not (isinstance(dimensions, str) and STYLE_DIMENSIONS.fullmatch(dimensions)):
        raise ValueError(f"Invalid dimensions for {style_id}: {dimensions}")
    if not traits.get("summary"):
        raise ValueError(f"Style {style_id} is missing a characteristics summary")
    if media == "vector" and extensions != [".svg"]:
        raise ValueError(f"Vector style {style_id} must use the .svg suffix")
    if media == "raster" and ".svg" in extensions:
        raise ValueError(f"Raster style {style_id} cannot use the .svg suffix")
    if transparency == "alpha" and not set(extensions) & ALPHA_EXTENSIONS:
        raise ValueError(f"Style {style_id} needs a suffix that can store a transparent layer")
    if media == "vector" and dimensions != "scalable":
        raise ValueError(f"Vector style {style_id} uses scalable dimensions")
    return style_id


def style_csv_row(style):
    traits = style["characteristics"]
    return {
        "id": style["id"],
        "name": style["name"],
        "status": style["status"],
        "extensions": ";".join(style["extensions"]),
        "definition": style["definition"],
        "media": traits["media"],
        "transparency": traits["transparency"],
        "dimensions": traits["dimensions"],
        "mask": traits["mask"],
        "summary": traits["summary"],
    }


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _check_entry(app, overrides, expected_ranks):
    if tuple(app) != ENTRY_FIELDS:
        raise ValueError(f"List fields differ: {app.get('id')}")
    apple = app["platforms"]["apple"]
    app_id = app["id"]
    if app_id != unified_id_from_bundle(apple["bundleId"]) or app["legacyId"] != legacy_id(apple["appStoreId"]):
        raise ValueError(f"Invalid unified ID: {app_id}")
    if app["kind"] not in {"game", "application"}:
        raise ValueError(f"Invalid kind: {app_id}")
    if not isinstance(app["authorApp"], bool):
        raise ValueError(f"authorApp must be boolean: {app_id}")
    huawei = app["platforms"].get("huawei")
    if not huawei or set(huawei) != {"appGalleryId"}:
        raise ValueError(f"Missing Huawei field: {app_id}")
    for platform, field in (
        ("android", "packageName"),
        ("harmony", "bundleName"),
        ("huawei", "appGalleryId"),
    ):
        value = app["platforms"][platform][field]
        if value is None:
            continue
        recorded = ((overrides.get(app_id) or {}).get(platform) or {}).get(field)
        if recorded != value:
            raise ValueError(f"Unverified {platform} id on {app_id}: {value}")
    ranks = {"cn": app["cnRank"], "us": app["usRank"]}
    if all(rank is None for rank in ranks.values()):
        raise ValueError(f"Missing both regional ranks: {app_id}")
    charts = []
    for country in ("cn", "us"):
        rank = ranks[country]
        if rank is None:
            continue
        if not isinstance(rank, int) or rank < 1:
            raise ValueError(f"Invalid {country} rank: {app_id}")
        charts.append({"country": country, "rank": rank})
        expected = expected_ranks[country].get(apple["appStoreId"])
        if expected != rank:
            raise ValueError(f"Chart provenance mismatch: {app_id} {country}")
    if app["charts"] != charts:
        raise ValueError(f"charts does not match cnRank and usRank: {app_id}")


def _check_list(document, snapshot, list_name, requested_depth, overrides):
    if document.get("schemaVersion") != 2 or document.get("list") != list_name:
        raise ValueError(f"{list_name} list must use schemaVersion 2")
    chart = document["chart"]
    if chart.get("requestedDepth") != requested_depth or chart.get("countries") != ["cn", "us"]:
        raise ValueError(f"Unexpected chart request for {list_name}")
    if chart.get("genreId") != snapshot["charts"][list_name]["genreId"]:
        raise ValueError(f"Genre mismatch for {list_name}")
    apps = document["apps"]
    if document["selection"]["count"] != len(apps):
        raise ValueError(f"{list_name} count does not match the entries")
    expected_ranks = {}
    seen_ids = set()
    seen_store = set()
    seen_bundle = set()
    for country in ("cn", "us"):
        ids = snapshot["charts"][list_name][country]["ids"]
        available = len(ids)
        used = chart["usedDepth"][country]
        if chart["availableDepth"][country] != available or used != min(requested_depth, available):
            raise ValueError(f"{list_name} {country} depth does not match the snapshot")
        expected_ranks[country] = {store_id: rank for rank, store_id in enumerate(ids[:used], start=1)}
    for app in apps:
        _check_entry(app, overrides, expected_ranks)
        apple = app["platforms"]["apple"]
        if app["id"] in seen_ids or apple["appStoreId"] in seen_store or apple["bundleId"] in seen_bundle:
            raise ValueError(f"Duplicate list identity: {app['id']}")
        seen_ids.add(app["id"])
        seen_store.add(apple["appStoreId"])
        seen_bundle.add(apple["bundleId"])
    for country in ("cn", "us"):
        listed = {
            app["platforms"]["apple"]["appStoreId"]
            for app in apps
            if app["cnRank" if country == "cn" else "usRank"] is not None
        }
        if listed != set(expected_ranks[country]):
            raise ValueError(f"{list_name} {country} ranks do not cover the snapshot")
    return {app["id"]: app for app in apps}


def _check_csv(path, apps):
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CSV_HEADER:
            raise ValueError(f"CSV header mismatch: {path.name}")
        rows = list(reader)
    if [row["id"] for row in rows] != [app["id"] for app in apps]:
        raise ValueError(f"CSV list differs from {path.name}")
    for row, app in zip(rows, apps):
        apple = app["platforms"]["apple"]
        if row["legacyId"] != app["legacyId"] or row["name"] != app["name"] or row["developer"] != app["developer"]:
            raise ValueError(f"CSV identity mismatch: {app['id']}")
        if row["kind"] != app["kind"] or row["appleAppStoreId"] != apple["appStoreId"]:
            raise ValueError(f"CSV kind or Apple ID mismatch: {app['id']}")
        if row["appleBundleId"] != apple["bundleId"] or row["marketCount"] != str(len(app["charts"])):
            raise ValueError(f"CSV bundle or market count mismatch: {app['id']}")
        if row["authorApp"] != str(app["authorApp"]):
            raise ValueError(f"CSV author flag mismatch: {app['id']}")
        if row["cnRank"] != ("" if app["cnRank"] is None else str(app["cnRank"])):
            raise ValueError(f"CSV China rank mismatch: {app['id']}")
        if row["usRank"] != ("" if app["usRank"] is None else str(app["usRank"])):
            raise ValueError(f"CSV US rank mismatch: {app['id']}")
        for platform, field, column in (
            ("android", "packageName", "androidPackageName"),
            ("harmony", "bundleName", "harmonyBundleName"),
            ("huawei", "appGalleryId", "huaweiAppGalleryId"),
        ):
            value = app["platforms"][platform][field]
            if row[column] != ("" if value is None else str(value)):
                raise ValueError(f"CSV {platform} mismatch: {app['id']}")


def validate():
    apps_doc = _load(ROOT / "metadata/apps.json")
    games_doc = _load(ROOT / "metadata/games.json")
    if apps_doc.get("snapshot") != games_doc.get("snapshot"):
        raise ValueError("Apps and games lists point at different chart snapshots")
    snapshot = _load(ROOT / apps_doc["snapshot"])
    overrides = _load(ROOT / "metadata/platform-overrides.json")["apps"]
    styles = _load(ROOT / "metadata/styles.json")
    assets = _load(ROOT / "metadata/assets.json")
    apps_by_id = _check_list(apps_doc, snapshot, "apps", APPS_DEPTH, overrides)
    games_by_id = _check_list(games_doc, snapshot, "games", GAMES_DEPTH, overrides)
    for app_id, game in games_by_id.items():
        app = apps_by_id.get(app_id)
        if app is None:
            continue
        for field in SHARED_FIELDS:
            if app[field] != game[field]:
                raise ValueError(f"Apps and games disagree on {field} for {app_id}")
        if app["platforms"] != game["platforms"] or app["genre"] != game["genre"]:
            raise ValueError(f"Apps and games disagree on identity for {app_id}")
    _check_csv(ROOT / "metadata/apps.csv", apps_doc["apps"])
    _check_csv(ROOT / "metadata/games.csv", games_doc["apps"])
    if tuple(CSV_HEADER) != tuple(_csv_header(ROOT / "metadata/games.csv")):
        raise ValueError("Apps and games CSV headers differ")
    preview = (ROOT / "preview.html").read_text(encoding="utf-8")
    if 'id="show-apps"' not in preview or 'id="show-games"' not in preview:
        raise ValueError("Preview page is missing the apps and games switch")
    for style in styles.get("styles", []):
        if f'id="style-{style["id"]}"' not in preview:
            raise ValueError(f"Preview page is missing the {style['id']} style switch")

    if styles.get("schemaVersion") != 2:
        raise ValueError("Style table must use schemaVersion 2")
    with (ROOT / "metadata/styles.csv").open(encoding="utf-8", newline="") as file:
        style_reader = csv.DictReader(file)
        if tuple(style_reader.fieldnames or ()) != STYLE_CSV_HEADER:
            raise ValueError(f"Style CSV header mismatch: {style_reader.fieldnames}")
        style_rows = list(style_reader)
    style_ids = set()
    styles_by_id = {}
    for style in styles["styles"]:
        style_id = check_style_record(style)
        if style_id in style_ids:
            raise ValueError(f"Duplicate style ID: {style_id}")
        style_ids.add(style_id)
        styles_by_id[style_id] = style
        if not (ROOT / "styles" / style_id).is_dir():
            raise ValueError(f"Missing style directory: {style_id}")
        allowed = set(style["extensions"])
        for image in (ROOT / "styles" / style_id).iterdir():
            if not image.is_file() or image.name.startswith("."):
                continue
            if image.suffix.lower() not in allowed:
                raise ValueError(
                    f"File suffix {image.suffix} is not registered for style {style_id}: {image.name}"
                )
    if [row["id"] for row in style_rows] != [style["id"] for style in styles["styles"]]:
        raise ValueError("styles.csv is not the same style sequence as styles.json")
    for row, style in zip(style_rows, styles["styles"]):
        expected = style_csv_row(style)
        for column, value in expected.items():
            if row[column] != value:
                raise ValueError(f"Style CSV field {column} mismatch for {style['id']}")

    ids = set(apps_by_id) | set(games_by_id)
    asset_paths = set()
    for asset in assets["assets"]:
        path = asset["path"]
        style = styles_by_id.get(asset["styleId"])
        if path in asset_paths or asset["appId"] not in ids or style is None:
            raise ValueError(f"Invalid asset record: {path}")
        if style["id"] == ORIGINAL_STYLE:
            raise ValueError(f"Original icons are not generated assets: {path}")
        if len(style["extensions"]) != 1:
            raise ValueError(f"Generated style {style['id']} must declare one file suffix")
        if path != f"styles/{style['id']}/{asset['appId']}{style['extensions'][0]}":
            raise ValueError(f"Asset path does not follow the style table: {path}")
        if not asset.get("license") or not asset.get("source") or not asset.get("prompt"):
            raise ValueError(f"Missing asset provenance: {path}")
        if asset["prompt"] != f"prompts/{asset['styleId']}/{asset['appId']}.md":
            raise ValueError(f"Prompt path does not follow the unified ID: {path}")
        if not (ROOT / path).is_file() or not (ROOT / asset["prompt"]).is_file():
            raise ValueError(f"Missing asset or prompt file: {path}")
        asset_paths.add(path)

    for style in styles["styles"]:
        if style["id"] == ORIGINAL_STYLE or len(style["extensions"]) != 1:
            continue
        extension = style["extensions"][0]
        dimensions = style["characteristics"]["dimensions"]
        for image in (ROOT / "styles" / style["id"]).glob(f"*{extension}"):
            relative = image.relative_to(ROOT).as_posix()
            if relative not in asset_paths:
                raise ValueError(f"Unregistered image: {relative}")
            if extension == ".png" and STYLE_DIMENSIONS.fullmatch(dimensions):
                with image.open("rb") as file:
                    header = file.read(24)
                if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
                    raise ValueError(f"Invalid PNG: {relative}")
                expected = tuple(int(part) for part in dimensions.split("x"))
                if struct.unpack(">II", header[16:24]) != expected:
                    raise ValueError(f"PNG must be {dimensions}: {relative}")
    print(
        f"Validated {len(apps_by_id)} apps, {len(games_by_id)} games, "
        f"{len(style_ids)} styles, {len(asset_paths)} assets"
    )


def _csv_header(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return tuple(csv.reader(handle).__next__())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    charts = subparsers.add_parser("charts", help="Fetch the current CN and US free charts")
    charts.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    subparsers.add_parser("validate", help="Check catalog, chart ranks, and the preview page")
    subparsers.add_parser("preview", help="Regenerate preview.html from the current lists")
    args = parser.parse_args()
    if args.command == "charts":
        capture_lists(ROOT, args.date)
    elif args.command == "preview":
        from preview_html import write_preview
        write_preview(ROOT)
    else:
        validate()


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
