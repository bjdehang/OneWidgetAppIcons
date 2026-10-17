---
name: one-widget-mono-icon
description: Collect a monochrome SVG app icon using the repository's unified app ID and provenance rules.
---

# Mono icon collection

1. Find the target in `metadata/apps.json` or `metadata/games.json`; use its unified `id`.
2. Prefer a public monochrome SVG (Simple Icons or an official brand SVG). Record the source in `metadata/mono-overrides.json`.
3. The SVG canvas must be 1:1 (`viewBox` width equals height, or equal `width`/`height`). Reject non-square sources and leave the slot empty.
4. Save `styles/mono/<id>.svg` and `prompts/mono/<id>.md`, then register the asset in `metadata/assets.json` with `appId`, `styleId`, `path`, `prompt`, `source`, and `license`.
5. Run:

```sh
python3 scripts/mono_icons.py download
python3 scripts/mono_icons.py verify
python3 scripts/catalog.py validate
```

Do not copy files from `styles/original/`. Missing icons stay empty on purpose.
