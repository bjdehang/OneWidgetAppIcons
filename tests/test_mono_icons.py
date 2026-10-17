#!/usr/bin/env python3
"""Tests for monochrome SVG canvas checks and style registration."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mono_icons import is_square_canvas, svg_canvas_ratio  # noqa: E402


class MonoIconsTests(unittest.TestCase):
    def test_square_viewbox_accepted(self):
        svg = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M0 0h24v24H0z"/></svg>'
        self.assertEqual(svg_canvas_ratio(svg), (24.0, 24.0))
        self.assertTrue(is_square_canvas(svg))

    def test_non_square_viewbox_rejected(self):
        svg = '<svg viewBox="0 0 32 16" xmlns="http://www.w3.org/2000/svg"><path d="M0 0h32v16H0z"/></svg>'
        self.assertEqual(svg_canvas_ratio(svg), (32.0, 16.0))
        self.assertFalse(is_square_canvas(svg))

    def test_equal_width_height_accepted(self):
        svg = '<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40"/></svg>'
        self.assertTrue(is_square_canvas(svg))

    def test_style_table_includes_mono(self):
        styles = json.loads((ROOT / "metadata/styles.json").read_text(encoding="utf-8"))["styles"]
        mono = next(item for item in styles if item["id"] == "mono")
        self.assertEqual(mono["extensions"], [".svg"])
        self.assertEqual(mono["characteristics"]["media"], "vector")
        self.assertEqual(mono["characteristics"]["dimensions"], "scalable")
        self.assertEqual(mono["status"], "published")


if __name__ == "__main__":
    unittest.main()
