#!/usr/bin/env python3
"""Resolve a platform identifier to a unified app ID and icon path."""

import argparse
import json
import sys
from pathlib import Path

from mapping import (
    PLATFORMS,
    DuplicateMappingError,
    MappingError,
    MissingImageError,
    MissingMappingError,
    UnknownPlatformError,
    lookup,
)


ROOT = Path(__file__).resolve().parents[1]
ERROR_CODES = {
    UnknownPlatformError: "unknown_platform",
    MissingMappingError: "missing_mapping",
    DuplicateMappingError: "duplicate_mapping",
    MissingImageError: "missing_image",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", help=f"one of: {', '.join(PLATFORMS)}")
    parser.add_argument("identifier")
    parser.add_argument("style", nargs="?", help="generated style id; omit for the official icon")
    parser.add_argument("--map", type=Path, help="platform map JSON (default: metadata/platform-map.json)")
    parser.add_argument("--root", type=Path, help="repository root used to check image files")
    args = parser.parse_args()

    root = args.root or ROOT
    map_path = args.map or (root / "metadata/platform-map.json")
    entries = json.loads(map_path.read_text(encoding="utf-8"))["entries"]
    assets = None
    if args.style:
        assets = json.loads((root / "metadata/assets.json").read_text(encoding="utf-8"))["assets"]
    try:
        result = lookup(entries, args.platform, args.identifier, root, style=args.style, assets=assets)
    except MappingError as error:
        code = ERROR_CODES.get(type(error), "mapping_error")
        print(f"Error: {error}", file=sys.stderr)
        print(json.dumps({
            "found": False,
            "iconAvailable": False,
            "error": code,
            "message": str(error),
        }, ensure_ascii=False))
        return 2 if isinstance(error, UnknownPlatformError) else 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
