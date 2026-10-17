# 应用图标目录与使用规范

## 目录

```text
metadata/apps.json              中区、美区免费应用总榜
metadata/games.json             中区、美区免费游戏榜，记录字段与应用表相同
metadata/apps.csv               应用表
metadata/games.csv              游戏表，列与 apps.csv 相同
preview.html                    列表预览页，顶部切换应用或游戏，并显示图标
metadata/platform-map.json      平台 ID → 统一 ID → 图标相对路径
metadata/official-icons.json    官方图标来源、尺寸、格式和 SHA-256
metadata/platform-overrides.json 已核实的跨平台 ID 与来源
metadata/styles.json            风格表：每个风格的后缀、定义和特点
metadata/styles.csv             同一张风格表，便于表格查看
metadata/assets.json            已发布风格图标的来源和授权记录
styles/original/<id>.<ext>      默认原图风格，后缀见风格表
styles/<style>/<id>.<ext>       绘制后的风格图标；后缀以风格表为准
prompts/<style>/<id>.md         单图标生成提示词
skills/<style>/SKILL.md         该风格的制作流程
data/app-store-snapshot-*.json  App Store 榜单研究快照
data/author-apps-*.json         OneWidget 开发者账号应用快照
design/                         设计文字说明；预览图按项目规则存 OneDrive
docs/                           使用说明和研究报告
```

`<id>` 是统一 ID，由 Apple bundle ID 小写后把 `.` 和空格换成 `_` 得到。`app.imone.OneWidget` 的统一 ID 是 `app_imone_onewidget`。以前的 `app-<Apple App Store ID>` 写在 `legacyId`，例如 `app-1527355884`，查询时仍然可用。统一 ID 只用于本仓库和 OneWidget 各端取图；不要将它误当成 Android package name、Harmony bundle name 或华为 AppGallery ID。应用改名不改 bundle ID，因此也不改统一 ID。bundle ID 发生变化时要人工核对，不能静默覆盖已有文件。

每个风格在 `metadata/styles.json` 和 `metadata/styles.csv` 里占一行。这一行记录文件后缀、风格定义，以及媒介、透明、尺寸和圆角这些特点。`original` 的后缀是 `.jpg` 和 `.png`，扩展名跟随商店返回的真实格式，不要求透明图层。`flat` 只存不透明的 `.png`，尺寸是 1024×1024，不预裁系统圆角。路径由风格、统一 ID 和该风格登记的后缀拼出：

```text
styles/flat/app_imone_onewidget.png
```

当前 `flat` 只是计划中的绘制风格，尚未发布任何 PNG。应用表和游戏表的条目数以各自 JSON 里的 `selection.count` 为准。原图是否已经下载，以 `metadata/official-icons.json` 的 `status` 和其中的记录为准。绘制风格只使用 `metadata/assets.json` 中登记且文件存在的项。缺图时使用端内默认图。

## 平台标识

`metadata/apps.json` 每项包含：

- `id`：跨平台统一 ID，由 bundle ID 按上述规则生成，也是图标文件名。
- `legacyId`：迁移前的 `app-<App Store ID>`。
- `name`：收录时的显示名称。
- `platforms.apple.appStoreId`：Apple 商品数字 ID，用于 Lookup API、App Store 页面及榜单去重。
- `platforms.apple.bundleId`：Apple 应用 bundle ID，保留原始大小写。
- `platforms.android.packageName`：Android 包名；`null` 表示尚未核实。
- `platforms.harmony.bundleName`：HarmonyOS bundle name；`null` 表示尚未核实。
- `platforms.huawei.appGalleryId`：华为 AppGallery ID；`null` 表示尚未核实。它和 HarmonyOS bundle name 不是同一个字段。
- `kind`：`game` 或 `application`。总榜里既有游戏也有应用，这个字段把两者分开。游戏榜里的条目同样带这个字段。
- `cnRank`、`usRank`：该表对应的中国区、美国区总榜序号。应用表用免费应用总榜，游戏表用免费游戏榜。没有出现在该区这张榜上时为 `null`，CSV 里留空。
- `charts`：和上面两个名次相同的 `{country, rank}` 列表，只含 `cn` 和 `us`。
- `authorApp`：是否属于 OneWidget 所在的 Apple 开发者账号。只有当前榜单里的作者应用会带上这个标记。

Android 包名、HarmonyOS bundle name 和华为 AppGallery ID 必须分别核实后写入 `metadata/platform-overrides.json`，再进入应用目录。不能从 Apple bundle ID 推导，也不能互相复制。跨平台同品牌但产品不同的情况要人工确认再映射到同一个统一 ID。OneWidget 已核实的 Android `applicationId` 和 HarmonyOS `bundleName` 均为 `tech.onenice.onewidget`，证据列在 `metadata/platform-overrides.json`。华为 ID 尚未核实，保持 `null`。

## 查找流程

1. 用 `metadata/platform-map.json` 按 Apple bundle ID、App Store 数字 ID、旧统一 ID、Android 包名、HarmonyOS bundle name 或华为 AppGallery ID 找到唯一的 `id`。
2. 取默认原图时读取该行的 `iconPath`，文件在 `styles/original/`。查询时省略风格名，或显式使用 `original`。
3. 取某种绘制风格时，再查 `metadata/assets.json`，并按风格表里的后缀读取 `styles/<style>/<id>.<后缀>`。

映射不存在、同一个平台 ID 对应多款应用、或记录在册但文件缺失时，查询命令会失败并说明是哪一种错误。不要把缺失当成空路径继续使用。

```sh
python3 scripts/resolve_icon.py apple-bundle app.imone.OneWidget
python3 scripts/resolve_icon.py apple-store 1527355884
python3 scripts/resolve_icon.py android tech.onenice.onewidget
python3 scripts/resolve_icon.py legacy app-1527355884
```

带风格参数时检查的是绘制结果，例如 `python3 scripts/resolve_icon.py apple-bundle app.imone.OneWidget flat`。`flat` 尚未发布图片时，这条命令会报告缺图。

## 新增应用、风格和图标

新增应用时先核实 Apple App Store ID 与 bundle ID，检查目录中是否已有同一产品。目录刷新脚本用于榜单研究；手工维护的跨平台标识在刷新前需保留或合并，不能被榜单快照覆盖。

新增风格时，在 `metadata/styles.json` 增加一行，并同步 `metadata/styles.csv`。必填的是 `id`、`name`、`status`、`definition`、`extensions` 和 `characteristics`。特点里的 `media` 取 `raster` 或 `vector`，`transparency` 取 `as-delivered`（保持原图有没有透明）、`opaque`（不带透明图层）或 `alpha`（必须有透明图层），`dimensions` 取 `source`、`scalable` 或 `1024x1024` 这种固定尺寸，`mask` 取 `none`（不预裁圆角）或 `unspecified`。矢量风格的后缀只能是 `.svg`，尺寸写 `scalable`。带透明图层的光栅风格把 `transparency` 写成 `alpha`，后缀用 `.png` 这类能保存透明通道的格式。风格 ID 只用小写英文字母、数字和连字符。同时创建 `styles/<style>/`、`prompts/<style>/` 与 `skills/<style>/SKILL.md`。

新增绘制风格的图标时保存准确提示词、来源及授权，在 `metadata/assets.json` 登记 `appId`、`styleId`、`path`、`prompt`、`source`、`license`。这里的 `appId` 使用新的统一 ID。`original` 不写入 `assets.json`：它由 `scripts/official_icons.py` 下载到 `styles/original/`，来源和校验值写在 `metadata/official-icons.json`。该清单不记载商业授权。运行：

```sh
python3 scripts/catalog.py validate
python3 scripts/official_icons.py verify
```

更新中美榜：

```sh
python3 scripts/catalog.py charts
python3 scripts/official_icons.py download
```

`charts` 读取苹果 viewTop 免费榜（榜单 id 27）。应用表请求中国区和美国区各自前 500 名；这个公开接口目前每个地区大约只返回 200 个名次，脚本会全部收下，不会把缺少的名次补成 500。游戏表取两边免费游戏榜前 200 名。两张表按统一 ID 去重，字段相同。已核实的跨平台标识仍从 `metadata/platform-overrides.json` 合并。预览页是仓库根目录的 `preview.html`。
