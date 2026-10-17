#!/usr/bin/env python3
"""Download official App Store icons and write the cross-platform map.

The iTunes Lookup API is queried by numeric App Store ID. The returned bundle ID
must match the catalog. Artwork is requested above the API's 512px URL; the CDN
response is kept only when its pixel size is smaller than the requested edge, which
is the size Apple actually serves rather than an upscale. Checkpoints and temporary
files stay under ``.cache/`` and are not part of the catalog.
"""

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from mapping import ORIGINAL_STYLE, DuplicateMappingError, assert_unique_platform_ids
from unified_id import legacy_id, unified_id_from_bundle


ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "OneWidgetAppIcons-official/1.0"
PROBE_EDGES = (10000, 2048, 1536, 1024, 768, 512, 256, 128, 100, 60)
ARTWORK_SIZE = re.compile(
    r"/(\d+)x(\d+)(bb|ss)?(\.(?:jpg|jpeg|png|webp))$",
    re.IGNORECASE,
)
PERMANENT_REASONS = {
    "not_in_store",
    "bundle_mismatch",
    "no_artwork",
    "duplicate_id",
    "refusing_overwrite",
    "upscale",
}
BATCH_SIZE = 80
ARTWORK_NOTE = (
    "Icon bytes are the file returned by the Apple iTunes Lookup artwork URL "
    "after requesting the largest size that CDN serves. This record stores the "
    "source URL, query country, time, dimensions, format, and SHA-256. It does "
    "not grant usage rights."
)
CSV_HEADER = (
    "id", "legacyId", "name", "developer", "kind",
    "appleAppStoreId", "appleBundleId",
    "androidPackageName", "harmonyBundleName", "huaweiAppGalleryId",
    "marketCount", "authorApp", "cnRank", "usRank",
    "officialIconPath", "iconWidth", "iconHeight", "iconFormat", "iconSha256",
)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def candidate_countries(app):
    """Countries to query, in order. Author apps use the US and China storefronts."""
    if app.get("authorApp") or not app.get("charts"):
        return ["us", "cn"]
    ranked = sorted(
        app["charts"],
        key=lambda item: (
            0 if item["country"] == "cn" else 1 if item["country"] == "us" else 2,
            item["rank"],
            item["country"],
        ),
    )
    countries = []
    for item in ranked:
        country = item["country"]
        if country not in countries:
            countries.append(country)
    if not countries:
        raise ValueError(f"No lookup country for {app.get('id')}")
    return countries


def rewrite_artwork_url(url, edge):
    """Replace the trailing size token, keeping the CDN suffix and file extension."""
    match = None
    for match in ARTWORK_SIZE.finditer(url):
        pass
    if match is None:
        raise ValueError(f"Unrecognized artwork URL: {url}")
    suffix = match.group(3) or ""
    extension = match.group(4)
    return url[:match.start()] + f"/{int(edge)}x{int(edge)}{suffix}{extension}" + url[match.end():]


def response_is_capped(width, height, edge):
    """True when the CDN returned a smaller master instead of filling the request."""
    return width < edge and height < edge


def sniff_format(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg", ".jpg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "gif", ".gif"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp", ".webp"
    raise ValueError("Unrecognized image format")


def decode_image(data):
    """Decode the whole image and return format, extension, width, and height."""
    from PIL import Image

    image_format, extension = sniff_format(data)
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        width, height = image.size
    if width < 1 or height < 1:
        raise ValueError("Image has no pixels")
    return image_format, extension, width, height


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def artwork_url_from_result(result):
    for key in ("artworkUrl512", "artworkUrl100", "artworkUrl60"):
        if result.get(key):
            return result[key]
    return None


def select_artwork(api_url, fetch_bytes):
    """Download the largest artwork Apple serves for this URL without upscaling it.

    A transport or decode error is raised immediately so the checkpoint can retry
    the same URL. A smaller edge is requested only when a decoded image fills the
    larger request and therefore might have been enlarged.
    """
    last_error = None
    for edge in PROBE_EDGES:
        url = rewrite_artwork_url(api_url, edge)
        data = fetch_bytes(url)
        image_format, extension, width, height = decode_image(data)
        if response_is_capped(width, height, edge):
            return {
                "sourceUrl": url,
                "apiArtworkUrl": api_url,
                "data": data,
                "format": image_format,
                "extension": extension,
                "width": width,
                "height": height,
                "sha256": sha256_bytes(data),
            }
        last_error = ValueError(
            f"Artwork response {width}x{height} filled the {edge}px request and may be upscaled"
        )
    raise ValueError(f"Could not find a non-upscaled artwork for {api_url}: {last_error}")


def original_icon_dir(root):
    return root / "styles" / ORIGINAL_STYLE


def original_icon_path(unified_id, extension):
    return f"styles/{ORIGINAL_STYLE}/{unified_id}{extension}"


def default_checkpoint_path(root):
    return root / ".cache" / "official-icons" / "checkpoint.json"


def load_checkpoint(path):
    if not path.exists():
        return {"version": 1, "apps": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("version", 1)
    data.setdefault("apps", {})
    return data


def save_checkpoint(path, checkpoint):
    write_json(path, checkpoint)


def app_store_id(app):
    return str(app["platforms"]["apple"]["appStoreId"])


def bundle_of(app):
    return app["platforms"]["apple"]["bundleId"]


def load_apps(root):
    return json.loads((root / "metadata" / "apps.json").read_text(encoding="utf-8"))["apps"]


def load_games(root):
    path = root / "metadata" / "games.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))["apps"]


def union_entries(apps, games):
    """One icon record per unified ID. Games already listed as apps are not repeated."""
    merged = []
    seen = {}
    for app in list(apps) + list(games or []):
        previous = seen.get(app["id"])
        if previous is None:
            seen[app["id"]] = app
            merged.append(app)
            continue
        if previous["platforms"]["apple"] != app["platforms"]["apple"]:
            raise ValueError(f"Apps and games disagree on Apple identity for {app['id']}")
    return merged


def load_official_icons(root):
    path = root / "metadata" / "official-icons.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("icons", [])


def _blank(value):
    return "" if value is None else value


def _rank_cell(app, key):
    value = app.get(key)
    return "" if value is None else str(value)


def list_csv_row(app, icon):
    platforms = app["platforms"]
    return (
        app["id"],
        app["legacyId"],
        app["name"],
        app["developer"],
        app.get("kind", ""),
        platforms["apple"]["appStoreId"],
        platforms["apple"]["bundleId"],
        _blank(platforms["android"]["packageName"]),
        _blank(platforms["harmony"]["bundleName"]),
        _blank(platforms["huawei"]["appGalleryId"]),
        len(app["charts"]),
        app["authorApp"],
        _rank_cell(app, "cnRank"),
        _rank_cell(app, "usRank"),
        icon.get("path", ""),
        icon.get("width", ""),
        icon.get("height", ""),
        icon.get("format", ""),
        icon.get("sha256", ""),
    )


def write_list_csv(path, apps, icons_by_id):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CSV_HEADER)
        for app in apps:
            writer.writerow(list_csv_row(app, icons_by_id.get(app["id"], {})))


def write_apps_csv(root, apps, icons_by_id, games=None):
    write_list_csv(root / "metadata" / "apps.csv", apps, icons_by_id)
    if games is not None:
        write_list_csv(root / "metadata" / "games.csv", games, icons_by_id)


def map_entry(app, icon):
    platforms = app["platforms"]
    return {
        "id": app["id"],
        "legacyId": app["legacyId"],
        "name": app["name"],
        "bundleId": platforms["apple"]["bundleId"],
        "appleAppStoreId": str(platforms["apple"]["appStoreId"]),
        "androidPackageName": platforms["android"]["packageName"],
        "harmonyBundleName": platforms["harmony"]["bundleName"],
        "huaweiAppGalleryId": platforms["huawei"]["appGalleryId"],
        "iconPath": icon.get("path") if icon else None,
    }


def write_maps(root, apps, icons, failures, status, now, games=None):
    icons_by_id = {item["id"]: item for item in icons}
    listed = union_entries(apps, games)
    entries = [map_entry(app, icons_by_id.get(app["id"])) for app in listed]
    assert_unique_platform_ids(entries)
    write_json(root / "metadata" / "platform-map.json", {
        "schemaVersion": 1,
        "status": status,
        "updatedAt": now,
        "artworkNote": ARTWORK_NOTE,
        "entries": entries,
    })
    write_json(root / "metadata" / "official-icons.json", {
        "schemaVersion": 1,
        "status": status,
        "updatedAt": now,
        "expectedCount": len(listed),
        "imageCount": len(icons),
        "failureCount": len(failures),
        "artworkNote": ARTWORK_NOTE,
        "icons": icons,
        "failures": failures,
    })
    write_apps_csv(root, apps, icons_by_id, games=games)


def rekey_overrides(root, legacy_to_new):
    path = root / "metadata" / "platform-overrides.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    apps = {}
    for key, value in document.get("apps", {}).items():
        new_key = legacy_to_new.get(key, key)
        entry = dict(value)
        if key in legacy_to_new:
            entry["legacyId"] = key
        elif "legacyId" not in entry:
            legacy = next((old for old, new in legacy_to_new.items() if new == new_key), None)
            if legacy:
                entry["legacyId"] = legacy
        apps[new_key] = entry
    evidence = {}
    for key, value in document.get("evidence", {}).items():
        evidence[legacy_to_new.get(key, key)] = value
    document["apps"] = apps
    document["evidence"] = evidence
    write_json(path, document)


def migrate_catalog(root, now=None):
    """Switch catalog IDs to bundle-ID names without changing the selected apps."""
    catalog_path = root / "metadata" / "apps.json"
    original = json.loads(catalog_path.read_text(encoding="utf-8"))
    seen = {}
    migrated = []
    for before in original["apps"]:
        apple = before["platforms"]["apple"]
        new_id = unified_id_from_bundle(apple["bundleId"])
        expected_legacy = legacy_id(apple["appStoreId"])
        current_legacy = before["legacyId"] if "legacyId" in before else before["id"]
        if current_legacy != expected_legacy:
            raise ValueError(f"Legacy ID mismatch for {apple['appStoreId']}: {current_legacy}")
        if new_id in seen:
            raise ValueError(
                f"Duplicate unified ID {new_id} for {apple['appStoreId']} and {seen[new_id]}"
            )
        seen[new_id] = apple["appStoreId"]
        huawei = before["platforms"].get("huawei") or {"appGalleryId": None}
        if "appGalleryId" not in huawei:
            raise ValueError(f"Invalid Huawei record for {new_id}")
        app = {
            "id": new_id,
            "legacyId": expected_legacy,
            "name": before["name"],
            "developer": before["developer"],
            "genre": before["genre"],
            "platforms": {
                "apple": apple,
                "android": before["platforms"]["android"],
                "harmony": before["platforms"]["harmony"],
                "huawei": {"appGalleryId": huawei.get("appGalleryId")},
            },
            "charts": before["charts"],
            "authorApp": before["authorApp"],
        }
        for optional in ("kind", "cnRank", "usRank"):
            if optional in before:
                app[optional] = before[optional]
        for key in ("name", "developer", "genre", "charts", "authorApp", "kind", "cnRank", "usRank"):
            if key in before and before[key] != app[key]:
                raise ValueError(f"Catalog field changed during migration: {key}")
        if before["platforms"]["apple"] != app["platforms"]["apple"]:
            raise ValueError("Apple identity changed during migration")
        if before["platforms"]["android"] != app["platforms"]["android"]:
            raise ValueError("Android mapping changed during migration")
        if before["platforms"]["harmony"] != app["platforms"]["harmony"]:
            raise ValueError("Harmony mapping changed during migration")
        migrated.append(app)
    if [item["platforms"]["apple"]["appStoreId"] for item in original["apps"]] != [
        item["platforms"]["apple"]["appStoreId"] for item in migrated
    ]:
        raise ValueError("App set changed during migration")
    original["apps"] = migrated
    write_json(catalog_path, original)
    rekey_overrides(root, {app["legacyId"]: app["id"] for app in migrated})
    games = load_games(root)
    listed = union_entries(migrated, games)
    icons, failures = _icons_still_valid(root, listed)
    timestamp = now or utc_now()
    status = manifest_status(listed, icons, failures)
    if status != "complete":
        status = "incomplete"
    write_maps(root, migrated, icons, failures, status=status, now=timestamp, games=games)
    return migrated


def _icons_still_valid(root, apps):
    """Keep icon and failure rows whose unified IDs still match the catalog."""
    path = root / "metadata" / "official-icons.json"
    if not path.exists():
        return [], []
    document = json.loads(path.read_text(encoding="utf-8"))
    known = {app["id"]: app for app in apps}
    icons = []
    for icon in document.get("icons", []):
        app = known.get(icon.get("id"))
        if app and icon.get("legacyId") == app["legacyId"] and icon.get("bundleId") == bundle_of(app):
            icons.append(icon)
    failures = []
    icon_ids = {icon["id"] for icon in icons}
    for failure in document.get("failures", []):
        app = known.get(failure.get("id"))
        if app and failure.get("id") not in icon_ids and failure.get("legacyId") == app["legacyId"]:
            failures.append(failure)
    return icons, failures


def collision_groups(apps):
    groups = {}
    for app in apps:
        groups.setdefault(app["id"], []).append(app)
    return {key: value for key, value in groups.items() if len(value) > 1}


def _identity(app, store_id):
    return {
        "id": app["id"],
        "legacyId": app["legacyId"],
        "name": app["name"],
        "bundleId": bundle_of(app),
        "appStoreId": store_id,
    }


def _failed(app, store_id, reason, detail, country):
    record = _identity(app, store_id)
    record.update({
        "status": "failed",
        "reason": reason,
        "detail": detail,
        "country": country,
    })
    return record


def _resolved(app, store_id, country, artwork):
    record = _identity(app, store_id)
    record.update({
        "status": "resolved",
        "country": country,
        "sourceApiUrl": artwork,
    })
    return record


def resolve_lookups(apps, fetch_lookup, log=None):
    """Look up each app in its candidate countries until the bundle ID matches."""
    log = log or (lambda *_args: None)
    pending = {app_store_id(app): app for app in apps}
    country_lists = {store_id: candidate_countries(app) for store_id, app in pending.items()}
    index = {store_id: 0 for store_id in pending}
    mismatches = {store_id: [] for store_id in pending}
    network_errors = {store_id: [] for store_id in pending}
    outcomes = {}

    while True:
        groups = {}
        for store_id in pending:
            countries = country_lists[store_id]
            cursor = index[store_id]
            if cursor >= len(countries):
                continue
            groups.setdefault(countries[cursor], []).append(store_id)
        if not groups:
            break
        for country, store_ids in groups.items():
            for offset in range(0, len(store_ids), BATCH_SIZE):
                batch = store_ids[offset:offset + BATCH_SIZE]
                for store_id in batch:
                    index[store_id] += 1
                log(f"lookup {country} {len(batch)} apps")
                try:
                    results = fetch_lookup(country, list(batch))
                except Exception as exc:
                    for store_id in batch:
                        network_errors[store_id].append(f"{country}: {exc}")
                    continue
                grouped = {}
                for result in results:
                    grouped.setdefault(str(result.get("trackId")), []).append(result)
                for store_id in batch:
                    app = pending[store_id]
                    matches = grouped.get(store_id, [])
                    exact = [item for item in matches if item.get("bundleId") == bundle_of(app)]
                    if exact:
                        artwork = artwork_url_from_result(exact[0])
                        if artwork:
                            outcomes[store_id] = _resolved(app, store_id, country, artwork)
                        else:
                            outcomes[store_id] = _failed(
                                app, store_id, "no_artwork",
                                f"Lookup in {country} matched the bundle ID but returned no artwork URL",
                                country,
                            )
                        pending.pop(store_id, None)
                    elif matches:
                        returned = ", ".join(sorted(
                            {str(item.get("bundleId")) for item in matches}
                        ))
                        mismatches[store_id].append(f"{country} returned {returned}")

    for store_id, app in pending.items():
        if network_errors[store_id]:
            outcomes[store_id] = _failed(
                app, store_id, "network",
                "Lookup failed: " + "; ".join(network_errors[store_id]),
                None,
            )
        elif mismatches[store_id]:
            outcomes[store_id] = _failed(
                app, store_id, "bundle_mismatch",
                "bundleId mismatch: " + "; ".join(mismatches[store_id]),
                None,
            )
        else:
            tried = ", ".join(country_lists[store_id]) or "(none)"
            outcomes[store_id] = _failed(
                app, store_id, "not_in_store",
                f"No lookup result in {tried}",
                None,
            )
    for app in apps:
        store_id = app_store_id(app)
        if store_id not in outcomes:
            raise RuntimeError(f"Lookup produced no outcome for {store_id}")
    return outcomes


def _checkpoint_file_ok(root, record):
    path = root / record.get("path", "")
    if not path.is_file():
        return False
    data = path.read_bytes()
    if sha256_bytes(data) != record.get("sha256"):
        return False
    image_format, _extension, width, height = decode_image(data)
    return (
        image_format == record.get("format")
        and width == record.get("width")
        and height == record.get("height")
        and Path(record["path"]).stem == record["id"]
    )


def _write_icon(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() == data:
            return
        raise FileExistsError(f"Refusing to overwrite {path.as_posix()}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _download_failure_reason(exc):
    message = str(exc)
    if isinstance(exc, FileExistsError):
        return "refusing_overwrite"
    if "non-upscaled" in message or "may be upscaled" in message:
        return "upscale"
    if (
        "Unrecognized image" in message
        or "cannot identify" in message.lower()
        or isinstance(exc, ValueError) and "Image" in message
    ):
        return "decode"
    return "network"


def sync_official_icons(
    apps, root, *, fetch_lookup, fetch_bytes, checkpoint_path, workers=4,
    clock=None, retry_permanent=False, log=None,
):
    """Download missing official icons. Completed checkpoint entries are not fetched again."""
    clock = clock or utc_now
    log = log or (lambda *_args: None)
    checkpoint = load_checkpoint(checkpoint_path)
    records = checkpoint["apps"]
    lock = threading.Lock()
    icon_dir = original_icon_dir(root)
    icon_dir.mkdir(parents=True, exist_ok=True)

    collisions = collision_groups(apps)
    if collisions:
        for unified, grouped in collisions.items():
            detail = (
                f"Unified ID {unified} is shared by "
                + ", ".join(app_store_id(app) for app in grouped)
            )
            for app in grouped:
                records[app_store_id(app)] = _failed(app, app_store_id(app), "duplicate_id", detail, None)
                records[app_store_id(app)]["updatedAt"] = clock()
        save_checkpoint(checkpoint_path, checkpoint)

    def persist():
        with lock:
            save_checkpoint(checkpoint_path, checkpoint)

    pending = []
    for app in apps:
        if app["id"] in collisions:
            continue
        store_id = app_store_id(app)
        current = records.get(store_id)
        if current and current.get("status") == "ok" and _checkpoint_file_ok(root, current):
            continue
        if (
            current and current.get("status") == "failed"
            and current.get("reason") in PERMANENT_REASONS
            and not retry_permanent
        ):
            continue
        pending.append(app)

    need_lookup = []
    for app in pending:
        current = records.get(app_store_id(app))
        if current and current.get("status") == "resolved" and current.get("sourceApiUrl"):
            if current.get("bundleId") == bundle_of(app) and current.get("id") == app["id"]:
                continue
        need_lookup.append(app)
    if need_lookup:
        outcomes = resolve_lookups(need_lookup, fetch_lookup, log=log)
        for app in need_lookup:
            store_id = app_store_id(app)
            outcome = outcomes[store_id]
            outcome["updatedAt"] = clock()
            records[store_id] = outcome
        persist()

    download_apps = []
    seen = set()
    for app in pending:
        store_id = app_store_id(app)
        current = records.get(store_id)
        if not current or current.get("status") != "resolved" or store_id in seen:
            continue
        seen.add(store_id)
        download_apps.append(app)

    saved = {"count": sum(1 for item in records.values() if item.get("status") == "ok")}

    def download_one(app):
        store_id = app_store_id(app)
        current = records[store_id]
        artwork = select_artwork(current["sourceApiUrl"], fetch_bytes)
        destination = icon_dir / f"{app['id']}{artwork['extension']}"
        relative_expected = original_icon_path(app["id"], artwork["extension"])
        relative = destination.relative_to(root).as_posix()
        if relative != relative_expected:
            raise ValueError(f"Original icon path must stay under styles/{ORIGINAL_STYLE}: {relative}")
        _write_icon(destination, artwork["data"])
        saved_bytes = destination.read_bytes()
        if sha256_bytes(saved_bytes) != artwork["sha256"]:
            raise ValueError(f"Hash changed while writing {relative}")
        image_format, _extension, width, height = decode_image(saved_bytes)
        if (image_format, width, height) != (artwork["format"], artwork["width"], artwork["height"]):
            raise ValueError(f"Decoded image does not match the download for {relative}")
        record = _identity(app, store_id)
        record.update({
            "status": "ok",
            "path": relative,
            "sourceUrl": artwork["sourceUrl"],
            "apiArtworkUrl": artwork["apiArtworkUrl"],
            "country": current["country"],
            "updatedAt": clock(),
            "width": artwork["width"],
            "height": artwork["height"],
            "format": artwork["format"],
            "sha256": artwork["sha256"],
        })
        return store_id, record

    def store_success(store_id, record):
        with lock:
            records[store_id] = record
            saved["count"] += 1
            count = saved["count"]
        persist()
        log(f"saved {count} {record['id']} {record['width']}x{record['height']} {record['format']}")

    def store_error(app, exc):
        reason = _download_failure_reason(exc)
        with lock:
            previous = records.get(app_store_id(app), {})
            record = _failed(app, app_store_id(app), reason, str(exc), previous.get("country"))
            record["updatedAt"] = clock()
            if previous.get("sourceApiUrl"):
                record["sourceApiUrl"] = previous["sourceApiUrl"]
            records[app_store_id(app)] = record
        persist()
        log(f"failed {app['id']} {reason}: {exc}")

    if workers <= 1:
        for app in download_apps:
            try:
                store_id, record = download_one(app)
            except Exception as exc:
                store_error(app, exc)
            else:
                store_success(store_id, record)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(download_one, app): app for app in download_apps}
            for future in as_completed(futures):
                app = futures[future]
                try:
                    store_id, record = future.result()
                except Exception as exc:
                    store_error(app, exc)
                else:
                    store_success(store_id, record)
    return records


def manifest_status(apps, icons, failures):
    accounted = {item["id"] for item in icons} | {item["id"] for item in failures}
    if len(accounted) != len(apps) or any(app["id"] not in accounted for app in apps):
        return "incomplete"
    if any(item.get("reason") not in PERMANENT_REASONS for item in failures):
        return "incomplete"
    return "complete"


def records_to_manifest(apps, records):
    icons = []
    failures = []
    for app in apps:
        record = records.get(app_store_id(app))
        if not record or record.get("status") not in ("ok", "failed"):
            continue
        if record["status"] == "ok":
            icons.append({
                "id": app["id"],
                "legacyId": app["legacyId"],
                "name": app["name"],
                "bundleId": bundle_of(app),
                "appStoreId": app_store_id(app),
                "path": record["path"],
                "sourceUrl": record["sourceUrl"],
                "country": record["country"],
                "updatedAt": record["updatedAt"],
                "width": record["width"],
                "height": record["height"],
                "format": record["format"],
                "sha256": record["sha256"],
            })
        else:
            failures.append({
                "id": app["id"],
                "legacyId": app["legacyId"],
                "name": app["name"],
                "bundleId": bundle_of(app),
                "appStoreId": app_store_id(app),
                "reason": record.get("reason"),
                "detail": record.get("detail", ""),
                "country": record.get("country"),
                "updatedAt": record.get("updatedAt"),
            })
    return icons, failures


def _extension_for_format(image_format):
    return {"jpeg": ".jpg", "png": ".png", "webp": ".webp", "gif": ".gif"}.get(image_format)


def verify(root, require_complete=None):
    """Check IDs, mapping rows, icon bytes, and paths against each other."""
    catalog = json.loads((root / "metadata" / "apps.json").read_text(encoding="utf-8"))
    apps = catalog["apps"]
    games = load_games(root)
    listed = union_entries(apps, games)
    official_path = root / "metadata" / "official-icons.json"
    map_path = root / "metadata" / "platform-map.json"
    if not official_path.is_file() or not map_path.is_file():
        raise ValueError("Missing official icon manifest or platform map")
    official = json.loads(official_path.read_text(encoding="utf-8"))
    mapping = json.loads(map_path.read_text(encoding="utf-8"))
    overrides = json.loads((root / "metadata" / "platform-overrides.json").read_text(encoding="utf-8"))
    if require_complete is None:
        require_complete = official.get("status") == "complete"
    if official.get("status") != mapping.get("status"):
        raise ValueError("Official icon status does not match the platform map")

    seen_ids = set()
    seen_legacy = set()
    seen_store = set()
    seen_bundle = set()
    for app in listed:
        apple = app["platforms"]["apple"]
        expected_id = unified_id_from_bundle(apple["bundleId"])
        expected_legacy = legacy_id(apple["appStoreId"])
        if app["id"] != expected_id or app.get("legacyId") != expected_legacy:
            raise ValueError(f"Invalid unified ID: {app['id']}")
        if app["id"] in seen_ids or expected_legacy in seen_legacy or apple["appStoreId"] in seen_store:
            raise ValueError(f"Duplicate catalog identity: {app['id']}")
        if apple["bundleId"] in seen_bundle:
            raise ValueError(f"Duplicate bundle ID: {apple['bundleId']}")
        seen_ids.add(app["id"])
        seen_legacy.add(expected_legacy)
        seen_store.add(apple["appStoreId"])
        seen_bundle.add(apple["bundleId"])
        huawei = app["platforms"].get("huawei")
        if not huawei or set(huawei) != {"appGalleryId"}:
            raise ValueError(f"Missing Huawei field: {app['id']}")
        for platform, field in (
            ("android", "packageName"),
            ("harmony", "bundleName"),
            ("huawei", "appGalleryId"),
        ):
            value = app["platforms"][platform][field]
            if value is None:
                continue
            override = overrides.get("apps", {}).get(app["id"], {})
            recorded = (override.get(platform) or {}).get(field)
            if recorded != value:
                raise ValueError(f"Unverified {platform} id on {app['id']}: {value}")

    one = next((app for app in listed if app["legacyId"] == "app-1527355884"), None)
    if one is not None:
        if one["id"] != "app_imone_onewidget":
            raise ValueError("OneWidget unified ID is not app_imone_onewidget")
        if one["platforms"]["apple"]["bundleId"] != "app.imone.OneWidget":
            raise ValueError("OneWidget bundle ID changed")
        if one["platforms"]["android"]["packageName"] != "tech.onenice.onewidget":
            raise ValueError("OneWidget Android package changed")
        if one["platforms"]["harmony"]["bundleName"] != "tech.onenice.onewidget":
            raise ValueError("OneWidget Harmony bundle changed")
        if one["platforms"]["huawei"]["appGalleryId"] is not None:
            raise ValueError("OneWidget Huawei ID must stay empty until it is verified")

    entries = mapping["entries"]
    if [entry["id"] for entry in entries] != [app["id"] for app in listed]:
        raise ValueError("Platform map is not the same sequence as the apps and games lists")
    assert_unique_platform_ids(entries)
    icons = official["icons"]
    failures = official["failures"]
    icons_by_id = {}
    for icon in icons:
        if icon["id"] in icons_by_id:
            raise ValueError(f"Duplicate icon record: {icon['id']}")
        icons_by_id[icon["id"]] = icon
    failed_ids = set()
    for failure in failures:
        if failure["id"] in failed_ids or failure["id"] in icons_by_id:
            raise ValueError(f"Duplicate or conflicting failure record: {failure['id']}")
        failed_ids.add(failure["id"])
        if not failure.get("reason") or not failure.get("detail"):
            raise ValueError(f"Failure record is missing a reason: {failure['id']}")

    for app, entry in zip(listed, entries):
        platforms = app["platforms"]
        expected = {
            "id": app["id"],
            "legacyId": app["legacyId"],
            "name": app["name"],
            "bundleId": platforms["apple"]["bundleId"],
            "appleAppStoreId": str(platforms["apple"]["appStoreId"]),
            "androidPackageName": platforms["android"]["packageName"],
            "harmonyBundleName": platforms["harmony"]["bundleName"],
            "huaweiAppGalleryId": platforms["huawei"]["appGalleryId"],
        }
        for key, value in expected.items():
            if entry.get(key) != value:
                raise ValueError(f"Platform map field {key} mismatch for {app['id']}")
        icon = icons_by_id.get(app["id"])
        expected_path = icon["path"] if icon else None
        if entry.get("iconPath") != expected_path:
            raise ValueError(f"Platform map icon path mismatch for {app['id']}")

    icon_dir = original_icon_dir(root)
    recorded_paths = set()
    for icon in icons:
        path = icon["path"]
        if path != original_icon_path(icon["id"], _extension_for_format(icon["format"])):
            raise ValueError(f"Icon path does not use the unified ID and real format: {path}")
        file_path = root / path
        if not file_path.is_file():
            raise ValueError(f"Missing image: {path}")
        data = file_path.read_bytes()
        digest = sha256_bytes(data)
        if digest != icon["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {path}")
        image_format, extension, width, height = decode_image(data)
        if image_format != icon["format"] or file_path.suffix != extension:
            raise ValueError(f"Image format mismatch: {path}")
        if width != icon["width"] or height != icon["height"]:
            raise ValueError(f"Image dimension mismatch: {path}")
        if icon["id"] not in seen_ids or icon["bundleId"] != next(
            app["platforms"]["apple"]["bundleId"] for app in listed if app["id"] == icon["id"]
        ):
            raise ValueError(f"Icon identity does not match the catalog: {icon['id']}")
        if not icon.get("sourceUrl") or not icon.get("country") or not icon.get("updatedAt"):
            raise ValueError(f"Icon record is missing source metadata: {path}")
        recorded_paths.add(path)

    if icon_dir.exists():
        for file_path in sorted(icon_dir.iterdir()):
            if not file_path.is_file():
                continue
            relative = file_path.relative_to(root).as_posix()
            if relative not in recorded_paths:
                raise ValueError(f"Unregistered image: {relative}")

    _check_list_csv(root / "metadata" / "apps.csv", apps, icons_by_id, "apps.json")
    if games is not None:
        _check_list_csv(root / "metadata" / "games.csv", games, icons_by_id, "games.json")

    if official.get("imageCount") != len(icons) or official.get("failureCount") != len(failures):
        raise ValueError("Official icon counts do not match the records")
    if official.get("expectedCount") != len(listed):
        raise ValueError("Official icon expected count does not match the catalog")
    status = manifest_status(listed, icons, failures)
    if require_complete and status != "complete":
        raise ValueError(
            f"Official icons are incomplete: {len(icons)} images, {len(failures)} failures, "
            f"{len(listed)} apps"
        )
    if official.get("status") == "complete" and status != "complete":
        raise ValueError("Manifest is marked complete but some apps are unresolved")
    if _has_license_key(official) or _has_license_key(mapping):
        raise ValueError("Icon metadata must not invent a license claim")
    game_count = 0 if games is None else len(games)
    print(
        f"Verified {len(apps)} apps, {game_count} games, {len(icons)} official icons, "
        f"{len(failures)} failures, status {official.get('status')}"
    )
    return {
        "apps": len(apps),
        "games": game_count,
        "icons": len(icons),
        "failures": len(failures),
        "status": official.get("status"),
    }


def _check_list_csv(path, apps, icons_by_id, label):
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CSV_HEADER:
            raise ValueError(f"CSV header mismatch in {path.name}: {reader.fieldnames}")
        rows = list(reader)
    if [row["id"] for row in rows] != [app["id"] for app in apps]:
        raise ValueError(f"CSV list differs from {label}")
    for row, app in zip(rows, apps):
        icon = icons_by_id.get(app["id"], {})
        if row["legacyId"] != app["legacyId"] or row["name"] != app["name"]:
            raise ValueError(f"CSV identity mismatch: {app['id']}")
        if row["kind"] != app.get("kind", ""):
            raise ValueError(f"CSV kind mismatch: {app['id']}")
        if row["cnRank"] != _rank_cell(app, "cnRank") or row["usRank"] != _rank_cell(app, "usRank"):
            raise ValueError(f"CSV rank mismatch: {app['id']}")
        if row["officialIconPath"] != icon.get("path", ""):
            raise ValueError(f"CSV icon path mismatch: {app['id']}")
        if icon and (
            row["iconSha256"] != icon["sha256"]
            or row["iconFormat"] != icon["format"]
            or row["iconWidth"] != str(icon["width"])
            or row["iconHeight"] != str(icon["height"])
        ):
            raise ValueError(f"CSV icon metadata mismatch: {app['id']}")


def _has_license_key(value):
    if isinstance(value, dict):
        if any(key.lower() == "license" for key in value):
            return True
        return any(_has_license_key(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_license_key(item) for item in value)
    return False


def production_fetch_lookup(country, store_ids):
    url = "https://itunes.apple.com/lookup?id=" + ",".join(store_ids) + "&country=" + country
    last_error = None
    for attempt in range(6):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=60) as response:
                payload = json.load(response)
            time.sleep(0.35)
            return payload.get("results", [])
        except Exception as exc:
            last_error = exc
            code = getattr(exc, "code", None)
            if code in (400, 404):
                break
            time.sleep(min(2 ** attempt, 20))
    raise RuntimeError(f"Lookup failed for {country}: {last_error}")


def production_fetch_bytes(url):
    last_error = None
    for attempt in range(8):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=60) as response:
                data = response.read()
            if not data:
                raise ValueError("Empty artwork response")
            return data
        except Exception as exc:
            last_error = exc
            time.sleep(min(2 ** attempt, 20))
    raise RuntimeError(f"Artwork download failed for {url}: {last_error}")


def command_migrate(root):
    apps = migrate_catalog(root)
    print(f"Migrated {len(apps)} apps; official icons are incomplete")


def prune_original_icons(root, keep_ids):
    """Delete original icons whose unified ID is no longer on either list."""
    icon_dir = original_icon_dir(root)
    if not icon_dir.is_dir():
        return []
    removed = []
    for file_path in sorted(icon_dir.iterdir()):
        if not file_path.is_file() or file_path.name.startswith("."):
            continue
        if file_path.stem not in keep_ids:
            file_path.unlink()
            removed.append(file_path.name)
    return removed


def command_download(root, workers, rounds, limit, retry_permanent):
    apps = load_apps(root)
    games = load_games(root)
    listed = union_entries(apps, games)
    if any("legacyId" not in app for app in listed):
        raise ValueError("Catalog IDs have not been migrated")
    removed = prune_original_icons(root, {app["id"] for app in listed})
    if removed:
        print(f"Removed {len(removed)} original icons that are no longer listed", file=sys.stderr, flush=True)
    checkpoint_path = default_checkpoint_path(root)
    selected = listed[:limit] if limit else listed

    def log(message):
        print(message, file=sys.stderr, flush=True)

    status = "incomplete"
    for round_index in range(rounds):
        records = sync_official_icons(
            selected, root,
            fetch_lookup=production_fetch_lookup,
            fetch_bytes=production_fetch_bytes,
            checkpoint_path=checkpoint_path,
            workers=workers,
            retry_permanent=retry_permanent,
            log=log,
        )
        icons, failures = records_to_manifest(listed, records)
        status = manifest_status(listed, icons, failures)
        write_maps(root, apps, icons, failures, status=status, now=utc_now(), games=games)
        transient = [item for item in failures if item.get("reason") not in PERMANENT_REASONS]
        print(
            f"Round {round_index + 1}: {len(icons)} images, {len(failures)} failures, status {status}",
            file=sys.stderr, flush=True,
        )
        if status == "complete" or not transient:
            break
    if (root / "metadata" / "games.json").is_file():
        from preview_html import write_preview
        write_preview(root)
    summary = verify(root, require_complete=False)
    return 0 if summary["status"] == "complete" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="repository root")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("migrate", help="Rename catalog IDs and write an empty icon map")
    download = subparsers.add_parser("download", help="Download official icons, resuming from the checkpoint")
    download.add_argument("--workers", type=int, default=4)
    download.add_argument("--rounds", type=int, default=4)
    download.add_argument("--limit", type=int, help="only process the first N catalog apps")
    download.add_argument("--retry-failed", action="store_true", help="retry permanent lookup failures")
    subparsers.add_parser("verify", help="Check icon files, hashes, and mapping rows")
    args = parser.parse_args()
    root = args.root or ROOT
    try:
        if args.command == "migrate":
            command_migrate(root)
        elif args.command == "download":
            return command_download(root, args.workers, args.rounds, args.limit, args.retry_failed)
        else:
            verify(root)
    except (OSError, ValueError, RuntimeError, DuplicateMappingError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
