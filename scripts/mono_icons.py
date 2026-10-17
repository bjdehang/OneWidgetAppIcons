#!/usr/bin/env python3
"""Collect monochrome SVG icons for catalog apps and games.

Sources are listed in metadata/mono-overrides.json. Icons that are missing from
the network, or whose SVG canvas is not 1:1, are left unset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
STYLE_ID = "mono"
OVERRIDES_PATH = ROOT / "metadata/mono-overrides.json"
ASSETS_PATH = ROOT / "metadata/assets.json"
APPS_PATH = ROOT / "metadata/apps.json"
GAMES_PATH = ROOT / "metadata/games.json"
STYLE_DIR = ROOT / "styles" / STYLE_ID
PROMPT_DIR = ROOT / "prompts" / STYLE_ID
CACHE_DIR = ROOT / ".cache/mono-icons"
USER_AGENT = "OneWidgetAppIcons-mono/1.0 (+https://github.com/bjdehang/OneWidgetAppIcons)"
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


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def catalog_ids() -> dict[str, dict]:
    apps = {item["id"]: item for item in _load(APPS_PATH)["apps"]}
    games = {item["id"]: item for item in _load(GAMES_PATH)["apps"]}
    merged = dict(games)
    merged.update(apps)
    return merged


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
    """Return (width, height) of the SVG canvas, or None if unknown."""
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


SI_VERSIONS = ("16.35.0", "15.0.0", "12.4.0", "11.14.0")


def fetch(url: str, timeout: float = 30.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def resolve_source(entry: dict) -> str:
    """Return a downloadable URL for one override entry, with SI version fallback."""
    if entry.get("source"):
        source = entry["source"]
        # Prefer the recorded URL; callers may still fall back on failure.
        return source
    provider = entry.get("provider") or "simple-icons"
    slug = entry.get("slug")
    if not slug:
        raise ValueError("override entry needs source or slug")
    if provider == "arcticons":
        return f"https://api.iconify.design/arcticons:{slug}.svg"
    if provider == "simple-icons":
        return f"https://api.iconify.design/simple-icons:{slug}.svg"
    raise ValueError(f"unsupported provider: {provider}")


def fetch_entry(entry: dict) -> tuple[bytes, str]:
    """Download SVG bytes and the URL that succeeded."""
    provider = entry.get("provider") or "simple-icons"
    slug = entry.get("slug") or ""
    candidates: list[str] = []
    primary = resolve_source(entry)
    candidates.append(primary)
    if provider == "simple-icons" and slug:
        candidates.append(f"https://api.iconify.design/simple-icons:{slug}.svg")
        for version in SI_VERSIONS:
            candidates.append(
                f"https://cdn.jsdelivr.net/npm/simple-icons@{version}/icons/{slug}.svg"
            )
    elif provider == "arcticons" and slug:
        candidates.append(f"https://api.iconify.design/arcticons:{slug}.svg")
    seen: set[str] = set()
    errors: list[str] = []
    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        try:
            return fetch(url), url
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append(f"{url}: {exc}")
    raise urllib.error.URLError("; ".join(errors) or "no candidates")


def prompt_text(app_id: str, name: str, entry: dict, sha256: str) -> str:
    return f"""# Mono icon collection record

Application ID: `{app_id}`
Application name: `{name}`

Collected a monochrome brand SVG (not redrawn). Canvas must be 1:1; non-square
sources are rejected and the slot stays empty.

## Source and rights

- Provider: `{entry.get("provider", "unknown")}`
- Slug / key: `{entry.get("slug", "")}`
- Source URL: `{entry["source"]}`
- License: `{entry.get("license", "")}`
- SHA-256: `{sha256}`
- Match reason: `{entry.get("match", "")}`
- Collected at: `{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}`
"""


def asset_record(app_id: str, entry: dict) -> dict:
    return {
        "appId": app_id,
        "styleId": STYLE_ID,
        "path": f"styles/{STYLE_ID}/{app_id}.svg",
        "prompt": f"prompts/{STYLE_ID}/{app_id}.md",
        "source": entry["source"],
        "license": entry.get("license") or "unknown",
    }


def download(force: bool = False) -> int:
    overrides = _load(OVERRIDES_PATH)
    catalog = catalog_ids()
    assets_doc = _load(ASSETS_PATH)
    existing = {
        asset["appId"]: asset
        for asset in assets_doc.get("assets", [])
        if asset.get("styleId") == STYLE_ID
    }
    other_assets = [
        asset for asset in assets_doc.get("assets", []) if asset.get("styleId") != STYLE_ID
    ]

    STYLE_DIR.mkdir(parents=True, exist_ok=True)
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    kept: list[dict] = []
    ok = skipped = failed = rejected = 0
    apps = overrides.get("apps") or {}

    for app_id, entry in sorted(apps.items()):
        if app_id not in catalog:
            print(f"skip unknown id: {app_id}", file=sys.stderr)
            skipped += 1
            continue
        name = catalog[app_id]["name"]
        target = STYLE_DIR / f"{app_id}.svg"
        prompt_path = PROMPT_DIR / f"{app_id}.md"
        provider = entry.get("provider") or "simple-icons"
        slug = entry.get("slug") or app_id

        if target.is_file() and prompt_path.is_file() and not force:
            content = target.read_text(encoding="utf-8")
            if not is_square_canvas(content):
                print(f"reject non-square existing: {app_id}", file=sys.stderr)
                target.unlink(missing_ok=True)
                prompt_path.unlink(missing_ok=True)
                rejected += 1
                continue
            sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
            kept.append(asset_record(app_id, entry))
            if not prompt_path.read_text(encoding="utf-8").strip():
                prompt_path.write_text(prompt_text(app_id, name, entry, sha256), encoding="utf-8")
            ok += 1
            continue

        cache_file = CACHE_DIR / f"{provider}_{slug}.svg"
        try:
            if cache_file.is_file() and not force:
                raw = cache_file.read_bytes()
                used_url = entry.get("source") or resolve_source(entry)
            else:
                raw, used_url = fetch_entry(entry)
                cache_file.write_bytes(raw)
                entry["source"] = used_url
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            print(f"fetch failed {app_id}: {exc}", file=sys.stderr)
            failed += 1
            continue

        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            print(f"reject non-utf8 SVG: {app_id}", file=sys.stderr)
            rejected += 1
            continue

        if "<svg" not in content.lower():
            print(f"reject non-svg payload: {app_id}", file=sys.stderr)
            rejected += 1
            continue
        if not is_square_canvas(content):
            ratio = svg_canvas_ratio(content)
            print(f"reject non-square canvas {app_id}: {ratio}", file=sys.stderr)
            rejected += 1
            continue

        sha256 = hashlib.sha256(raw).hexdigest()
        target.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
        prompt_path.write_text(prompt_text(app_id, name, entry, sha256), encoding="utf-8")
        kept.append(asset_record(app_id, entry))
        ok += 1
        print(f"saved {app_id} <- {provider}:{slug}")

    # Drop mono assets that are no longer sourced or whose files vanished.
    mono_ids = {item["appId"] for item in kept}
    for app_id, asset in existing.items():
        path = ROOT / asset["path"]
        if app_id in mono_ids:
            continue
        if path.is_file():
            # Keep only if still registered above; otherwise remove orphans.
            path.unlink(missing_ok=True)
        prompt = ROOT / asset["prompt"]
        prompt.unlink(missing_ok=True)

    assets_doc["assets"] = other_assets + kept
    assets_doc["schemaVersion"] = assets_doc.get("schemaVersion", 1)
    _write_json(ASSETS_PATH, assets_doc)
    # Persist any source URLs resolved via provider fallback.
    overrides["apps"] = apps
    _write_json(OVERRIDES_PATH, overrides)

    print(
        f"mono icons: saved/kept={ok} fetch_failed={failed} "
        f"rejected_non_square_or_invalid={rejected} skipped={skipped} "
        f"listed_sources={len(apps)} catalog={len(catalog)}"
    )
    return 0 if failed == 0 else 1


def verify() -> int:
    assets_doc = _load(ASSETS_PATH)
    mono = [asset for asset in assets_doc.get("assets", []) if asset.get("styleId") == STYLE_ID]
    errors = 0
    for asset in mono:
        path = ROOT / asset["path"]
        if not path.is_file():
            print(f"missing file: {asset['path']}", file=sys.stderr)
            errors += 1
            continue
        content = path.read_text(encoding="utf-8")
        if not is_square_canvas(content):
            print(f"non-square SVG: {asset['path']}", file=sys.stderr)
            errors += 1
        prompt = ROOT / asset["prompt"]
        if not prompt.is_file():
            print(f"missing prompt: {asset['prompt']}", file=sys.stderr)
            errors += 1
    print(f"verified {len(mono)} mono assets, errors={errors}")
    return 0 if errors == 0 else 1


def status() -> int:
    catalog = catalog_ids()
    overrides = (_load(OVERRIDES_PATH).get("apps") or {})
    assets = {
        asset["appId"]
        for asset in _load(ASSETS_PATH).get("assets", [])
        if asset.get("styleId") == STYLE_ID and (ROOT / asset["path"]).is_file()
    }
    print(f"catalog={len(catalog)}")
    print(f"sourced={len(overrides)}")
    print(f"downloaded={len(assets)}")
    print(f"empty={len(catalog) - len(assets)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("download", "verify", "status"),
        help="download icons, verify square SVGs, or print coverage",
    )
    parser.add_argument("--force", action="store_true", help="re-download even if files exist")
    args = parser.parse_args(argv)
    if args.command == "download":
        return download(force=args.force)
    if args.command == "verify":
        return verify()
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
