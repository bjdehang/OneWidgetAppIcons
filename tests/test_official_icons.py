"""Naming, mapping, download resume, and catalog checks for official icons."""

import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import catalog  # noqa: E402
from catalog import check_style_record  # noqa: E402
import official_icons  # noqa: E402
from mapping import (  # noqa: E402
    DuplicateMappingError,
    MissingImageError,
    MissingMappingError,
    UnknownPlatformError,
    lookup,
)
from official_icons import (  # noqa: E402
    candidate_countries,
    map_entry,
    migrate_catalog,
    response_is_capped,
    rewrite_artwork_url,
    select_artwork,
    sync_official_icons,
    verify,
    write_maps,
)
from unified_id import legacy_id, unified_id_from_bundle  # noqa: E402


def sample_app(store_id, bundle, name="Sample", charts=None, author=False,
               android=None, harmony=None, huawei=None):
    return {
        "id": unified_id_from_bundle(bundle),
        "legacyId": legacy_id(store_id),
        "name": name,
        "developer": "Example Developer",
        "genre": {"id": "6002", "name": "Utilities"},
        "platforms": {
            "apple": {
                "appStoreId": str(store_id),
                "bundleId": bundle,
                "url": f"https://apps.apple.com/app/id{store_id}",
            },
            "android": {"packageName": android},
            "harmony": {"bundleName": harmony},
            "huawei": {"appGalleryId": huawei},
        },
        "charts": [] if charts is None and author else (charts if charts is not None else [{"country": "us", "rank": 1}]),
        "authorApp": author,
    }


def png_bytes(size, color=(0, 0, 0)):
    image = Image.new("RGB", (size, size), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def lookup_result(app, artwork=True):
    result = {
        "trackId": int(app["platforms"]["apple"]["appStoreId"]),
        "bundleId": app["platforms"]["apple"]["bundleId"],
    }
    if artwork:
        store_id = app["platforms"]["apple"]["appStoreId"]
        result["artworkUrl512"] = f"https://cdn.test/{store_id}/512x512bb.jpg"
    return result


class NamingTests(unittest.TestCase):
    def test_onewidget_bundle_id(self):
        self.assertEqual(unified_id_from_bundle("app.imone.OneWidget"), "app_imone_onewidget")

    def test_lowercase_dots_and_spaces(self):
        self.assertEqual(unified_id_from_bundle("App.Foo Bar.Baz"), "app_foo_bar_baz")

    def test_hyphen_is_preserved(self):
        self.assertEqual(unified_id_from_bundle("ru.inDriver-ru"), "ru_indriver-ru")

    def test_legacy_id_keeps_the_numeric_store_id(self):
        self.assertEqual(legacy_id("1527355884"), "app-1527355884")

    def test_rejects_empty_bundle_id(self):
        with self.assertRaises(ValueError):
            unified_id_from_bundle("  ")


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.one = sample_app(
            "1527355884", "app.imone.OneWidget", name="OneWidget",
            author=True, android="tech.onenice.onewidget", harmony="tech.onenice.onewidget",
        )
        self.other = sample_app("1", "com.example.Other", name="Other")
        self.entries = [map_entry(self.one, None), map_entry(self.other, None)]

    def test_missing_mapping(self):
        with self.assertRaises(MissingMappingError) as caught:
            lookup(self.entries, "android", "com.not.mapped", self.root)
        self.assertIn("Missing mapping", str(caught.exception))

    def test_huawei_is_not_copied_from_apple_or_harmony(self):
        with self.assertRaises(MissingMappingError):
            lookup(self.entries, "huawei", "tech.onenice.onewidget", self.root)
        with self.assertRaises(MissingMappingError):
            lookup(self.entries, "huawei", "app.imone.OneWidget", self.root)
        with self.assertRaises(MissingImageError):
            lookup(self.entries, "harmony", "tech.onenice.onewidget", self.root)

    def test_duplicate_mapping(self):
        duplicate = map_entry(sample_app("2", "com.example.Second", android="tech.onenice.onewidget"), None)
        entries = self.entries + [duplicate]
        with self.assertRaises(DuplicateMappingError) as caught:
            lookup(entries, "android", "tech.onenice.onewidget", self.root)
        self.assertIn("Duplicate mapping", str(caught.exception))

    def test_unknown_platform(self):
        with self.assertRaises(UnknownPlatformError) as caught:
            lookup(self.entries, "windows", "app.imone.OneWidget", self.root)
        self.assertIn("Unknown platform", str(caught.exception))

    def test_missing_image_file(self):
        entries = [map_entry(self.one, {"path": "styles/original/app_imone_onewidget.png"})]
        with self.assertRaises(MissingImageError) as caught:
            lookup(entries, "apple-bundle", "app.imone.OneWidget", self.root)
        self.assertIn("Missing image", str(caught.exception))

    def test_existing_image_returns_the_unified_path(self):
        relative = "styles/original/app_imone_onewidget.png"
        destination = self.root / relative
        destination.parent.mkdir(parents=True)
        destination.write_bytes(png_bytes(1))
        entries = [map_entry(self.one, {"path": relative})]
        found = lookup(entries, "legacy", "app-1527355884", self.root)
        self.assertEqual(found["id"], "app_imone_onewidget")
        self.assertEqual(found["iconPath"], relative)
        named = lookup(entries, "legacy", "app-1527355884", self.root, style="original")
        self.assertEqual(named["iconPath"], relative)

    def test_cli_reports_wrong_platform_and_missing_image(self):
        map_path = self.root / "map.json"
        map_path.write_text(json.dumps({"entries": self.entries}), encoding="utf-8")
        script = ROOT / "scripts" / "resolve_icon.py"
        wrong = subprocess.run(
            [sys.executable, str(script), "windows", "x", "--map", str(map_path), "--root", str(self.root)],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(wrong.returncode, 2)
        self.assertIn("Unknown platform", wrong.stderr)
        self.assertEqual(json.loads(wrong.stdout)["error"], "unknown_platform")
        missing = subprocess.run(
            [sys.executable, str(script), "apple-store", "1", "--map", str(map_path), "--root", str(self.root)],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(missing.returncode, 1)
        self.assertIn("Missing image", missing.stderr)
        self.assertEqual(json.loads(missing.stdout)["error"], "missing_image")


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.clock = "2026-10-17T00:00:00+00:00"
        self.one = sample_app("1", "com.example.One", name="One")
        self.two = sample_app("2", "com.example.Two", name="Two")

    def sync(self, apps, fetch_lookup, fetch_bytes, **kwargs):
        return sync_official_icons(
            apps, self.root,
            fetch_lookup=fetch_lookup,
            fetch_bytes=fetch_bytes,
            checkpoint_path=self.root / "checkpoint.json",
            workers=1,
            clock=lambda: self.clock,
            log=lambda *_args: None,
            **kwargs,
        )

    def test_resume_skips_completed_download_and_keeps_the_file(self):
        calls = {"bytes": [], "lookups": []}
        outage = {"used": False}

        def fetch_lookup(country, ids):
            calls["lookups"].append((country, list(ids)))
            return [lookup_result(app) for app in (self.one, self.two) if app["platforms"]["apple"]["appStoreId"] in ids]

        def fetch_bytes(url):
            calls["bytes"].append(url)
            if "/2/" in url and not outage["used"]:
                outage["used"] = True
                raise RuntimeError("temporary outage")
            return png_bytes(2, (1, 2, 3))

        self.sync([self.one, self.two], fetch_lookup, fetch_bytes)
        first = self.root / "styles" / "original" / "com_example_one.png"
        original = first.read_bytes()
        self.assertFalse((self.root / "styles" / "original" / "com_example_two.png").exists())
        calls["bytes"].clear()
        calls["lookups"].clear()
        self.sync([self.one, self.two], fetch_lookup, fetch_bytes)
        self.assertEqual(first.read_bytes(), original)
        self.assertTrue(all("/1/" not in url for url in calls["bytes"]))
        self.assertTrue(all("1" not in ids for _country, ids in calls["lookups"]))
        self.assertTrue((self.root / "styles" / "original" / "com_example_two.png").is_file())

    def test_refuses_to_overwrite_a_different_file(self):
        destination = self.root / "styles" / "original" / "com_example_one.png"
        destination.parent.mkdir(parents=True)
        original = png_bytes(2, (9, 9, 9))
        destination.write_bytes(original)

        def fetch_lookup(country, ids):
            return [lookup_result(self.one)]

        def fetch_bytes(url):
            return png_bytes(2, (1, 2, 3))

        records = self.sync([self.one], fetch_lookup, fetch_bytes)
        self.assertEqual(destination.read_bytes(), original)
        self.assertEqual(records["1"]["reason"], "refusing_overwrite")

    def test_duplicate_unified_id_does_not_download(self):
        first = sample_app("1", "com.example.One")
        second = sample_app("2", "com.example.Two")
        second["id"] = first["id"]
        calls = {"bytes": 0}

        def fetch_lookup(country, ids):
            raise AssertionError("lookup should not run for a duplicate ID")

        def fetch_bytes(url):
            calls["bytes"] += 1
            return png_bytes(1)

        records = self.sync([first, second], fetch_lookup, fetch_bytes)
        self.assertEqual(calls["bytes"], 0)
        self.assertEqual(records["1"]["reason"], "duplicate_id")
        self.assertEqual(records["2"]["reason"], "duplicate_id")
        self.assertEqual(list((self.root / "styles" / "original").glob("*")), [])

    def test_bundle_mismatch_and_removed_app(self):
        def fetch_lookup(country, ids):
            results = []
            if "1" in ids:
                results.append({
                    "trackId": 1,
                    "bundleId": "com.example.Wrong",
                    "artworkUrl512": "https://cdn.test/1/512x512bb.jpg",
                })
            return results

        records = self.sync([self.one, self.two], fetch_lookup, lambda url: png_bytes(1))
        self.assertEqual(records["1"]["reason"], "bundle_mismatch")
        self.assertIn("bundleId mismatch", records["1"]["detail"])
        self.assertEqual(records["2"]["reason"], "not_in_store")
        self.assertEqual(list((self.root / "styles" / "original").glob("*")), [])

    def test_author_app_tries_us_then_cn(self):
        author = sample_app("5", "app.imone.OneWidget", author=True)
        seen = []

        def fetch_lookup(country, ids):
            seen.append(country)
            if country == "cn":
                return [lookup_result(author)]
            return []

        records = self.sync([author], fetch_lookup, lambda url: png_bytes(2))
        self.assertEqual(seen, ["us", "cn"])
        self.assertEqual(records["5"]["status"], "ok")
        self.assertEqual(records["5"]["country"], "cn")
        self.assertTrue(records["5"]["path"].endswith(".png"))

    def test_chart_country_prefers_cn_and_does_not_invent_us(self):
        app = sample_app("9", "com.example.Local", charts=[{"country": "jp", "rank": 3}, {"country": "cn", "rank": 8}])
        self.assertEqual(candidate_countries(app), ["cn", "jp"])
        author = sample_app("8", "com.example.Author", author=True)
        self.assertEqual(candidate_countries(author), ["us", "cn"])

    def test_artwork_size_is_capped_and_not_upscaled(self):
        self.assertTrue(response_is_capped(1024, 1024, 10000))
        self.assertFalse(response_is_capped(1024, 1024, 1024))
        api_url = "https://cdn.test/icon/512x512bb.jpg"
        self.assertEqual(rewrite_artwork_url(api_url, 10000), "https://cdn.test/icon/10000x10000bb.jpg")
        images = {8: png_bytes(8, (1, 1, 1)), 4: png_bytes(2, (2, 2, 2))}
        previous = official_icons.PROBE_EDGES
        official_icons.PROBE_EDGES = (8, 4, 2)
        try:
            selected = select_artwork(api_url, lambda url: images[8] if "/8x8" in url else images[4])
        finally:
            official_icons.PROBE_EDGES = previous
        self.assertEqual((selected["width"], selected["height"]), (2, 2))
        self.assertIn("/4x4bb.jpg", selected["sourceUrl"])
        self.assertEqual(selected["format"], "png")

    def test_filled_probe_is_rejected(self):
        previous = official_icons.PROBE_EDGES
        official_icons.PROBE_EDGES = (4,)
        try:
            with self.assertRaises(ValueError) as caught:
                select_artwork(
                    "https://cdn.test/icon/512x512bb.jpg",
                    lambda url: png_bytes(4),
                )
        finally:
            official_icons.PROBE_EDGES = previous
        self.assertIn("upscaled", str(caught.exception))


class CatalogTests(unittest.TestCase):
    def test_migrate_preserves_identity_and_is_idempotent(self):
        root = Path(tempfile.mkdtemp())
        (root / "metadata").mkdir()
        app = sample_app(
            "1527355884", "app.imone.OneWidget", name="OneWidget", author=True,
            charts=[{"country": "cn", "rank": 4}],
        )
        app["id"] = "app-1527355884"
        app.pop("legacyId")
        catalog_document = {
            "schemaVersion": 1,
            "generatedAt": "2026-10-16T00:00:00+00:00",
            "snapshot": "data/app-store-snapshot.json",
            "selection": {"target": 1},
            "apps": [app],
        }
        (root / "metadata" / "apps.json").write_text(
            json.dumps(catalog_document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (root / "metadata" / "platform-overrides.json").write_text(json.dumps({
            "schemaVersion": 1,
            "apps": {"app-1527355884": {
                "android": {"packageName": "tech.onenice.onewidget"},
                "harmony": {"bundleName": "tech.onenice.onewidget"},
            }},
            "evidence": {"app-1527355884": {"android": "gradle"}},
        }, indent=2) + "\n", encoding="utf-8")
        migrate_catalog(root, now="2026-10-17T00:00:00+00:00")
        migrated = json.loads((root / "metadata" / "apps.json").read_text(encoding="utf-8"))
        stored = migrated["apps"][0]
        self.assertEqual(stored["id"], "app_imone_onewidget")
        self.assertEqual(stored["legacyId"], "app-1527355884")
        self.assertEqual(stored["charts"], [{"country": "cn", "rank": 4}])
        self.assertEqual(stored["platforms"]["apple"]["bundleId"], "app.imone.OneWidget")
        self.assertEqual(stored["platforms"]["huawei"]["appGalleryId"], None)
        self.assertEqual(migrated["generatedAt"], "2026-10-16T00:00:00+00:00")
        overrides = json.loads((root / "metadata" / "platform-overrides.json").read_text(encoding="utf-8"))
        self.assertEqual(
            overrides["apps"]["app_imone_onewidget"]["android"]["packageName"],
            "tech.onenice.onewidget",
        )
        self.assertNotIn("app.imone.OneWidget", json.dumps(overrides["apps"]["app_imone_onewidget"]["android"]))
        official = json.loads((root / "metadata" / "official-icons.json").read_text(encoding="utf-8"))
        self.assertEqual(official["status"], "incomplete")
        self.assertEqual(official["icons"], [])
        migrate_catalog(root, now="2026-10-17T00:00:00+00:00")
        again = json.loads((root / "metadata" / "apps.json").read_text(encoding="utf-8"))["apps"][0]
        self.assertEqual(again["id"], stored["id"])
        self.assertEqual(again["legacyId"], stored["legacyId"])

    def test_verify_accepts_a_decoded_icon_and_rejects_a_broken_manifest(self):
        root = Path(tempfile.mkdtemp())
        (root / "metadata").mkdir()
        app = sample_app("7", "com.example.Icon", name="Icon")
        image = png_bytes(3, (4, 5, 6))
        relative = "styles/original/com_example_icon.png"
        destination = root / relative
        destination.parent.mkdir(parents=True)
        destination.write_bytes(image)
        import hashlib
        digest = hashlib.sha256(image).hexdigest()
        icon = {
            "id": app["id"],
            "legacyId": app["legacyId"],
            "name": app["name"],
            "bundleId": app["platforms"]["apple"]["bundleId"],
            "appStoreId": "7",
            "path": relative,
            "sourceUrl": "https://cdn.test/7/10000x10000bb.jpg",
            "country": "us",
            "updatedAt": "2026-10-17T00:00:00+00:00",
            "width": 3,
            "height": 3,
            "format": "png",
            "sha256": digest,
        }
        (root / "metadata" / "apps.json").write_text(
            json.dumps({"apps": [app]}, indent=2) + "\n", encoding="utf-8")
        (root / "metadata" / "platform-overrides.json").write_text(
            json.dumps({"apps": {}, "evidence": {}}) + "\n", encoding="utf-8")
        write_maps(root, [app], [icon], [], status="complete", now="2026-10-17T00:00:00+00:00")
        summary = verify(root)
        self.assertEqual(summary["icons"], 1)
        icon["sha256"] = "0" * 64
        write_maps(root, [app], [icon], [], status="complete", now="2026-10-17T00:00:00+00:00")
        with self.assertRaises(ValueError) as caught:
            verify(root)
        self.assertIn("SHA-256", str(caught.exception))

    def test_live_catalog_ids_platforms_and_validate(self):
        apps = json.loads((ROOT / "metadata" / "apps.json").read_text(encoding="utf-8"))["apps"]
        self.assertEqual(len(apps), 2000)
        ids = [app["id"] for app in apps]
        self.assertEqual(len(set(ids)), 2000)
        one = next(app for app in apps if app["legacyId"] == "app-1527355884")
        self.assertEqual(one["id"], "app_imone_onewidget")
        self.assertEqual(one["platforms"]["android"]["packageName"], "tech.onenice.onewidget")
        self.assertEqual(one["platforms"]["harmony"]["bundleName"], "tech.onenice.onewidget")
        self.assertIsNone(one["platforms"]["huawei"]["appGalleryId"])
        entries = [map_entry(app, None) for app in apps]
        with self.assertRaises(MissingMappingError):
            lookup(entries, "huawei", "tech.onenice.onewidget", ROOT)
        with self.assertRaises(MissingImageError):
            lookup(entries, "android", "tech.onenice.onewidget", ROOT)
        catalog.validate()


class StyleTableTests(unittest.TestCase):
    def test_registered_styles_record_suffix_definition_and_traits(self):
        styles = json.loads((ROOT / "metadata/styles.json").read_text(encoding="utf-8"))["styles"]
        by_id = {style["id"]: style for style in styles}
        original = by_id["original"]
        flat = by_id["flat"]
        self.assertEqual(original["extensions"], [".jpg", ".png"])
        self.assertIn("商店原图", original["definition"])
        self.assertEqual(original["characteristics"]["transparency"], "as-delivered")
        self.assertEqual(flat["extensions"], [".png"])
        self.assertEqual(flat["characteristics"]["transparency"], "opaque")
        self.assertEqual(flat["characteristics"]["dimensions"], "1024x1024")
        self.assertTrue(flat["characteristics"]["summary"])

    def test_style_table_accepts_svg_and_transparent_png_shapes(self):
        svg = {
            "id": "line",
            "name": "Line",
            "status": "planned",
            "definition": "描边矢量图标。",
            "extensions": [".svg"],
            "characteristics": {
                "media": "vector",
                "transparency": "alpha",
                "dimensions": "scalable",
                "mask": "none",
                "summary": "SVG，可以包含透明区域。",
            },
        }
        transparent = {
            "id": "cutout",
            "name": "Cutout",
            "status": "planned",
            "definition": "带透明图层的光栅图标。",
            "extensions": [".png"],
            "characteristics": {
                "media": "raster",
                "transparency": "alpha",
                "dimensions": "1024x1024",
                "mask": "none",
                "summary": "PNG 必须保留透明通道。",
            },
        }
        self.assertEqual(check_style_record(svg), "line")
        self.assertEqual(check_style_record(transparent), "cutout")
        jpeg_alpha = json.loads(json.dumps(transparent))
        jpeg_alpha["extensions"] = [".jpg"]
        with self.assertRaises(ValueError) as caught:
            check_style_record(jpeg_alpha)
        self.assertIn("transparent", str(caught.exception))
        raster_svg = json.loads(json.dumps(svg))
        raster_svg["characteristics"]["media"] = "raster"
        with self.assertRaises(ValueError):
            check_style_record(raster_svg)


if __name__ == "__main__":
    unittest.main()
