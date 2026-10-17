---
name: one-widget-mono-icon
description: Draw a unified monochrome SVG app icon using the repository's unified app ID and provenance rules.
---

# Mono icon production

`mono` is a **hand-drawn** style. Do not download or paste third-party icon packs
(Simple Icons, Arcticons, Wikimedia wordmarks, etc.). Mixed sources break stroke
weight and silhouette consistency.

## Visual system (must match across every icon)

1. Canvas: SVG `viewBox="0 0 1024 1024"` only (1:1). No other aspect ratio.
2. Medium: single-color vector. Fill `#000000` on transparent background (alpha).
3. Optical padding: keep the glyph inside the center ~76% box (about 122px inset
   on each side). Do not touch the canvas edge.
4. Weight: one optical weight family only — either **solid fill silhouettes** or
   **uniform stroke** (`stroke-width` equivalent to ~64 on the 1024 canvas,
   round caps/joins). Never mix fill-logo and thin-line icons in the same set.
5. Default for this repo: **solid fill silhouette** (no outlines, no dual stroke
   weights, no gradients, no text glyphs spelling the brand name).
6. Corner language: prefer slightly rounded joins; no random sharp/soft mix.
7. No system corner mask, no shadow, no color besides black.

If an icon cannot be drawn to this system, leave the slot empty.

## Steps

1. Find the target in `metadata/apps.json` or `metadata/games.json`; use unified `id`.
2. Create `prompts/mono/<id>.md` from `prompts/mono/_template.md`. Record the
   drawing brief (shapes, references reviewed, why the silhouette reads as that app).
3. Draw original artwork to the visual system above. Export
   `styles/mono/<id>.svg` with `viewBox="0 0 1024 1024"`.
4. Register in `metadata/assets.json` with `appId`, `styleId`=`mono`, `path`,
   `prompt`, `source` (e.g. `original-drawing`), and an approved `license`.
5. Run:

```sh
python3 scripts/mono_icons.py verify
python3 scripts/catalog.py validate
```

Do not copy files from `styles/original/` or ingest external icon CDNs.
