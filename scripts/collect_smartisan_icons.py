#!/usr/bin/env python3
"""Collect the Smartisan OS icon library still served by icon.smartisan.com.

Images land in ``smartisan/icons/``. Names, Android package names, and any
Apple App Store match land in ``smartisan/catalog.json``. An entry stays in
the catalog when Apple cannot be matched; it keeps the package name and
whatever display name was found.
"""

import argparse
import base64
import csv
import hashlib
import json
import re
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
ICON_ROOT = ROOT / "smartisan"
ICON_DIR = ICON_ROOT / "icons"
CACHE = ROOT / ".cache" / "smartisan"
CATEGORY_URL = (
    "https://raw.githubusercontent.com/Sunbelife/get_smartisan_icon_pack/"
    "master/apps_category.json"
)
INFO_URL = "https://icon.smartisan.com/info/{package}/icon_provided_by_smartisan.xml"
DRAWABLE_URL = "https://icon.smartisan.com/drawable/{package}/icon_provided_by_smartisan.png"
YYB_URL = "https://sj.qq.com/appdetail/{package}"
USER_AGENT = "OneWidgetAppIcons-smartisan/1.0"

# Packages the Chinese stores no longer list, whose public names are unambiguous.
KNOWN_IDENTITIES = {
    "com.facebook.katana": ("Facebook", "application"),
    "com.google.android.youtube": ("YouTube", "application"),
    "com.happyelements.AndroidAnimal": ("开心消消乐", "game"),
    "com.hulu.plus": ("Hulu", "application"),
    "com.instagram.android": ("Instagram", "application"),
    "com.king.candycrushsaga": ("Candy Crush Saga", "game"),
    "com.mojang.minecraftpe": ("Minecraft", "game"),
    "com.netflix.mediaclient": ("Netflix", "application"),
    "com.spotify.music": ("Spotify", "application"),
    "com.whatsapp": ("WhatsApp", "application"),
    "com.unionpay.chsp": ("云闪付", "application"),
}

# Current apps and games that post-date the 2020 package index.
EXTRA_PACKAGES = (
    "com.ss.android.ugc.aweme",
    "com.ss.android.ugc.aweme.lite",
    "com.ss.android.ugc.live",
    "com.ss.android.article.news",
    "com.ss.android.article.lite",
    "com.ss.android.article.video",
    "com.ss.android.lark",
    "com.xunmeng.pinduoduo",
    "com.kuaishou.nebula",
    "com.xingin.xhs",
    "com.dragon.read",
    "com.phoenix.read",
    "com.xs.fm",
    "com.luna.music",
    "com.kmxs.reader",
    "com.tencent.qqlive",
    "com.qiyi.video",
    "com.youku.phone",
    "com.hunantv.imgo.activity",
    "com.cctv.yangshipin",
    "com.lemon.lv",
    "com.xt.retouch",
    "com.meitu.meiyancamera",
    "com.mt.mtxx.mtxx",
    "com.tencent.weread",
    "com.qidian.QDReader",
    "com.alibaba.android.rimet",
    "com.tencent.wework",
    "com.sankuai.meituan.takeoutnew",
    "me.ele",
    "com.taobao.idlefish",
    "com.tmall.wireless",
    "com.achievo.vipshop",
    "com.sdu.didi.psnger",
    "com.jingyao.easybike",
    "ctrip.android.view",
    "com.Qunar",
    "com.MobileTicket",
    "com.greenpoint.android.mc10086.activity",
    "com.sinovatech.unicom.ui",
    "com.ct.client",
    "com.icbc",
    "com.chinamworld.main",
    "com.android.bankabc",
    "cmb.pb",
    "com.unionpay",
    "com.tencent.mm",
    "com.tencent.mobileqq",
    "com.eg.android.AlipayGphone",
    "com.taobao.taobao",
    "com.jingdong.app.mall",
    "com.sankuai.meituan",
    "com.dianping.v1",
    "com.baidu.searchbox",
    "com.autonavi.minimap",
    "com.baidu.BaiduMap",
    "com.tencent.map",
    "com.netease.cloudmusic",
    "com.tencent.qqmusic",
    "com.kugou.android",
    "com.ximalaya.ting.android",
    "tv.danmaku.bili",
    "com.sina.weibo",
    "com.zhihu.android",
    "com.douban.frodo",
    "com.smile.gifmaker",
    "com.baidu.netdisk",
    "com.tencent.mtt",
    "com.UCMobile",
    "com.youdao.dict",
    "com.baidu.input",
    "com.sohu.inputmethod.sogou",
    "com.iflytek.inputmethod",
    "com.wuba",
    "com.anjuke.android.app",
    "com.homelink.android",
    "com.chaoxing.mobile",
    "com.xueersi.parentsmeeting",
    "com.baidu.homework",
    "com.duolingo",
    "com.tencent.tmgp.sgame",
    "com.tencent.tmgp.pubgmhd",
    "com.tencent.tmgp.speedmobile",
    "com.tencent.tmgp.cf",
    "com.tencent.jkchess",
    "com.tencent.lolm",
    "com.tencent.mf.uam",
    "com.netease.my",
    "com.netease.dwrg",
    "com.netease.onmyoji",
    "com.netease.mrzh",
    "com.netease.party",
    "com.netease.sky",
    "com.miHoYo.Yuanshen",
    "com.miHoYo.hkrpg",
    "com.miHoYo.Nap",
    "com.papegames.nn4",
    "com.hypergryph.arknights",
    "com.lilithgames.hgame.cn",
    "com.supercell.clashofclans",
    "com.supercell.clashroyale",
    "com.supercell.brawlstars",
    "com.king.candycrushsaga",
    "com.kiloo.subwaysurf",
    "com.mojang.minecraftpe",
    "com.roblox.client",
    "com.innersloth.spacemafia",
    "com.dts.freefireth",
    "com.riotgames.league.wildrift",
    "com.happyelements.AndroidAnimal",
    "com.outfit7.mytalkingtom2",
    "com.openai.chatgpt",
    "com.deepseek.chat",
    "com.moonshot.kimichat",
    "com.aliyun.tongyi",
    "com.baidu.newapp",
    "com.zhipu.chatglm",
    "com.instagram.android",
    "com.facebook.katana",
    "com.whatsapp",
    "com.spotify.music",
    "com.netflix.mediaclient",
    "com.google.android.youtube",
    "com.zhiliaoapp.musically",
    "com.discord",
    "org.telegram.messenger",
)

CSV_FIELDS = (
    "androidPackage",
    "name",
    "nameSource",
    "kind",
    "smartisanCategoryId",
    "yybCategory",
    "image",
    "width",
    "height",
    "md5",
    "smartisanUpdatedAt",
    "appleAppStoreId",
    "appleBundleId",
    "appleName",
    "appleStatus",
    "unifiedId",
    "inCatalog",
)


def parse_info_xml(text):
    """Read the small metadata document the icon server returns for one package."""
    root = ElementTree.fromstring(text)
    package = (root.findtext("package") or "").strip()
    md5 = (root.findtext("md5") or "").strip().lower()
    updated = (root.findtext("last_update_time") or "").strip()
    if not package or not re.fullmatch(r"[0-9a-f]{32}", md5):
        raise ValueError(f"Icon info is missing package or md5: {package!r}")
    return {"package": package, "md5": md5, "updatedAt": updated}


def apple_id_from_url(url):
    """Pull a numeric App Store id out of an iTunes or Apple URL."""
    if not url:
        return None
    match = re.search(r"(?:/id|id=)(\d{5,})", str(url))
    if match is None:
        match = re.search(r"\bid(\d{5,})\b", str(url))
    return match.group(1) if match else None


def parse_yyb_page(html, package):
    """Read the display name and optional Apple id from an 应用宝 detail page."""
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if match is None:
        return None
    data = json.loads(match.group(1))
    found = []

    def walk(value):
        if isinstance(value, dict):
            if value.get("pkg_name") == package and value.get("name"):
                found.append(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    if not found:
        return None
    found.sort(
        key=lambda item: (
            bool(item.get("ios_url")),
            bool(item.get("cate_name_new") or item.get("cate_name")),
            len(item),
        ),
        reverse=True,
    )
    item = found[0]
    is_game = str(item.get("is_game")) == "1"
    category = item.get("cate_name_new") or item.get("cate_name") or None
    return {
        "name": str(item["name"]).strip(),
        "developer": (item.get("developer") or None),
        "category": category,
        "isGame": is_game,
        "appleAppStoreId": apple_id_from_url(item.get("ios_url") or ""),
    }


def png_size(data):
    """Return width and height when ``data`` is a PNG."""
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Icon is not a PNG")
    return struct.unpack(">II", data[16:24])


def icon_filename(package):
    """Keep the package name as the file name when it is safe to do so."""
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,180}", package):
        return f"{package}.png"
    digest = hashlib.sha256(package.encode("utf-8")).hexdigest()[:16]
    return f"pkg-{digest}.png"


def load_catalog_packages(root):
    """Apple bundle IDs already in the chart lists, used as extra icon probes."""
    packages = []
    for name in ("apps.json", "games.json"):
        path = root / "metadata" / name
        if not path.is_file():
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        for app in document["apps"]:
            bundle = app["platforms"]["apple"]["bundleId"]
            if bundle:
                packages.append(bundle)
    return packages


def load_catalog_index(root):
    """Index chart apps by Apple bundle id, store id, and Android package."""
    by_bundle = {}
    by_store = {}
    by_android = {}
    for name in ("apps.json", "games.json"):
        path = root / "metadata" / name
        if not path.is_file():
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        for app in document["apps"]:
            by_bundle.setdefault(app["platforms"]["apple"]["bundleId"], app)
            by_store.setdefault(app["platforms"]["apple"]["appStoreId"], app)
            android = app["platforms"]["android"]["packageName"]
            if android:
                by_android.setdefault(android, app)
    return by_bundle, by_store, by_android


def category_kind_map(entries):
    """Categories whose named icons are entirely apps or entirely games.

    A category needs at least two named icons. Categories 28 and 112 only have
    one named game each (王者荣耀, 纪念碑谷) and no named apps, so they are
    treated as games as well.
    """
    votes = {}
    for entry in entries:
        category = entry.get("smartisanCategoryId")
        if not category or entry.get("kind") == "unknown":
            continue
        votes.setdefault(category, {"application": 0, "game": 0})
        if entry["kind"] in votes[category]:
            votes[category][entry["kind"]] += 1
    decided = {}
    for category, counts in votes.items():
        if counts["game"] >= 2 and counts["application"] == 0:
            decided[category] = "game"
        elif counts["application"] >= 2 and counts["game"] == 0:
            decided[category] = "application"
    for category in ("28", "112"):
        counts = votes.get(category, {})
        if counts.get("game") and not counts.get("application"):
            decided[category] = "game"
    return decided


def apply_known_names(entries):
    """Fill a few public names the Chinese stores no longer return."""
    for entry in entries:
        known = KNOWN_IDENTITIES.get(entry["androidPackage"])
        if not known:
            continue
        name, kind = known
        if not entry.get("name"):
            entry["name"] = name
            entry["nameSource"] = "known"
        if entry.get("kind") == "unknown":
            entry["kind"] = kind


def apply_category_kinds(entries):
    """Fill unknown kinds from categories that are consistently apps or games."""
    decided = category_kind_map(entries)
    for entry in entries:
        if entry.get("kind") == "unknown":
            kind = decided.get(entry.get("smartisanCategoryId"))
            if kind:
                entry["kind"] = kind
    return decided


def game_categories(rows):
    """Categories where 应用宝 calls at least 80 percent of named icons games."""
    votes = {}
    for row in rows:
        category = row.get("smartisanCategoryId")
        yyb = row.get("yyb")
        if not category or not yyb:
            continue
        apps, games = votes.setdefault(category, [0, 0])
        if yyb["isGame"]:
            votes[category][1] = games + 1
        else:
            votes[category][0] = apps + 1
    chosen = set()
    for category, (apps, games) in votes.items():
        total = apps + games
        if total >= 5 and games / total >= 0.8:
            chosen.add(category)
    return chosen


def build_entry(hit, yyb, apple, catalog_index, game_cats):
    """Combine one downloaded icon with its name and optional Apple match."""
    by_bundle, by_store, by_android = catalog_index
    apple = apple or {}
    store_id = (yyb or {}).get("appleAppStoreId") or apple.get("appStoreId")
    bundle_id = apple.get("bundleId")
    apple_name = apple.get("name")
    if yyb and yyb.get("name"):
        name = yyb["name"]
        name_source = "yyb"
    elif apple_name:
        name = apple_name
        name_source = "apple"
    else:
        name = None
        name_source = None
    if yyb is not None:
        kind = "game" if yyb["isGame"] else "application"
    elif hit.get("smartisanCategoryId") in game_cats:
        kind = "game"
    else:
        kind = "unknown"
    if store_id or bundle_id:
        apple_status = "matched" if bundle_id else "store_id_only"
    else:
        apple_status = "unmatched"
    linked = (
        by_android.get(hit["package"])
        or (by_bundle.get(bundle_id) if bundle_id else None)
        or (by_store.get(store_id) if store_id else None)
    )
    return {
        "androidPackage": hit["package"],
        "name": name,
        "nameSource": name_source,
        "developer": (yyb or {}).get("developer"),
        "kind": kind,
        "smartisanCategoryId": hit.get("smartisanCategoryId"),
        "yybCategory": (yyb or {}).get("category"),
        "image": f"smartisan/icons/{hit['filename']}",
        "width": hit["width"],
        "height": hit["height"],
        "md5": hit["md5"],
        "sha256": hit["sha256"],
        "smartisanUpdatedAt": hit["updatedAt"],
        "sourceUrl": DRAWABLE_URL.format(package=urllib.parse.quote(hit["package"], safe="")),
        "appleAppStoreId": store_id,
        "appleBundleId": bundle_id,
        "appleName": apple_name,
        "appleStatus": apple_status,
        "unifiedId": linked["id"] if linked else None,
        "inCatalog": linked is not None,
    }


def write_catalog(entries, captured_at):
    """Write the JSON catalog and the app and game CSV lists."""
    entries = sorted(
        entries,
        key=lambda item: (
            {"application": 0, "game": 1, "unknown": 2}[item["kind"]],
            0 if item["name"] else 1,
            item["name"] or "",
            item["androidPackage"].lower(),
        ),
    )
    document = {
        "schemaVersion": 1,
        "capturedAt": captured_at,
        "source": "https://icon.smartisan.com/drawable/{package}/icon_provided_by_smartisan.png",
        "nameSource": "https://sj.qq.com/appdetail/{package}",
        "note": (
            "这些图是锤子官方图标接口仍在提供的 Smartisan OS 图标，不是 "
            "styles/smartisan/ 里的重绘结果。name 优先用应用宝上的名字，"
            "应用宝没有时再用酷安仍在收录的名字。appleStatus 为 matched 时已经用 "
            "iTunes Lookup 核对过 bundle ID；store_id_only 只有应用宝给出的 "
            "App Store 数字 ID；unmatched 还没有对上苹果应用，保留 Android 包名和已知名字，供以后核对。"
            "没有名字的旧包只保留包名。kind 在应用宝或酷安没有标明时，按同一锤子分类里"
            "已经标明的应用或游戏补上。"
        ),
        "counts": {
            "icons": len(entries),
            "named": sum(1 for item in entries if item["name"]),
            "applications": sum(1 for item in entries if item["kind"] == "application"),
            "games": sum(1 for item in entries if item["kind"] == "game"),
            "unknownKind": sum(1 for item in entries if item["kind"] == "unknown"),
            "appleMatched": sum(1 for item in entries if item["appleStatus"] == "matched"),
            "appleStoreIdOnly": sum(1 for item in entries if item["appleStatus"] == "store_id_only"),
            "appleUnmatched": sum(1 for item in entries if item["appleStatus"] == "unmatched"),
            "inCatalog": sum(1 for item in entries if item["inCatalog"]),
        },
        "icons": entries,
    }
    ICON_ROOT.mkdir(parents=True, exist_ok=True)
    (ICON_ROOT / "catalog.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for kind, filename in (("application", "apps.csv"), ("game", "games.csv")):
        rows = [item for item in entries if item["kind"] == kind]
        _write_csv(ICON_ROOT / filename, rows)
    unknown = [item for item in entries if item["kind"] == "unknown"]
    if unknown:
        _write_csv(ICON_ROOT / "unknown.csv", unknown)
    elif (ICON_ROOT / "unknown.csv").exists():
        (ICON_ROOT / "unknown.csv").unlink()
    return document


def _write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _fetch(url, timeout=25, attempts=3):
    last_error = None
    for attempt in range(attempts):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code in {404, 410}:
                raise
            last_error = error
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
        time.sleep(attempt + 1)
    raise last_error


def _quote_package(package):
    return urllib.parse.quote(package, safe="")


def probe_package(package, category):
    url = INFO_URL.format(package=_quote_package(package))
    try:
        payload = _fetch(url, timeout=8, attempts=2)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    info = parse_info_xml(payload.decode("utf-8"))
    if info["package"] != package:
        raise ValueError(f"Icon info package {info['package']!r} != {package!r}")
    info["smartisanCategoryId"] = category
    info["filename"] = icon_filename(package)
    return info


def download_icon(info):
    url = DRAWABLE_URL.format(package=_quote_package(info["package"]))
    payload = _fetch(url, timeout=30)
    digest = hashlib.md5(payload).hexdigest()
    if digest != info["md5"]:
        raise ValueError(f"MD5 mismatch for {info['package']}: {digest} != {info['md5']}")
    width, height = png_size(payload)
    path = ICON_DIR / info["filename"]
    path.write_bytes(payload)
    info["width"] = width
    info["height"] = height
    info["sha256"] = hashlib.sha256(payload).hexdigest()
    return info


def parse_coolapk_detail(payload, package):
    """Read a display name from a Coolapk detail response."""
    data = payload if isinstance(payload, dict) else json.loads(payload)
    item = data.get("data")
    if data.get("status") == -2 or not isinstance(item, dict):
        return None
    if item.get("apkname") and item.get("apkname") != package:
        return None
    title = str(item.get("title") or "").strip()
    if not title:
        return None
    if item.get("apktype") == 2 or item.get("apkTypeName") == "游戏":
        kind = "game"
    elif item.get("apktype") == 1:
        kind = "application"
    else:
        kind = None
    return {
        "name": title,
        "developer": item.get("developername") or None,
        "category": item.get("catName") or None,
        "kind": kind,
    }


def coolapk_token(device_code):
    """Build the X-App-Token Coolapk expects. Requires the bcrypt package."""
    import bcrypt

    timestamp = str(int(time.time()))
    md5_timestamp = hashlib.md5(timestamp.encode("utf-8")).hexdigest()
    md5_device = hashlib.md5(device_code.encode("utf-8")).hexdigest()
    token = (
        "token://com.coolapk.market/dcf01e569c1e3db93a3d0fcf191a622c?"
        f"{md5_timestamp}${md5_device}&com.coolapk.market"
    )
    md5_token = hashlib.md5(token.encode("utf-8")).hexdigest()
    base64_token = base64.b64encode(token.encode("utf-8")).decode("ascii")
    md5_base64_token = hashlib.md5(base64_token.encode("utf-8")).hexdigest()
    base64_timestamp = base64.b64encode(timestamp.encode("utf-8")).decode("ascii")
    salt = f"$2a$10${base64_timestamp[:14]}/{md5_token[:6]}u"
    hashed = bcrypt.hashpw(md5_base64_token.encode("utf-8"), salt.encode("utf-8")).decode("ascii")
    rewritten = "$2y" + hashed[3:]
    return "v2" + base64.b64encode(rewritten.encode("utf-8")).decode("ascii")


def fetch_coolapk(package, device_code):
    url = "https://api2.coolapk.com/v6/apk/detail?id=" + _quote_package(package)
    request = urllib.request.Request(url, headers={
        "User-Agent": (
            "Dalvik/2.1.0 (Linux; U; Android 9; MI 8 SE MIUI/9.5.9) "
            "(#Build; Xiaomi; MI 8 SE; PKQ1.181121.001; 9) +CoolMarket/12.4.2-2208241-universal"
        ),
        "X-App-Id": "com.coolapk.market",
        "X-Requested-With": "XMLHttpRequest",
        "X-Sdk-Int": "30",
        "X-App-Mode": "universal",
        "X-App-Channel": "coolapk",
        "X-Sdk-Locale": "zh-CN",
        "X-App-Version": "12.4.2",
        "X-Api-Supported": "2208241",
        "X-App-Code": "2208241",
        "X-Api-Version": "12",
        "X-App-Device": device_code,
        "X-Dark-Mode": "0",
        "X-App-Token": coolapk_token(device_code),
    })
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read()
    except urllib.error.HTTPError as error:
        if error.code in {404, 410}:
            return None
        raise
    return parse_coolapk_detail(payload.decode("utf-8"), package)


def fetch_yyb(package):
    url = YYB_URL.format(package=_quote_package(package))
    try:
        payload = _fetch(url, timeout=30)
    except urllib.error.HTTPError as error:
        if error.code in {404, 410}:
            return None
        raise
    return parse_yyb_page(payload.decode("utf-8", "replace"), package)


def lookup_apple_ids(store_ids):
    """Batch iTunes Lookup by numeric App Store id. Returns id -> result."""
    found = {}
    pending = sorted(set(store_ids))
    for country in ("cn", "us"):
        still_missing = []
        for start in range(0, len(pending), 150):
            chunk = pending[start:start + 150]
            url = f"https://itunes.apple.com/lookup?country={country}&id=" + ",".join(chunk)
            payload = _fetch(url, timeout=40)
            body = json.loads(payload.decode("utf-8"))
            returned = set()
            for result in body.get("results", []):
                store_id = str(result.get("trackId") or "")
                bundle = result.get("bundleId")
                if store_id and bundle:
                    returned.add(store_id)
                    found.setdefault(store_id, {
                        "appStoreId": store_id,
                        "bundleId": bundle,
                        "name": result.get("trackName"),
                        "developer": result.get("artistName"),
                    })
            still_missing.extend(store_id for store_id in chunk if store_id not in returned)
            time.sleep(0.2)
        pending = still_missing
        if not pending:
            break
    return found


def lookup_apple_bundle(package):
    url = "https://itunes.apple.com/lookup?country=cn&bundleId=" + _quote_package(package)
    payload = _fetch(url, timeout=30)
    body = json.loads(payload.decode("utf-8"))
    results = body.get("results") or []
    if len(results) != 1 or not results[0].get("bundleId"):
        return None
    result = results[0]
    if result["bundleId"] != package:
        return None
    return {
        "appStoreId": str(result["trackId"]),
        "bundleId": result["bundleId"],
        "name": result.get("trackName"),
        "developer": result.get("artistName"),
    }


def _run_pool(items, worker, workers, label):
    results = []
    errors = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(worker, item): item for item in items}
        for future in as_completed(futures):
            done += 1
            item = futures[future]
            try:
                results.append(future.result())
            except Exception as error:
                if isinstance(item, str):
                    name = item
                elif isinstance(item, dict):
                    name = item.get("package")
                elif isinstance(item, tuple):
                    name = item[0]
                else:
                    name = item
                errors.append(f"{name}: {error}")
            if done % 500 == 0 or done == len(items):
                print(f"{label} {done}/{len(items)}", flush=True)
    return results, errors


def collect(root):
    """Probe the icon server, download hits, and write the smartisan catalog."""
    CACHE.mkdir(parents=True, exist_ok=True)
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading package index", flush=True)
    categories = json.loads(_fetch(CATEGORY_URL, timeout=60).decode("utf-8"))
    packages = dict(categories)
    for package in load_catalog_packages(root):
        packages.setdefault(package, None)
    for package in EXTRA_PACKAGES:
        packages.setdefault(package, None)
    print(f"Probing {len(packages)} packages", flush=True)
    progress_path = CACHE / "probe-progress.json"
    if progress_path.is_file():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
    else:
        progress = {"done": [], "hits": [], "errors": []}
    done = set(progress["done"])
    hits = list(progress["hits"])
    probe_errors = list(progress["errors"])
    items = [(package, category) for package, category in packages.items() if package not in done]
    print(f"Remaining probes: {len(items)}; already done: {len(done)}", flush=True)

    def probe(item):
        package, category = item
        return probe_package(package, category)

    chunk_size = 250
    for offset in range(0, len(items), chunk_size):
        chunk = items[offset:offset + chunk_size]
        probed, errors = _run_pool(chunk, probe, 8, "probe")
        # The whole chunk is marked done. Recorded errors are not retried.
        for result in probed:
            if result:
                hits.append(result)
        probe_errors.extend(errors)
        done.update(package for package, _category in chunk)
        progress = {"done": sorted(done), "hits": hits, "errors": probe_errors}
        progress_path.write_text(json.dumps(progress, ensure_ascii=False) + "\n", encoding="utf-8")
        print(
            f"probe checkpoint {len(done)}/{len(packages)} hits {len(hits)} errors {len(probe_errors)}",
            flush=True,
        )
    filenames = {}
    unique_hits = []
    for hit in hits:
        previous = filenames.get(hit["filename"])
        if previous:
            probe_errors.append(f"{hit['package']}: filename collision with {previous}")
            continue
        filenames[hit["filename"]] = hit["package"]
        unique_hits.append(hit)
    hits = unique_hits
    print(f"Icons available: {len(hits)}; probe errors: {len(probe_errors)}", flush=True)
    (CACHE / "hits.json").write_text(
        json.dumps(hits, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    downloaded, download_errors = _run_pool(hits, download_icon, 8, "download")
    downloaded = [item for item in downloaded if item]
    print(f"Downloaded {len(downloaded)}; download errors: {len(download_errors)}", flush=True)

    def yyb_worker(info):
        return info["package"], fetch_yyb(info["package"])

    yyb_rows, yyb_errors = _run_pool(downloaded, yyb_worker, 8, "names")
    yyb_by_package = {package: record for package, record in yyb_rows if package}
    store_ids = [
        record["appleAppStoreId"]
        for record in yyb_by_package.values()
        if record and record.get("appleAppStoreId")
    ]
    print(f"Looking up {len(set(store_ids))} Apple ids", flush=True)
    apple_by_id = lookup_apple_ids(store_ids) if store_ids else {}

    bundle_matches = {}
    missing_apple = [
        info["package"]
        for info in downloaded
        if not ((yyb_by_package.get(info["package"]) or {}).get("appleAppStoreId"))
    ]

    def bundle_worker(package):
        return package, lookup_apple_bundle(package)

    bundle_rows, bundle_errors = _run_pool(missing_apple, bundle_worker, 8, "bundle-lookup")
    for package, record in bundle_rows:
        if record:
            bundle_matches[package] = record

    provisional = []
    for info in downloaded:
        yyb = yyb_by_package.get(info["package"])
        provisional.append({"smartisanCategoryId": info.get("smartisanCategoryId"), "yyb": yyb})
    game_cats = game_categories(provisional)
    catalog_index = load_catalog_index(root)
    entries = []
    for info in downloaded:
        yyb = yyb_by_package.get(info["package"])
        apple = None
        if yyb and yyb.get("appleAppStoreId"):
            apple = apple_by_id.get(yyb["appleAppStoreId"])
        if apple is None:
            apple = bundle_matches.get(info["package"])
        entries.append(build_entry(info, yyb, apple, catalog_index, game_cats))
    apply_known_names(entries)
    apply_category_kinds(entries)
    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    document = write_catalog(entries, captured_at)
    error_log = {
        "probe": probe_errors,
        "download": download_errors,
        "yyb": yyb_errors,
        "bundle": bundle_errors,
        "gameCategories": sorted(game_cats),
    }
    (CACHE / "errors.json").write_text(
        json.dumps(error_log, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(document["counts"], ensure_ascii=False), flush=True)
    print(f"Game categories inferred: {sorted(game_cats)}", flush=True)
    if probe_errors or download_errors:
        print(f"Finished with {len(probe_errors)} probe errors and {len(download_errors)} download errors", flush=True)
    return document


def fill_names():
    """Fill icons that 应用宝 did not name, using Coolapk when the app is still listed."""
    document = json.loads((ICON_ROOT / "catalog.json").read_text(encoding="utf-8"))
    missing = [entry for entry in document["icons"] if not entry.get("name")]
    print(f"Coolapk lookup for {len(missing)} unnamed icons", flush=True)
    device_code = base64.b64encode(
        b"A1B2C3D4E5F60718; ; ; 02:11:22:33:44:55; Xiaomi; Xiaomi; MI 8 SE; PKQ1.181121.001"
    ).decode("ascii")

    def worker(entry):
        return entry["androidPackage"], fetch_coolapk(entry["androidPackage"], device_code)

    rows, errors = _run_pool(missing, worker, 4, "coolapk")
    found = {package: record for package, record in rows if record}
    for entry in document["icons"]:
        record = found.get(entry["androidPackage"])
        if not record:
            continue
        entry["name"] = record["name"]
        entry["nameSource"] = "coolapk"
        if not entry.get("developer"):
            entry["developer"] = record["developer"]
        if not entry.get("yybCategory"):
            entry["yybCategory"] = record["category"]
        if entry["kind"] == "unknown" and record["kind"]:
            entry["kind"] = record["kind"]
    apply_known_names(document["icons"])
    apply_category_kinds(document["icons"])
    updated = write_catalog(document["icons"], document["capturedAt"])
    print(json.dumps(updated["counts"], ensure_ascii=False), flush=True)
    print(f"Coolapk filled {len(found)}; errors {len(errors)}", flush=True)
    if errors:
        print("\n".join(errors[:20]), flush=True)
    return updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--fill-names", action="store_true",
                        help="Look up names Coolapk still lists, without downloading icons again")
    args = parser.parse_args()
    try:
        if args.fill_names:
            fill_names()
        else:
            collect(args.root)
    except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
