"""Chart rank selection, shared list fields, and the HTML preview."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from official_icons import union_entries  # noqa: E402
from preview_html import render_preview  # noqa: E402
from store_charts import (  # noqa: E402
    ENTRY_FIELDS,
    build_list,
    capture_lists,
    free_chart_ids,
    kind_from_genre,
    list_sort_key,
    merge_regions,
    take_ranks,
)
from unified_id import unified_id_from_bundle  # noqa: E402


def chart_payload(ids):
    return {
        "pageData": {
            "segmentedControl": {
                "segments": [{
                    "pageData": {
                        "topCharts": [
                            {"id": "30", "title": "Top Paid", "adamIds": ["9"]},
                            {"id": "27", "title": "Top Free", "adamIds": ids},
                        ]
                    }
                }]
            }
        }
    }


def lookup_result(store_id, bundle, name, genre_id, genre_name, artist_id="1"):
    return {
        "wrapperType": "software",
        "trackId": int(store_id),
        "trackName": name,
        "bundleId": bundle,
        "artistId": int(artist_id),
        "artistName": "Example",
        "primaryGenreId": genre_id,
        "primaryGenreName": genre_name,
    }


class ChartSelectionTests(unittest.TestCase):
    def test_free_chart_is_id_27_not_the_paid_chart(self):
        ids = free_chart_ids(chart_payload(["20", "21", "22"]))
        self.assertEqual(ids, ["20", "21", "22"])

    def test_repeated_chart_id_is_rejected(self):
        with self.assertRaises(ValueError):
            free_chart_ids(chart_payload(["20", "20"]))

    def test_requested_500_keeps_a_shorter_public_chart(self):
        ids = [str(number) for number in range(1, 211)]
        ranks = take_ranks(ids, 500)
        self.assertEqual(len(ranks), 210)
        self.assertEqual(ranks["1"], 1)
        self.assertEqual(ranks["210"], 210)

    def test_games_stop_at_200_when_the_chart_is_longer(self):
        ids = [str(number) for number in range(1, 211)]
        ranks = take_ranks(ids, 200)
        self.assertEqual(len(ranks), 200)
        self.assertNotIn("201", ranks)
        self.assertEqual(ranks["200"], 200)

    def test_kind_distinguishes_games_from_applications(self):
        self.assertEqual(kind_from_genre(6014, "Games"), "game")
        self.assertEqual(kind_from_genre(7012, "Puzzle"), "game")
        self.assertEqual(kind_from_genre("6024", "游戏"), "game")
        self.assertEqual(kind_from_genre(6005, "Social Networking"), "application")

    def test_region_union_keeps_a_blank_rank(self):
        rows = merge_regions({"1": 2, "2": 1}, {"2": 9, "3": 4})
        by_id = {row["appStoreId"]: row for row in rows}
        self.assertEqual(by_id["1"]["usRank"], None)
        self.assertEqual(by_id["3"]["cnRank"], None)
        self.assertEqual(by_id["2"]["cnRank"], 1)
        self.assertEqual(by_id["2"]["usRank"], 9)

    def test_sort_uses_the_better_regional_rank(self):
        us_only = {"name": "A", "id": "a", "cnRank": None, "usRank": 1}
        cn_lower = {"name": "B", "id": "b", "cnRank": 3, "usRank": None}
        self.assertLess(list_sort_key(us_only), list_sort_key(cn_lower))

    def test_entries_share_fields_and_record_both_ranks(self):
        lookups = {
            "10": lookup_result("10", "com.example.Game", "Blocks", 7012, "Puzzle"),
            "11": lookup_result("11", "com.example.App", "Notes", 6002, "Utilities"),
        }
        rows = [
            {"appStoreId": "10", "cnRank": 1, "usRank": None},
            {"appStoreId": "11", "cnRank": None, "usRank": 4},
        ]
        entries = build_list(rows, lookups, {})
        self.assertEqual(tuple(entries[0]), ENTRY_FIELDS)
        self.assertEqual(tuple(entries[1]), ENTRY_FIELDS)
        self.assertEqual(entries[0]["kind"], "game")
        self.assertEqual(entries[0]["cnRank"], 1)
        self.assertIsNone(entries[0]["usRank"])
        self.assertEqual(entries[1]["kind"], "application")
        self.assertEqual(entries[1]["charts"], [{"country": "us", "rank": 4}])

    def test_verified_platform_override_is_applied_by_unified_id(self):
        lookups = {"1527355884": lookup_result(
            "1527355884", "app.imone.OneWidget", "OneWidget", 6002, "Utilities", "1250290964",
        )}
        overrides = {
            "app_imone_onewidget": {
                "legacyId": "app-1527355884",
                "android": {"packageName": "tech.onenice.onewidget"},
                "harmony": {"bundleName": "tech.onenice.onewidget"},
            }
        }
        entry = build_list(
            [{"appStoreId": "1527355884", "cnRank": 8, "usRank": None}],
            lookups,
            overrides,
        )[0]
        self.assertEqual(entry["id"], "app_imone_onewidget")
        self.assertTrue(entry["authorApp"])
        self.assertEqual(entry["platforms"]["android"]["packageName"], "tech.onenice.onewidget")
        self.assertIsNone(entry["platforms"]["huawei"]["appGalleryId"])

    def test_union_rejects_conflicting_apple_identity(self):
        left = build_list(
            [{"appStoreId": "10", "cnRank": 1, "usRank": None}],
            {"10": lookup_result("10", "com.example.Game", "Blocks", 7012, "Puzzle")},
            {},
        )
        right = build_list(
            [{"appStoreId": "11", "cnRank": 1, "usRank": None}],
            {"11": lookup_result("11", "com.example.Game", "Other", 7012, "Puzzle")},
            {},
        )
        right[0]["id"] = left[0]["id"]
        with self.assertRaises(ValueError):
            union_entries(left, right)


class PreviewTests(unittest.TestCase):
    def test_page_switches_lists_and_embeds_icon_paths(self):
        app = build_list(
            [{"appStoreId": "10", "cnRank": 1, "usRank": 2}],
            {"10": lookup_result("10", "com.example.App", "</script>", 6002, "Utilities")},
            {},
        )[0]
        game = build_list(
            [{"appStoreId": "11", "cnRank": None, "usRank": 1}],
            {"11": lookup_result("11", "com.example.Game", "Blocks", 7012, "Puzzle")},
            {},
        )[0]
        document = {
            "chart": {
                "note": "说明",
                "usedDepth": {"cn": 1, "us": 1},
                "requestedDepth": 500,
            },
            "selection": {"count": 1},
        }
        icons = {app["id"]: {"id": app["id"], "path": f"styles/original/{app['id']}.jpg"}}
        html = render_preview(
            {**document, "apps": [app]},
            {**document, "chart": {**document["chart"], "requestedDepth": 200}, "apps": [game]},
            icons,
        )
        self.assertIn('id="show-apps"', html)
        self.assertIn('id="show-games"', html)
        self.assertIn(f"styles/original/{app['id']}.jpg", html)
        self.assertNotIn("</script><script>", html)
        self.assertIn("\\u003c/script>", html)
        self.assertEqual(unified_id_from_bundle("com.example.App"), app["id"])


class CaptureTests(unittest.TestCase):
    def test_capture_writes_matching_lists_without_padding(self):
        root = Path(tempfile.mkdtemp())
        (root / "metadata").mkdir()
        (root / "metadata" / "platform-overrides.json").write_text(
            json.dumps({"apps": {}, "evidence": {}}) + "\n", encoding="utf-8")
        charts = {
            ("apps", "cn"): ["10", "11", "12"],
            ("apps", "us"): ["11", "13"],
            ("games", "cn"): ["10", "14"],
            ("games", "us"): ["14", "15"],
        }
        details = {
            "10": lookup_result("10", "com.example.Game", "Blocks", 7012, "Puzzle"),
            "11": lookup_result("11", "com.example.App", "Notes", 6002, "Utilities"),
            "12": lookup_result("12", "com.example.Shop", "Shop", 6024, "Shopping"),
            "13": lookup_result("13", "com.example.Video", "Video", 6016, "Entertainment"),
            "14": lookup_result("14", "com.example.Race", "Race", 7013, "Racing"),
            "15": lookup_result("15", "com.example.Card", "Card", 7005, "Card"),
        }

        def fetch_chart(country, genre_id):
            list_name = "apps" if genre_id == "36" else "games"
            return charts[(list_name, country)], f"https://example.test/{list_name}/{country}"

        def fetch_lookup(country, store_ids):
            return [details[store_id] for store_id in store_ids]

        documents = capture_lists(root, "2026-10-17", fetch_chart=fetch_chart, fetch_lookup=fetch_lookup)
        apps = documents["apps"]["apps"]
        games = documents["games"]["apps"]
        self.assertEqual(documents["apps"]["chart"]["usedDepth"], {"cn": 3, "us": 2})
        self.assertEqual(documents["apps"]["chart"]["requestedDepth"], 500)
        self.assertEqual(len(apps), 4)
        self.assertEqual(tuple(apps[0]), tuple(games[0]))
        blocks = next(entry for entry in apps if entry["platforms"]["apple"]["appStoreId"] == "10")
        self.assertEqual(blocks["kind"], "game")
        self.assertEqual(blocks["cnRank"], 1)
        self.assertIsNone(blocks["usRank"])
        notes = next(entry for entry in apps if entry["platforms"]["apple"]["appStoreId"] == "11")
        self.assertEqual(notes["cnRank"], 2)
        self.assertEqual(notes["usRank"], 1)
        self.assertEqual(notes["kind"], "application")
        game_ids = {entry["platforms"]["apple"]["appStoreId"] for entry in games}
        self.assertEqual(game_ids, {"10", "14", "15"})
        preview = (root / "preview.html").read_text(encoding="utf-8")
        self.assertIn('id="show-apps"', preview)
        self.assertIn('id="show-games"', preview)
        apps_csv = (root / "metadata" / "apps.csv").read_text(encoding="utf-8").splitlines()[0]
        games_csv = (root / "metadata" / "games.csv").read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(apps_csv, games_csv)
        self.assertIn("cnRank", apps_csv)
        self.assertIn("usRank", apps_csv)


if __name__ == "__main__":
    unittest.main()
