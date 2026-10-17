---
name: one-widget-clay-icon
description: Produce a claymorphism OneWidget app icon as matte clay or ceramic with a transparent PNG.
---

# 黏土图标

1. 在 `metadata/apps.json` 或 `metadata/games.json` 找到目标，使用统一 `id`。
2. 按 `prompts/clay/_template.md` 写 `prompts/clay/<id>.md`，记下实际提示词和参考来源。
3. 画一张 1024×1024、带透明通道的 PNG，保存为 `styles/clay/<id>.png`。表面是彩色橡皮泥或哑光陶瓷，不预裁圆角。
4. 在 `metadata/assets.json` 登记 `appId`、`styleId`、`path`、`prompt`、`source` 和已确认的 `license`。
5. 运行 `python3 scripts/catalog.py validate`。不要把 `styles/original/` 里的文件拷进这个风格。
