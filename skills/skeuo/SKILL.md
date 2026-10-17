---
name: one-widget-skeuo-icon
description: Produce a skeuomorphic OneWidget app icon in glass, metal, and leather with a transparent PNG.
---

# 拟物图标

1. 在 `metadata/apps.json` 或 `metadata/games.json` 找到目标，使用统一 `id`。
2. 按 `prompts/skeuo/_template.md` 写 `prompts/skeuo/<id>.md`，记下实际提示词和参考来源。
3. 画一张 1024×1024、带透明通道的 PNG，保存为 `styles/skeuo/<id>.png`。材质用玻璃、金属、皮革，不预裁圆角。
4. 在 `metadata/assets.json` 登记 `appId`、`styleId`、`path`、`prompt`、`source` 和已确认的 `license`。
5. 运行 `python3 scripts/catalog.py validate`。不要把 `styles/original/` 里的文件拷进这个风格。
