#!/usr/bin/env python3
"""Resolve a platform identifier to a unified app ID and optional icon path."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIELDS = {
    "apple-bundle": ("apple", "bundleId"),
    "apple-store": ("apple", "appStoreId"),
    "android": ("android", "packageName"),
    "harmony": ("harmony", "bundleName"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=FIELDS)
    parser.add_argument("identifier")
    parser.add_argument("style")
    args = parser.parse_args()

    apps = json.loads((ROOT / "metadata/apps.json").read_text(encoding="utf-8"))["apps"]
    assets = json.loads((ROOT / "metadata/assets.json").read_text(encoding="utf-8"))["assets"]
    platform, field = FIELDS[args.platform]
    app = next((item for item in apps
                if item["platforms"][platform][field] == args.identifier), None)
    if app is None:
        print(json.dumps({"found": False, "iconAvailable": False}))
        return
    path = f"styles/{args.style}/{app['id']}.png"
    available = any(asset["path"] == path for asset in assets) and (ROOT / path).is_file()
    print(json.dumps({
        "found": True,
        "id": app["id"],
        "name": app["name"],
        "iconAvailable": available,
        "iconPath": path if available else None,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
