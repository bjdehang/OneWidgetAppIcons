"""Parsers and catalog rows for the collected Smartisan icon library."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collect_smartisan_icons import (  # noqa: E402
    apple_id_from_url,
    build_entry,
    apply_category_kinds,
    apply_known_names,
    game_categories,
    assign_style_ids,
    place_style_files,
    style_icon_identity,
    icon_filename,
    parse_coolapk_detail,
    parse_info_xml,
    parse_yyb_page,
    png_size,
)


INFO_XML = """<?xml version='1.0' encoding='utf-8'?>
<info>
  <package>com.tencent.mm</package>
  <file>icon_provided_by_smartisan.png</file>
  <md5>3afcc2ebdb2af74056016539a9e5a002</md5>
  <last_update_time>2014-12-16 16:44:43</last_update_time>
</info>
"""

YYB_PAGE = """
<script id="__NEXT_DATA__" type="application/json" crossorigin="anonymous">
{"props":{"pageProps":{"dynamicCardResponse":{"data":{"components":[
  {"data":{"itemData":[
    {"pkg_name":"com.tencent.android.qqdownloader","name":"应用宝","is_game":"0"},
    {"pkg_name":"com.tencent.mm","name":"微信","developer":"深圳市腾讯计算机系统有限公司",
     "is_game":"0","cate_name":"社交","ios_url":"https://itunes.apple.com/cn/app/id414478124"}
  ]}}
]}}}}}
</script>
"""


class SmartisanIconTests(unittest.TestCase):
    def test_parse_info_xml(self):
        info = parse_info_xml(INFO_XML)
        self.assertEqual(info["package"], "com.tencent.mm")
        self.assertEqual(info["md5"], "3afcc2ebdb2af74056016539a9e5a002")
        self.assertEqual(info["updatedAt"], "2014-12-16 16:44:43")

    def test_apple_id_from_url(self):
        self.assertEqual(apple_id_from_url("https://itunes.apple.com/cn/app/id414478124"), "414478124")
        self.assertEqual(apple_id_from_url("https://apps.apple.com/app/id1527355884"), "1527355884")
        self.assertIsNone(apple_id_from_url(""))
        self.assertIsNone(apple_id_from_url("https://example.com/no-id"))

    def test_parse_yyb_page_picks_the_requested_package(self):
        record = parse_yyb_page(YYB_PAGE, "com.tencent.mm")
        self.assertEqual(record["name"], "微信")
        self.assertFalse(record["isGame"])
        self.assertEqual(record["category"], "社交")
        self.assertEqual(record["appleAppStoreId"], "414478124")
        self.assertIsNone(parse_yyb_page(YYB_PAGE, "com.missing.app"))

    def test_png_size_and_filename(self):
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct_wh(192, 192)
        self.assertEqual(png_size(data), (192, 192))
        self.assertEqual(icon_filename("com.tencent.mm"), "com.tencent.mm.png")
        self.assertTrue(icon_filename("bad/name").startswith("pkg-"))

    def test_build_entry_keeps_unmatched_package(self):
        hit = {
            "package": "com.example.oldgame",
            "filename": "com.example.oldgame.png",
            "smartisanCategoryId": "27",
            "md5": "a" * 32,
            "sha256": "b" * 64,
            "updatedAt": "2016-01-01 00:00:00",
            "width": 192,
            "height": 192,
        }
        entry = build_entry(hit, None, None, ({}, {}, {}), {"27"})
        self.assertEqual(entry["kind"], "game")
        self.assertIsNone(entry["name"])
        self.assertEqual(entry["appleStatus"], "unmatched")
        self.assertFalse(entry["inCatalog"])
        self.assertEqual(entry["androidPackage"], "com.example.oldgame")

    def test_build_entry_links_catalog_and_apple_lookup(self):
        hit = {
            "package": "com.tencent.mm",
            "filename": "com.tencent.mm.png",
            "smartisanCategoryId": "41",
            "md5": "a" * 32,
            "sha256": "b" * 64,
            "updatedAt": "2014-12-16 16:44:43",
            "width": 192,
            "height": 192,
        }
        yyb = {
            "name": "微信",
            "developer": "Tencent",
            "category": "社交",
            "isGame": False,
            "appleAppStoreId": "414478124",
        }
        apple = {"appStoreId": "414478124", "bundleId": "com.tencent.xin", "name": "微信"}
        catalog = (
            {"com.tencent.xin": {"id": "com_tencent_xin"}},
            {"414478124": {"id": "com_tencent_xin"}},
            {},
        )
        entry = build_entry(hit, yyb, apple, catalog, set())
        self.assertEqual(entry["name"], "微信")
        self.assertEqual(entry["nameSource"], "yyb")
        self.assertEqual(entry["kind"], "application")
        self.assertEqual(entry["appleStatus"], "matched")
        self.assertEqual(entry["appleBundleId"], "com.tencent.xin")
        self.assertEqual(entry["unifiedId"], "com_tencent_xin")
        self.assertTrue(entry["inCatalog"])

    def test_parse_coolapk_detail(self):
        listed = {
            "data": {
                "apkname": "com.tencent.tmgp.sgame",
                "title": "王者荣耀",
                "apktype": 2,
                "apkTypeName": "游戏",
                "catName": "掌上网游",
                "developername": "深圳市腾讯计算机系统有限公司",
            }
        }
        record = parse_coolapk_detail(listed, "com.tencent.tmgp.sgame")
        self.assertEqual(record["name"], "王者荣耀")
        self.assertEqual(record["kind"], "game")
        self.assertIsNone(parse_coolapk_detail({"status": -2, "message": "应用已下架"}, "com.durex"))
        self.assertIsNone(parse_coolapk_detail(listed, "com.other.app"))

    def test_style_icon_identity_uses_the_apple_bundle(self):
        apple = style_icon_identity({
            "androidPackage": "com.tencent.mm",
            "appleBundleId": "com.tencent.xin",
        })
        self.assertEqual(apple, ("com_tencent_xin", "apple"))
        android = style_icon_identity({"androidPackage": "com.example.oldgame", "appleBundleId": None})
        self.assertEqual(android, ("com_example_oldgame", "android"))

    def test_assign_style_ids_shares_one_file_when_packages_match_one_apple_bundle(self):
        entries = [
            {
                "androidPackage": "com.tencent.mm",
                "appleBundleId": "com.tencent.xin",
                "name": "微信",
                "inCatalog": True,
                "unifiedId": "com_tencent_xin",
                "image": "smartisan/icons/com.tencent.mm.png",
            },
            {
                "androidPackage": "com.unionpay",
                "appleBundleId": "com.unionpay.chsp",
                "name": "云闪付",
                "inCatalog": True,
                "unifiedId": "com_unionpay_chsp",
                "image": "smartisan/icons/com.unionpay.png",
            },
            {
                "androidPackage": "com.unionpay.chsp",
                "appleBundleId": None,
                "name": "云闪付",
                "inCatalog": False,
                "unifiedId": None,
                "image": "smartisan/icons/com.unionpay.chsp.png",
            },
            {
                "androidPackage": "com.foo bar",
                "appleBundleId": None,
                "name": None,
                "inCatalog": False,
                "unifiedId": None,
                "image": "smartisan/icons/com.foo bar.png",
            },
            {
                "androidPackage": "com.other",
                "appleBundleId": "com.foo.bar",
                "name": "Foo",
                "inCatalog": False,
                "unifiedId": None,
                "image": "smartisan/icons/com.other.png",
            },
        ]
        assign_style_ids(entries)
        self.assertEqual(entries[0]["id"], "com_tencent_xin")
        self.assertEqual(entries[0]["image"], "styles/smartisan/com_tencent_xin.png")
        self.assertEqual(entries[1]["id"], "com_unionpay_chsp")
        self.assertEqual(entries[2]["id"], "com_unionpay_chsp")
        self.assertEqual(entries[2]["idSource"], "apple")
        self.assertEqual(entries[1]["image"], entries[2]["image"])
        self.assertEqual(entries[3]["id"], "com_foo_bar_android")
        self.assertEqual(entries[3]["idSource"], "android")
        self.assertEqual(entries[4]["id"], "com_foo_bar")
        self.assertEqual(entries[4]["image"], "styles/smartisan/com_foo_bar.png")

    def test_place_style_files_keeps_one_png_per_unified_id(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "smartisan" / "icons"
            source_dir.mkdir(parents=True)
            (source_dir / "com.tencent.mm.png").write_bytes(b"wechat")
            (source_dir / "com.unionpay.png").write_bytes(b"old-unionpay")
            (source_dir / "com.unionpay.chsp.png").write_bytes(b"kept-unionpay")
            entries = [
                {
                    "androidPackage": "com.tencent.mm",
                    "appleBundleId": "com.tencent.xin",
                    "name": "微信",
                    "inCatalog": True,
                    "unifiedId": "com_tencent_xin",
                    "image": "smartisan/icons/com.tencent.mm.png",
                    "width": 1, "height": 1, "md5": "a", "sha256": "a",
                    "sourceUrl": "https://example.test/mm",
                },
                {
                    "androidPackage": "com.unionpay",
                    "appleBundleId": "com.unionpay.chsp",
                    "name": "云闪付",
                    "inCatalog": True,
                    "unifiedId": "com_unionpay_chsp",
                    "image": "smartisan/icons/com.unionpay.png",
                    "width": 1, "height": 1, "md5": "b", "sha256": "b",
                    "sourceUrl": "https://example.test/unionpay",
                },
                {
                    "androidPackage": "com.unionpay.chsp",
                    "appleBundleId": "com.unionpay.chsp",
                    "name": "云闪付",
                    "inCatalog": False,
                    "unifiedId": None,
                    "image": "smartisan/icons/com.unionpay.chsp.png",
                    "width": 2, "height": 2, "md5": "c", "sha256": "c",
                    "sourceUrl": "https://example.test/chsp",
                },
            ]
            place_style_files(entries, root)
            self.assertEqual((root / "styles/smartisan/com_tencent_xin.png").read_bytes(), b"wechat")
            self.assertFalse((source_dir / "com.tencent.mm.png").exists())
            self.assertEqual((root / "styles/smartisan/com_unionpay_chsp.png").read_bytes(), b"kept-unionpay")
            self.assertFalse((source_dir / "com.unionpay.png").exists())
            self.assertEqual(entries[1]["md5"], "c")
            self.assertEqual(entries[1]["sourceUrl"], "https://example.test/chsp")
            self.assertEqual(entries[1]["image"], "styles/smartisan/com_unionpay_chsp.png")

    def test_apply_known_names_does_not_replace_a_store_name(self):
        entries = [{
            "androidPackage": "com.whatsapp",
            "name": None,
            "nameSource": None,
            "kind": "unknown",
        }, {
            "androidPackage": "com.unionpay.chsp",
            "name": "云闪付-银行业统一移动支付App",
            "nameSource": "yyb",
            "kind": "unknown",
        }]
        apply_known_names(entries)
        self.assertEqual(entries[0]["name"], "WhatsApp")
        self.assertEqual(entries[0]["nameSource"], "known")
        self.assertEqual(entries[0]["kind"], "application")
        self.assertEqual(entries[1]["name"], "云闪付-银行业统一移动支付App")
        self.assertEqual(entries[1]["nameSource"], "yyb")
        self.assertEqual(entries[1]["kind"], "application")

    def test_apply_category_kinds_uses_a_consistent_category(self):
        entries = [
            {"smartisanCategoryId": "36", "kind": "application"},
            {"smartisanCategoryId": "36", "kind": "application"},
            {"smartisanCategoryId": "36", "kind": "unknown"},
            {"smartisanCategoryId": "27", "kind": "game"},
            {"smartisanCategoryId": "27", "kind": "game"},
            {"smartisanCategoryId": "27", "kind": "unknown"},
            {"smartisanCategoryId": "41", "kind": "application"},
            {"smartisanCategoryId": "41", "kind": "game"},
            {"smartisanCategoryId": "41", "kind": "unknown"},
        ]
        decided = apply_category_kinds(entries)
        self.assertEqual(decided["36"], "application")
        self.assertEqual(decided["27"], "game")
        self.assertNotIn("41", decided)
        self.assertEqual([item["kind"] for item in entries], [
            "application", "application", "application",
            "game", "game", "game",
            "application", "game", "unknown",
        ])

    def test_game_categories_need_a_clear_majority(self):
        rows = [
            {"smartisanCategoryId": "27", "yyb": {"isGame": True}},
            {"smartisanCategoryId": "27", "yyb": {"isGame": True}},
            {"smartisanCategoryId": "27", "yyb": {"isGame": True}},
            {"smartisanCategoryId": "27", "yyb": {"isGame": True}},
            {"smartisanCategoryId": "27", "yyb": {"isGame": False}},
            {"smartisanCategoryId": "41", "yyb": {"isGame": False}},
            {"smartisanCategoryId": "41", "yyb": {"isGame": False}},
            {"smartisanCategoryId": "41", "yyb": {"isGame": False}},
            {"smartisanCategoryId": "41", "yyb": {"isGame": False}},
            {"smartisanCategoryId": "41", "yyb": {"isGame": False}},
        ]
        self.assertEqual(game_categories(rows), {"27"})


def struct_wh(width, height):
    import struct
    return struct.pack(">II", width, height)


if __name__ == "__main__":
    unittest.main()
