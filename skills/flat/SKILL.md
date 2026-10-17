---
name: one-widget-flat-icon
description: Produce a flat-style OneWidget app icon using the repository's unified app ID and provenance rules.
---

# Flat icon production

1. Find the target in `metadata/apps.json`; use its unified `id` (for example `app_imone_onewidget`). The old `app-<store id>` value is `legacyId`.
2. Create `prompts/flat/<id>.md` from `prompts/flat/_template.md`. Record the exact prompt and reference source.
3. Generate original artwork, visually review it, and export a 1024 × 1024 PNG to `styles/flat/<id>.png`. Keep the square image unmasked.
4. Add `styles/flat/<id>.png` to `metadata/assets.json` with `appId`, `styleId`, `path`, `prompt`, `source`, and an approved `license`.
5. Run `python3 scripts/catalog.py validate` before committing. Do not copy a file from `styles/original/` into this style. Original artwork stays in that directory and is not a generated asset.
