# OneWidgetAppIcons

OneWidget 各端共用的应用图标目录。当前收录来自 31 个 App Store 地区免费榜的 **1000 款应用标识**，供 iOS、Android、HarmonyOS 使用同一个 `id` 查找图标。图标资源、提示词和风格技能按统一 ID 组织；目前尚未发布图标。

```text
metadata/apps.json              1000 款应用及平台 ID
metadata/apps.csv               便于人工查阅的同序列表
metadata/styles.json            风格目录
metadata/assets.json            已发布图标清单
styles/<style>/<id>.png         一个风格一个文件夹
prompts/<style>/<id>.md         单图标提示词
skills/<style>/SKILL.md         风格制作规范
data/                           带日期的榜单研究快照
docs/                           研究方法与使用说明
```

统一 ID 采用 `app-<Apple App Store ID>`，例如 `app-414478124` 对应微信。获取某个风格的图标时，用 `styles/<style>/<id>.png` 拼接路径，并先检查 `metadata/assets.json` 是否已发布该资源。Android 和 HarmonyOS 的原生标识字段保留在目录中，待官方来源核实后逐项填写。

- [目录结构与使用方法](docs/catalog-guide.md)
- [1000 款应用的 App Store 研究方法](docs/app-store-research-2026-10-16.md)

校验目录：`python3 scripts/catalog.py validate`。
