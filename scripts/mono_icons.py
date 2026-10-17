#!/usr/bin/env python3
"""Verify hand-drawn mono SVG icons.

mono is a drawn style. This script does not download third-party icon packs.
It only checks that registered mono assets exist, are SVG, and use a 1:1 canvas.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
STYLE_ID = "mono"
ASSETS_PATH = ROOT / "metadata/assets.json"
APPS_PATH = ROOT / "metadata/apps.json"
GAMES_PATH = ROOT / "metadata/games.json"
STYLE_DIR = ROOT / "styles" / STYLE_ID
VIEWBOX_RE = re.compile(
    r"viewBox\s*=\s*[\"']\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
    r"(?:[\s,]+)([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
    r"(?:[\s,]+)([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
    r"(?:[\s,]+)([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)[\"']",
    re.I,
)
LENGTH_RE = re.compile(
    r"""^(?P<num>[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)(?P<unit>[a-z%]*)$""",
    re.I,
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def catalog_ids() -> set[str]:
    apps = {item["id"] for item in _load(APPS_PATH)["apps"]}
    games = {item["id"] for item in _load(GAMES_PATH)["apps"]}
    return apps | games


def parse_length(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if not text or text.endswith("%"):
        return None
    match = LENGTH_RE.match(text)
    if not match:
        return None
    return float(match.group("num"))


def svg_canvas_ratio(content: str) -> tuple[float, float] | None:
    view = VIEWBOX_RE.search(content)
    if view:
        width = float(view.group(3))
        height = float(view.group(4))
        if width > 0 and height > 0:
            return width, height
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return None
    width = parse_length(root.attrib.get("width"))
    height = parse_length(root.attrib.get("height"))
    if width and height and width > 0 and height > 0:
        return width, height
    return None


def is_square_canvas(content: str, tol: float = 1e-6) -> bool:
    size = svg_canvas_ratio(content)
    if size is None:
        return False
    width, height = size
    return abs(width - height) <= tol * max(width, height)


def verify() -> int:
    assets_doc = _load(ASSETS_PATH)
    mono = [asset for asset in assets_doc.get("assets", []) if asset.get("styleId") == STYLE_ID]
    ids = catalog_ids()
    errors = 0
    for asset in mono:
        if asset.get("appId") not in ids:
            print(f"unknown appId: {asset.get('appId')}", file=sys.stderr)
            errors += 1
        path = ROOT / asset["path"]
        if not path.is_file():
            print(f"missing file: {asset['path']}", file=sys.stderr)
            errors += 1
            continue
        content = path.read_text(encoding="utf-8")
        if not is_square_canvas(content):
            print(f"non-square SVG: {asset['path']}", file=sys.stderr)
            errors += 1
        size = svg_canvas_ratio(content)
        if size != (1024.0, 1024.0):
            print(
                f"mono SVG should use viewBox 0 0 1024 1024: {asset['path']} got {size}",
                file=sys.stderr,
            )
            errors += 1
        prompt = ROOT / asset["prompt"]
        if not prompt.is_file():
            print(f"missing prompt: {asset['prompt']}", file=sys.stderr)
            errors += 1
    # Unregistered files under styles/mono are also errors (catalog validate catches this too).
    for image in STYLE_DIR.glob("*.svg"):
        relative = image.relative_to(ROOT).as_posix()
        if not any(asset["path"] == relative for asset in mono):
            print(f"unregistered mono SVG: {relative}", file=sys.stderr)
            errors += 1
    print(f"verified {len(mono)} mono assets, errors={errors}")
    return 0 if errors == 0 else 1


def status() -> int:
    ids = catalog_ids()
    assets = {
        asset["appId"]
        for asset in _load(ASSETS_PATH).get("assets", [])
        if asset.get("styleId") == STYLE_ID and (ROOT / asset["path"]).is_file()
    }
    print(f"catalog={len(ids)}")
    print(f"drawn={len(assets)}")
    print(f"empty={len(ids) - len(assets)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("verify", "status"),
        help="verify drawn mono SVGs or print coverage",
    )
    args = parser.parse_args(argv)
    if args.command == "verify":
        return verify()
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
