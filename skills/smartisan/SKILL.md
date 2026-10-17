---
name: one-widget-smartisan-icon
description: Draw a Smartisan-style OneWidget app icon as an opaque 1024 PNG without copying Smartisan system files.
---

# 锤子图标

1. 在 `metadata/apps.json` 或 `metadata/games.json` 找到目标，使用统一 `id`。
2. 按 `prompts/smartisan/_template.md` 写 `prompts/smartisan/<id>.md`，记下实际提示词和参考来源。
3. 按 Smartisan OS 图标库的画法重绘一张 1024×1024 的不透明 PNG，保存为 `styles/smartisan/<id>.png`。使用大圆角色块底板、高饱和纯色和居中图形。不要把锤子系统里的图标文件拷进仓库。
4. 在 `metadata/assets.json` 登记 `appId`、`styleId`、`path`、`prompt`、`source` 和已确认的 `license`。
5. 运行 `python3 scripts/catalog.py validate`。不要把 `styles/original/` 里的文件拷进这个风格。
