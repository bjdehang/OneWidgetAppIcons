---
name: one-widget-mono-icon
description: Curate unified monochrome SVG app icons from Simple Icons only, normalized to the repo canvas.
---

# Mono icon curation

`mono` uses **one** external pack so style stays unified:

| Source | Why |
| --- | --- |
| [Simple Icons](https://simpleicons.org) ([GitHub](https://github.com/simple-icons/simple-icons)) | De-facto standard for monochrome brand SVGs; every mark is a filled silhouette on `24×24`, CC0 |

Do **not** mix Arcticons, Dashboard Icons stroke sets, Wikimedia wordmarks, or random X posts. Those packs use different line weights and break visual unity.

## Visual system (after normalize)

1. Canvas: `viewBox="0 0 1024 1024"` (1:1 only).
2. Fill: `#000000` on transparent background.
3. Optical padding: ~12% inset (glyph in the center 76% box).
4. Language: solid fill silhouette only (Simple Icons path language).
5. No gradients, no multi-color, no system corner mask.

## Steps

1. Only add **hot / popular** catalog apps that have a Simple Icons slug.
2. Record the mapping in `metadata/mono-sources.json`.
3. Run:

```sh
python3 scripts/mono_icons.py download
python3 scripts/mono_icons.py verify
python3 scripts/catalog.py validate
```

4. The download step normalizes each SVG onto the 1024 canvas and writes
   `styles/mono/<id>.svg`, `prompts/mono/<id>.md`, and `metadata/assets.json`.

If Simple Icons has no mark for an app, leave the slot empty.
