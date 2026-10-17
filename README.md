# OneWidgetAppIcons

OneWidget 各端共用的应用图标目录。当前收录来自 59 个 App Store 地区免费榜和 OneWidget 开发者账号的 **2000 款应用标识**。统一 ID 由 Apple bundle ID 生成，iOS、Android、HarmonyOS 和华为 AppGallery 都通过映射表回到这个 ID。官方商店图标与后来绘制的风格图标分开存放。

```text
metadata/apps.json              2000 款应用及平台 ID
metadata/apps.csv               便于人工查阅的同序列表
metadata/platform-map.json      平台 ID 到统一 ID、再到图标路径
metadata/official-icons.json    官方图标的来源、尺寸、格式和校验值
metadata/platform-overrides.json 已核实的跨平台标识
metadata/styles.json            风格目录
metadata/assets.json            已发布的风格图标清单
styles/original/<id>.<ext>      默认原图风格，扩展名与实际格式一致
styles/<style>/<id>.png         绘制风格；一个风格一个文件夹
prompts/<style>/<id>.md         单图标提示词
skills/<style>/SKILL.md         风格制作规范
data/                           带日期的榜单研究快照
docs/                           研究方法与使用说明
```

统一 ID 的例子是 `app_imone_onewidget`，对应 bundle ID `app.imone.OneWidget`。旧 ID `app-1527355884` 保留在 `legacyId`。默认原图在 `styles/original/`。是否已经收齐，看 `metadata/official-icons.json` 的 `status`。OneWidget 的 Android 和 HarmonyOS 标识已按对应工程核实为 `tech.onenice.onewidget`；其他应用的原生标识未核实前保持空白。

- [目录结构与使用方法](docs/catalog-guide.md)
- [官方图标与跨平台映射](docs/official-icons.md)
- [2000 款应用的 App Store 研究方法](docs/app-store-research-2026-10-16.md)

校验目录：`python3 scripts/catalog.py validate`。校验官方图标：`python3 scripts/official_icons.py verify`。查询：`python3 scripts/resolve_icon.py apple-bundle app.imone.OneWidget`。
