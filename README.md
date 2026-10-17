# OneWidgetAppIcons

OneWidget 各端共用的应用图标目录。当前列表是中国区和美国区的 iPhone 免费榜：应用表收录两边免费应用总榜里苹果公开返回的全部名次（请求前 500，公开接口大约只有 200），游戏表收录两边免费游戏榜前 200。两边按统一 ID 去重。统一 ID 由 Apple bundle ID 生成，iOS、Android、HarmonyOS 和华为 AppGallery 都通过映射表回到这个 ID。官方商店图标与后来绘制的风格图标分开存放。

```text
metadata/apps.json              应用总榜：中区、美区名次和类型
metadata/games.json             游戏榜，字段与应用表相同
metadata/apps.csv               应用表
metadata/games.csv              游戏表，列与应用表相同
preview.html                    列表预览，顶部切换应用或游戏
metadata/platform-map.json      平台 ID 到统一 ID、再到图标路径
metadata/official-icons.json    官方图标的来源、尺寸、格式和校验值
metadata/platform-overrides.json 已核实的跨平台标识
metadata/styles.json            风格表：后缀、定义和特点
metadata/styles.csv             同一张风格表的表格
metadata/assets.json            已发布的绘制风格图标清单
styles/original/<id>.<ext>      默认原图风格，后缀见风格表
styles/mono/<id>.svg            手绘单色矢量图标（统一规范，须 1:1）
styles/<style>/<id>.<ext>       绘制风格；后缀以风格表为准
prompts/<style>/<id>.md         单图标提示词或绘制说明
skills/<style>/SKILL.md         风格制作规范
data/                           带日期的榜单研究快照
docs/                           研究方法与使用说明
```

统一 ID 的例子是 `app_imone_onewidget`，对应 bundle ID `app.imone.OneWidget`。旧 ID `app-1527355884` 保留在 `legacyId`。默认原图在 `styles/original/`。是否已经收齐，看 `metadata/official-icons.json` 的 `status`。`mono` 是计划中的手绘单色 SVG：按统一字重与边距绘制，不拼凑外网图标包；未绘制则留空。OneWidget 的 Android 和 HarmonyOS 标识已按对应工程核实为 `tech.onenice.onewidget`；其他应用的原生标识未核实前保持空白。应用和游戏如果出现在同一张榜里会各记一次名次，图标文件仍是一份。

`kind` 为 `game` 或 `application`。`cnRank`、`usRank` 是该表对应地区的总榜序号，没有上榜则留空。打开 `preview.html` 可以按列表查看图标。

- [目录结构与使用方法](docs/catalog-guide.md)
- [官方图标与跨平台映射](docs/official-icons.md)
- [2026-10-16 的 59 区样本研究](docs/app-store-research-2026-10-16.md)

校验目录：`python3 scripts/catalog.py validate`。校验官方图标：`python3 scripts/official_icons.py verify`。校验手绘单色图标：`python3 scripts/mono_icons.py verify`。更新中美榜：`python3 scripts/catalog.py charts`。查询：`python3 scripts/resolve_icon.py apple-bundle app.imone.OneWidget`。
