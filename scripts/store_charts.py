#!/usr/bin/env python3
"""Build the China and US free-chart lists for apps and games.

Apple's public iPhone free chart currently returns about 200 ids. The apps list
asks for 500 and keeps every id the endpoint actually returns, up to 500. The
games list keeps the first 200. Ranks are that chart's position; a blank rank
means the app is not on that region's chart.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from unified_id import legacy_id, unified_id_from_bundle


ROOT = Path(__file__).resolve().parents[1]
AUTHOR_ID = "1250290964"
APPS_DEPTH = 500
GAMES_DEPTH = 200
FREE_CHART_ID = "27"
GAME_GENRE_MIN = 7001
GAME_GENRE_MAX = 7019
STOREFRONTS = {
    "cn": "143465-19,29",
    "us": "143441-1,29",
}
LISTS = {
    "apps": {"genreId": "36", "depth": APPS_DEPTH},
    "games": {"genreId": "6014", "depth": GAMES_DEPTH},
}
ENTRY_FIELDS = (
    "id", "legacyId", "name", "developer", "kind", "genre", "platforms",
    "charts", "cnRank", "usRank", "authorApp",
)
APPS_NOTE = (
    "请求中国区和美国区 iPhone 免费应用总榜各自前 500 名。"
    "苹果公开的 viewTop 总榜目前每个地区大约只返回 200 个名次，网页展示上限也是 200，"
    "没有公开的第 201 名以后的总榜，所以应用表收录接口实际返回的全部名次，不会补造到 500。"
    "cnRank、usRank 是对应地区应用总榜的序号，没有上榜则为空。"
    "kind 为 game 或 application，表示这条是游戏还是应用。"
)
GAMES_NOTE = (
    "中国区和美国区 iPhone 免费游戏榜各自前 200 名，按统一 ID 去重。"
    "cnRank、usRank 是对应地区游戏榜的序号，没有上榜则为空。"
    "字段和应用列表相同。"
)
NOTES = {"apps": APPS_NOTE, "games": GAMES_NOTE}
LIST_RULE = "中国区和美国区当前免费榜按统一 ID 去重；名次是该区这张榜的序号，未上榜留空。"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def free_chart_ids(payload):
    """Return the Top Free adam ids. Chart id 27 is free; the first chart is often paid."""
    charts = payload["pageData"]["segmentedControl"]["segments"][0]["pageData"]["topCharts"]
    free = next(chart for chart in charts if str(chart.get("id")) == FREE_CHART_ID)
    ids = [str(item) for item in free["adamIds"]]
    if not ids or any(not item.isdecimal() for item in ids):
        raise ValueError("Free chart is empty or contains a non-numeric App Store ID")
    if len(ids) != len(set(ids)):
        raise ValueError("Free chart repeats an App Store ID")
    return ids


def take_ranks(ids, depth):
    """Map the first `depth` chart ids to 1-based ranks. Shorter charts are kept whole."""
    if depth < 1:
        raise ValueError("Chart depth must be positive")
    selected = list(ids)[:depth]
    return {store_id: rank for rank, store_id in enumerate(selected, start=1)}


def kind_from_genre(genre_id, genre_name):
    """Classify a store listing as a game or an application from its primary genre."""
    text = str(genre_name or "").strip().casefold()
    if text in {"games", "game", "游戏"} or text.startswith("games"):
        return "game"
    try:
        numeric = int(genre_id)
    except (TypeError, ValueError):
        return "application"
    if numeric == 6014 or GAME_GENRE_MIN <= numeric <= GAME_GENRE_MAX:
        return "game"
    return "application"


def merge_regions(cn_ranks, us_ranks):
    """Union of two regional rank maps. A missing region stays None."""
    rows = []
    for store_id in set(cn_ranks) | set(us_ranks):
        rows.append({
            "appStoreId": store_id,
            "cnRank": cn_ranks.get(store_id),
            "usRank": us_ranks.get(store_id),
        })
    return rows


def list_sort_key(entry):
    cn_rank = entry["cnRank"]
    us_rank = entry["usRank"]
    present = [rank for rank in (cn_rank, us_rank) if rank is not None]
    best = min(present) if present else 10**9
    return (
        best,
        cn_rank if cn_rank is not None else 10**9,
        us_rank if us_rank is not None else 10**9,
        entry["name"].casefold(),
        entry["id"],
    )


def _platform(override, platform, field):
    recorded = override.get(platform) or {}
    value = recorded.get(field)
    return {field: value if value else None}


def make_entry(result, ranks, overrides):
    store_id = str(result["trackId"])
    bundle_id = result["bundleId"]
    if not bundle_id or store_id != ranks["appStoreId"]:
        raise ValueError(f"Lookup identity does not match chart id {ranks['appStoreId']}")
    app_id = unified_id_from_bundle(bundle_id)
    alias = legacy_id(store_id)
    override = overrides.get(app_id) or {}
    if override.get("legacyId") and override["legacyId"] != alias:
        override = {}
    cn_rank = ranks["cnRank"]
    us_rank = ranks["usRank"]
    charts = []
    if cn_rank is not None:
        charts.append({"country": "cn", "rank": cn_rank})
    if us_rank is not None:
        charts.append({"country": "us", "rank": us_rank})
    genre_id = str(result["primaryGenreId"])
    genre_name = result.get("primaryGenreName") or ""
    entry = {
        "id": app_id,
        "legacyId": alias,
        "name": result["trackName"],
        "developer": result.get("artistName") or "",
        "kind": kind_from_genre(genre_id, genre_name),
        "genre": {"id": genre_id, "name": genre_name},
        "platforms": {
            "apple": {
                "appStoreId": store_id,
                "bundleId": bundle_id,
                "url": f"https://apps.apple.com/app/id{store_id}",
            },
            "android": _platform(override, "android", "packageName"),
            "harmony": _platform(override, "harmony", "bundleName"),
            "huawei": _platform(override, "huawei", "appGalleryId"),
        },
        "charts": charts,
        "cnRank": cn_rank,
        "usRank": us_rank,
        "authorApp": str(result.get("artistId")) == AUTHOR_ID,
    }
    if tuple(entry) != ENTRY_FIELDS:
        raise ValueError(f"Entry fields drifted for {app_id}")
    return entry


def build_list(rank_rows, lookups, overrides):
    entries = []
    seen = {}
    for row in rank_rows:
        result = lookups[row["appStoreId"]]
        entry = make_entry(result, row, overrides)
        previous = seen.get(entry["id"])
        if previous is not None:
            raise ValueError(
                f"Duplicate unified ID {entry['id']} for {previous} and {row['appStoreId']}"
            )
        seen[entry["id"]] = row["appStoreId"]
        entries.append(entry)
    entries.sort(key=list_sort_key)
    return entries


def _fetch_json(url, headers):
    last_error = None
    for attempt in range(4):
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=45) as response:
                data = response.read()
            if data[:2] == b"\x1f\x8b":
                import gzip
                data = gzip.decompress(data)
            return json.loads(data)
        except Exception as exc:
            last_error = exc
            time.sleep(attempt + 1)
    raise RuntimeError(f"Could not fetch {url}: {last_error}")


def fetch_free_chart(country, genre_id):
    url = (
        "https://itunes.apple.com/WebObjects/MZStore.woa/wa/viewTop"
        f"?genreId={genre_id}&popId=27&dataOnly=true&l=en&cc={country}"
    )
    payload = _fetch_json(url, {
        "User-Agent": "iTunes/12.12 (Macintosh; OS X 10.15) AppleWebKit/605.1.15",
        "X-Apple-Store-Front": STOREFRONTS[country],
        "Accept": "application/json",
    })
    ids = free_chart_ids(payload)
    if len(ids) < 100:
        raise RuntimeError(f"{country} genre {genre_id} returned only {len(ids)} ids")
    return ids, url


def _lookup_results(fetch_lookup, country, store_ids):
    found = {}
    for offset in range(0, len(store_ids), 80):
        batch = store_ids[offset:offset + 80]
        results = fetch_lookup(country, list(batch))
        for item in results:
            if item.get("wrapperType") not in (None, "software"):
                continue
            if not item.get("bundleId") or item.get("trackId") is None:
                continue
            found[str(item["trackId"])] = item
    return found


def lookup_chart_apps(store_ids, on_cn_chart, fetch_lookup):
    """Look up each id once. Apps on the China chart use the China storefront name."""
    pending_cn = [store_id for store_id in store_ids if store_id in on_cn_chart]
    pending_us = [store_id for store_id in store_ids if store_id not in on_cn_chart]
    found = {}
    found.update(_lookup_results(fetch_lookup, "cn", pending_cn))
    found.update(_lookup_results(fetch_lookup, "us", pending_us))
    missing = [store_id for store_id in store_ids if store_id not in found]
    if missing:
        retry_us = [store_id for store_id in missing if store_id in on_cn_chart]
        retry_cn = [store_id for store_id in missing if store_id not in on_cn_chart]
        found.update(_lookup_results(fetch_lookup, "us", retry_us))
        found.update(_lookup_results(fetch_lookup, "cn", retry_cn))
        missing = [store_id for store_id in store_ids if store_id not in found]
        if missing:
            raise RuntimeError(f"Lookup missed {len(missing)} chart apps, including {missing[:8]}")
    return found


def _list_document(list_name, entries, ranks, captured_at, snapshot_name):
    spec = LISTS[list_name]
    return {
        "schemaVersion": 2,
        "generatedAt": captured_at,
        "list": list_name,
        "snapshot": snapshot_name,
        "chart": {
            "type": "top-free-iphone",
            "popId": FREE_CHART_ID,
            "genreId": spec["genreId"],
            "countries": ["cn", "us"],
            "requestedDepth": spec["depth"],
            "availableDepth": {country: ranks[country]["available"] for country in ("cn", "us")},
            "usedDepth": {country: ranks[country]["used"] for country in ("cn", "us")},
            "note": NOTES[list_name],
        },
        "selection": {
            "count": len(entries),
            "rule": LIST_RULE,
        },
        "apps": entries,
    }


def capture_lists(root, date, fetch_chart=None, fetch_lookup=None):
    """Fetch CN/US free charts, write both lists, and refresh the preview page."""
    from official_icons import load_official_icons, write_apps_csv
    from preview_html import write_preview

    fetch_chart = fetch_chart or fetch_free_chart
    if fetch_lookup is None:
        from official_icons import production_fetch_lookup
        fetch_lookup = production_fetch_lookup
    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    snapshot_name = f"data/store-charts-{date}.json"
    snapshot_charts = {}
    regional_ranks = {}
    all_ids = []
    on_cn = set()
    for list_name, spec in LISTS.items():
        snapshot_charts[list_name] = {"genreId": spec["genreId"]}
        regional_ranks[list_name] = {}
        for country in ("cn", "us"):
            ids, source = fetch_chart(country, spec["genreId"])
            used = min(spec["depth"], len(ids))
            ranks = take_ranks(ids, spec["depth"])
            regional_ranks[list_name][country] = {
                "ranks": ranks,
                "available": len(ids),
                "used": used,
            }
            snapshot_charts[list_name][country] = {
                "storefront": STOREFRONTS[country],
                "source": source,
                "ids": ids,
            }
            all_ids.extend(ranks)
            if country == "cn":
                on_cn.update(ranks)
            print(f"{list_name} {country}: available {len(ids)}, used {used}", flush=True)

    unique_ids = list(dict.fromkeys(all_ids))
    lookups = lookup_chart_apps(unique_ids, on_cn, fetch_lookup)
    overrides = json.loads((root / "metadata" / "platform-overrides.json").read_text(encoding="utf-8"))
    override_apps = overrides.get("apps", {})

    documents = {}
    for list_name in LISTS:
        rows = merge_regions(
            regional_ranks[list_name]["cn"]["ranks"],
            regional_ranks[list_name]["us"]["ranks"],
        )
        entries = build_list(rows, lookups, override_apps)
        documents[list_name] = _list_document(
            list_name, entries, regional_ranks[list_name], captured_at, snapshot_name,
        )
        print(f"{list_name}: {len(entries)} unique", flush=True)

    shared = {entry["id"]: entry for entry in documents["apps"]["apps"]}
    for entry in documents["games"]["apps"]:
        other = shared.get(entry["id"])
        if other is None:
            continue
        for field in ("legacyId", "name", "developer", "kind", "authorApp"):
            if entry[field] != other[field]:
                raise ValueError(f"Apps and games disagree on {field} for {entry['id']}")
        if entry["platforms"] != other["platforms"] or entry["genre"] != other["genre"]:
            raise ValueError(f"Apps and games disagree on identity for {entry['id']}")

    snapshot = {
        "schemaVersion": 1,
        "capturedAt": captured_at,
        "source": "https://itunes.apple.com/WebObjects/MZStore.woa/wa/viewTop",
        "popId": FREE_CHART_ID,
        "note": APPS_NOTE,
        "charts": snapshot_charts,
    }
    write_json(root / snapshot_name, snapshot)
    write_json(root / "metadata" / "apps.json", documents["apps"])
    write_json(root / "metadata" / "games.json", documents["games"])
    icons = {icon["id"]: icon for icon in load_official_icons(root)}
    write_apps_csv(root, documents["apps"]["apps"], icons, games=documents["games"]["apps"])
    write_preview(root)
    return documents
