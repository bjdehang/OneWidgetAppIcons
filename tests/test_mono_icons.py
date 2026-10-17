#!/usr/bin/env python3
"""Tests for mono SVG normalization and style registration."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mono_icons import is_square_canvas, normalize_simple_icon, svg_canvas_ratio  # noqa: E402


class MonoIconsTests(unittest.TestCase):
    def test_normalize_simple_icon_to_1024(self):
        raw = (
            '<svg role="img" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
            '<title>Test</title><path d="M0 0h24v24H0z"/></svg>'
        )
        out = normalize_simple_icon(raw, "Test App")
        self.assertEqual(svg_canvas_ratio(out), (1024.0, 1024.0))
        self.assertTrue(is_square_canvas(out))
        self.assertIn('fill="#000000"', out)
        self.assertIn("scale(32.5)", out)

    def test_non_square_viewbox_rejected(self):
        svg = '<svg viewBox="0 0 32 16" xmlns="http://www.w3.org/2000/svg"><path d="M0 0h32v16H0z"/></svg>'
        self.assertFalse(is_square_canvas(svg))

    def test_style_and_sources_use_simple_icons_only(self):
        styles = json.loads((ROOT / "metadata/styles.json").read_text(encoding="utf-8"))["styles"]
        mono = next(item for item in styles if item["id"] == "mono")
        self.assertEqual(mono["status"], "published")
        self.assertIn("Simple Icons", mono["definition"])
        sources = json.loads((ROOT / "metadata/mono-sources.json").read_text(encoding="utf-8"))
        self.assertEqual(sources["provider"], "simple-icons")
        self.assertTrue(sources["apps"])


if __name__ == "__main__":
    unittest.main()
