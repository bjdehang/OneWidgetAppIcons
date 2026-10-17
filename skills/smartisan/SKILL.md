---
name: one-widget-smartisan-icon
description: Place Smartisan OS server icons at source size, or later redraw a 1024 PNG. Do not delete the server icons.
---

# 锤子图标

1. 在 `metadata/apps.json` 或 `metadata/games.json` 找到目标，使用统一 `id`。
2. 按 `prompts/smartisan/_template.md` 写 `prompts/smartisan/<id>.md`，记下实际提示词和参考来源。
3. 图标先放在 `styles/smartisan/<统一 ID>.png`。统一 ID 来自苹果 bundle ID；还没有苹果 bundle ID 时，用 Android 包名按同一规则命名。当前文件是锤子图标服务器的原尺寸，先不要重绘，也不要删掉这些文件。
4. 这些原尺寸文件不写入 `metadata/assets.json`，也不配生成提示词。以后若重绘成 1024，再另存那张重绘图并登记来源、授权和提示词。
5. 运行 `python3 scripts/catalog.py validate`。不要把 `styles/original/` 里的文件拷进这个风格。
