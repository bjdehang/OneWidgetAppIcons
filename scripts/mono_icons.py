#!/usr/bin/env python3
"""Curate and verify mono SVG icons from a single approved pack.

Only Simple Icons (CC0) is allowed as an external source, so every glyph shares
the same filled-silhouette language. Downloaded SVGs are normalized to
viewBox 0 0 1024 1024 with black fill and uniform optical padding.
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
SOURCES_PATH = ROOT / "metadata/mono-sources.json"
ASSETS_PATH = ROOT / "metadata/assets.json"
APPS_PATH = ROOT / "metadata/apps.json"
GAMES_PATH = ROOT / "metadata/games.json"
STYLE_DIR = ROOT / "styles" / STYLE_ID
PROMPT_DIR = ROOT / "prompts" / STYLE_ID
CACHE_DIR = ROOT / ".cache/mono-icons"
USER_AGENT = "OneWidgetAppIcons-mono/1.0 (+https://github.com/bjdehang/OneWidgetAppIcons)"
CANVAS = 1024.0
PAD = 122.0  # ~12% inset → 76% glyph box
CONTENT = CANVAS - 2 * PAD  # 780
SI_SIZE = 24.0
SCALE = CONTENT / SI_SIZE  # 32.5
APPROVED_PROVIDER = "simple-icons"
SI_VERSIONS = ("16.35.0", "15.0.0", "12.4.0", "11.14.0")
VIEWBOX_RE = re.compile(
    r"viewBox\s*=\s*[\"']\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
    r"(?:[\s,]+)([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
    r"(?:[\s,]+)([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
    r"(?:[\s,]+)([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)[\"']",
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


def svg_canvas_ratio(content: str) -> tuple[float, float] | None:
    view = VIEWBOX_RE.search(content)
    if not view:
        return None
    width = float(view.group(3))
    height = float(view.group(4))
    if width > 0 and height > 0:
        return width, height
    return None


def is_square_canvas(content: str, tol: float = 1e-6) -> bool:
    size = svg_canvas_ratio(content)
    if size is None:
        return False
    width, height = size
    return abs(width - height) <= tol * max(width, height)


def fetch(url: str, timeout: float = 30.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def candidate_urls(slug: str) -> list[str]:
    urls = [f"https://api.iconify.design/simple-icons:{slug}.svg"]
    for version in SI_VERSIONS:
        urls.append(f"https://cdn.jsdelivr.net/npm/simple-icons@{version}/icons/{slug}.svg")
    return urls


def fetch_simple_icon(slug: str) -> tuple[bytes, str]:
    errors: list[str] = []
    for url in candidate_urls(slug):
        try:
            return fetch(url), url
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append(f"{url}: {exc}")
    raise urllib.error.URLError("; ".join(errors))


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def extract_drawable(root: ET.Element) -> list[ET.Element]:
    keep = []
    for elem in root.iter():
        if _local_tag(elem.tag) in {"path", "circle", "rect", "polygon", "polyline"}:
            keep.append(elem)
    return keep


def normalize_simple_icon(content: str, title: str) -> str:
    """Rewrite a Simple Icons SVG onto the repo mono canvas."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError(f"invalid SVG: {exc}") from exc
    if _local_tag(root.tag) != "svg":
        raise ValueError("root is not svg")
    size = svg_canvas_ratio(content)
    if size != (24.0, 24.0):
        raise ValueError(f"Simple Icons canvas must be 24x24, got {size}")
    shapes = extract_drawable(root)
    if not shapes:
        raise ValueError("no drawable shapes")

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" role="img">',
        f"<title>{_xml_escape(title)}</title>",
        f'<g transform="translate({PAD:g},{PAD:g}) scale({SCALE:g})" fill="#000000">',
    ]
    for shape in shapes:
        tag = _local_tag(shape.tag)
        attrs = []
        for key, value in shape.attrib.items():
            local = key.rsplit("}", 1)[-1]
            if local in {"fill", "stroke", "style", "class", "id"}:
                continue
            attrs.append(f'{local}="{_xml_escape(value)}"')
        attr_text = (" " + " ".join(attrs)) if attrs else ""
        parts.append(f"<{tag}{attr_text}/>")
    parts.append("</g></svg>\n")
    return "".join(parts)


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def prompt_text(app_id: str, name: str, entry: dict, sha256: str, source: str) -> str:
    return f"""# Mono icon curation record

Application ID: `{app_id}`
Application name: `{name}`

Curated from the sole approved pack **Simple Icons** (filled monochrome brand
marks, unified 24×24 language), then normalized to the repo mono canvas
`viewBox="0 0 1024 1024"` with black fill and ~12% optical padding.

## Source and rights

- Provider: `{APPROVED_PROVIDER}`
- Slug: `{entry.get("slug", "")}`
- Source URL: `{source}`
- License: `{entry.get("license", "CC0-1.0")}`
- SHA-256 (normalized file): `{sha256}`
- Popularity note: `{entry.get("note", "hot/popular catalog app")}`
- Collected at: `{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}`
"""


def asset_record(app_id: str, entry: dict, source: str) -> dict:
    return {
        "appId": app_id,
        "styleId": STYLE_ID,
        "path": f"styles/{STYLE_ID}/{app_id}.svg",
        "prompt": f"prompts/{STYLE_ID}/{app_id}.md",
        "source": source,
        "license": entry.get("license") or "CC0-1.0",
    }


def download(force: bool = False) -> int:
    sources = _load(SOURCES_PATH)
    if sources.get("provider") != APPROVED_PROVIDER:
        raise SystemExit(f"mono sources must use provider={APPROVED_PROVIDER}")
    catalog = catalog_ids()
    assets_doc = _load(ASSETS_PATH)
    other_assets = [
        asset for asset in assets_doc.get("assets", []) if asset.get("styleId") != STYLE_ID
    ]
    existing = {
        asset["appId"]: asset
        for asset in assets_doc.get("assets", [])
        if asset.get("styleId") == STYLE_ID
    }

    STYLE_DIR.mkdir(parents=True, exist_ok=True)
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    kept: list[dict] = []
    ok = failed = rejected = skipped = 0
    apps = sources.get("apps") or {}

    for app_id, entry in sorted(apps.items()):
        if app_id not in catalog:
            print(f"skip unknown id: {app_id}", file=sys.stderr)
            skipped += 1
            continue
        if entry.get("provider", APPROVED_PROVIDER) != APPROVED_PROVIDER:
            print(f"reject non-approved provider: {app_id}", file=sys.stderr)
            rejected += 1
            continue
        slug = entry.get("slug")
        if not slug:
            skipped += 1
            continue
        name = catalog[app_id]["name"]
        target = STYLE_DIR / f"{app_id}.svg"
        prompt_path = PROMPT_DIR / f"{app_id}.md"
        cache_raw = CACHE_DIR / f"si_{slug}.svg"

        if target.is_file() and prompt_path.is_file() and not force:
            content = target.read_text(encoding="utf-8")
            if svg_canvas_ratio(content) != (CANVAS, CANVAS) or not is_square_canvas(content):
                print(f"reject bad existing canvas: {app_id}", file=sys.stderr)
                target.unlink(missing_ok=True)
                prompt_path.unlink(missing_ok=True)
                rejected += 1
                continue
            source = entry.get("source") or candidate_urls(slug)[0]
            kept.append(asset_record(app_id, entry, source))
            ok += 1
            continue

        try:
            if cache_raw.is_file() and not force:
                raw = cache_raw.read_bytes()
                used_url = entry.get("source") or candidate_urls(slug)[0]
            else:
                raw, used_url = fetch_simple_icon(slug)
                cache_raw.write_bytes(raw)
            entry["source"] = used_url
            entry["provider"] = APPROVED_PROVIDER
            entry.setdefault("license", "CC0-1.0")
            normalized = normalize_simple_icon(raw.decode("utf-8"), name)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError) as exc:
            print(f"fail {app_id} ({slug}): {exc}", file=sys.stderr)
            failed += 1
            continue

        if not is_square_canvas(normalized) or svg_canvas_ratio(normalized) != (CANVAS, CANVAS):
            print(f"reject normalized canvas {app_id}", file=sys.stderr)
            rejected += 1
            continue

        sha256 = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        target.write_text(normalized, encoding="utf-8")
        prompt_path.write_text(
            prompt_text(app_id, name, entry, sha256, entry["source"]), encoding="utf-8"
        )
        kept.append(asset_record(app_id, entry, entry["source"]))
        ok += 1
        print(f"saved {app_id} <- simple-icons:{slug}")

    mono_ids = {item["appId"] for item in kept}
    for app_id, asset in existing.items():
        if app_id in mono_ids:
            continue
        (ROOT / asset["path"]).unlink(missing_ok=True)
        (ROOT / asset["prompt"]).unlink(missing_ok=True)

    assets_doc["assets"] = other_assets + kept
    assets_doc["schemaVersion"] = assets_doc.get("schemaVersion", 1)
    _write_json(ASSETS_PATH, assets_doc)
    sources["apps"] = apps
    _write_json(SOURCES_PATH, sources)

    print(
        f"mono icons: saved/kept={ok} failed={failed} rejected={rejected} "
        f"skipped={skipped} sourced={len(apps)} catalog={len(catalog)}"
    )
    return 0 if failed == 0 else 1


def verify() -> int:
    assets_doc = _load(ASSETS_PATH)
    mono = [asset for asset in assets_doc.get("assets", []) if asset.get("styleId") == STYLE_ID]
    ids = set(catalog_ids())
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
        if svg_canvas_ratio(content) != (CANVAS, CANVAS) or not is_square_canvas(content):
            print(f"bad canvas: {asset['path']}", file=sys.stderr)
            errors += 1
        if 'fill="#000000"' not in content and "fill='#000000'" not in content:
            print(f"missing black fill: {asset['path']}", file=sys.stderr)
            errors += 1
        prompt = ROOT / asset["prompt"]
        if not prompt.is_file():
            print(f"missing prompt: {asset['prompt']}", file=sys.stderr)
            errors += 1
    for image in STYLE_DIR.glob("*.svg"):
        relative = image.relative_to(ROOT).as_posix()
        if not any(asset["path"] == relative for asset in mono):
            print(f"unregistered mono SVG: {relative}", file=sys.stderr)
            errors += 1
    print(f"verified {len(mono)} mono assets, errors={errors}")
    return 0 if errors == 0 else 1


def status() -> int:
    catalog = catalog_ids()
    sourced = len((_load(SOURCES_PATH).get("apps") or {})) if SOURCES_PATH.exists() else 0
    assets = {
        asset["appId"]
        for asset in _load(ASSETS_PATH).get("assets", [])
        if asset.get("styleId") == STYLE_ID and (ROOT / asset["path"]).is_file()
    }
    print(f"catalog={len(catalog)}")
    print(f"sourced={sourced}")
    print(f"downloaded={len(assets)}")
    print(f"empty={len(catalog) - len(assets)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("download", "verify", "status"),
        help="download curated Simple Icons, verify, or print coverage",
    )
    parser.add_argument("--force", action="store_true", help="re-download and renormalize")
    args = parser.parse_args(argv)
    if args.command == "download":
        return download(force=args.force)
    if args.command == "verify":
        return verify()
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
