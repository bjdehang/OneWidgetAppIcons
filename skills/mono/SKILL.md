---
name: one-widget-mono-icon
description: Produce a monochrome OneWidget app icon with a transparent PNG and the repository's unified app ID.
---

# 单色图标

1. 在 `metadata/apps.json` 或 `metadata/games.json` 找到目标，使用统一 `id`。
2. 按 `prompts/mono/_template.md` 写 `prompts/mono/<id>.md`，记下实际提示词和参考来源。
3. 画一张 1024×1024、带透明通道的 PNG，保存为 `styles/mono/<id>.png`。只用纯色透明玻璃或符号，不预裁圆角。
4. 在 `metadata/assets.json` 登记 `appId`、`styleId`、`path`、`prompt`、`source` 和已确认的 `license`。
5. 运行 `python3 scripts/catalog.py validate`。不要把 `styles/original/` 里的文件拷进这个风格。
