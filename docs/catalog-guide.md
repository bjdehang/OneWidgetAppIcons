# 应用图标目录与使用规范

## 目录

```text
metadata/apps.json              统一应用目录和各平台标识
metadata/apps.csv               同序、便于表格查看的应用列表
metadata/platform-map.json      平台 ID → 统一 ID → 图标相对路径
metadata/official-icons.json    官方图标来源、尺寸、格式和 SHA-256
metadata/platform-overrides.json 已核实的跨平台 ID 与来源
metadata/styles.json            风格列表
metadata/assets.json            已发布风格图标的来源和授权记录
icons/official/<id>.<ext>       App Store 官方图标，按实际格式保存
styles/<style>/<id>.png         绘制后的风格图标；一个风格一个文件夹
prompts/<style>/<id>.md         单图标生成提示词
skills/<style>/SKILL.md         该风格的制作流程
data/app-store-snapshot-*.json  App Store 榜单研究快照
data/author-apps-*.json         OneWidget 开发者账号应用快照
design/                         设计文字说明；预览图按项目规则存 OneDrive
docs/                           使用说明和研究报告
```

`<id>` 是统一 ID，由 Apple bundle ID 小写后把 `.` 和空格换成 `_` 得到。`app.imone.OneWidget` 的统一 ID 是 `app_imone_onewidget`。以前的 `app-<Apple App Store ID>` 写在 `legacyId`，例如 `app-1527355884`，查询时仍然可用。统一 ID 只用于本仓库和 OneWidget 各端取图；不要将它误当成 Android package name、Harmony bundle name 或华为 AppGallery ID。应用改名不改 bundle ID，因此也不改统一 ID。bundle ID 发生变化时要人工核对，不能静默覆盖已有文件。

官方图标和风格图标分开。风格目录只放该风格的 PNG。统一输出为 **1024 × 1024 PNG**，不预裁系统圆角。路径由风格与统一 ID 拼出：

```text
styles/flat/app_imone_onewidget.png
```

当前 `flat` 只是计划中的风格，尚未发布任何 PNG。应用目录中的 2000 项表示这 2000 款应用被收录；官方图标是否已经下载，以 `metadata/official-icons.json` 的 `status` 和其中的记录为准。风格图标则只使用 `metadata/assets.json` 中登记且文件存在的项。缺图时使用端内默认图。

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
- `charts`：上榜地区与当时名次，供排序和人工审查。它不是永久热度排名。
- `authorApp`：是否属于 OneWidget 所在的 Apple 开发者账号。作者应用即使未进入采样榜单也固定收录。

Android 包名、HarmonyOS bundle name 和华为 AppGallery ID 必须分别核实后写入 `metadata/platform-overrides.json`，再进入应用目录。不能从 Apple bundle ID 推导，也不能互相复制。跨平台同品牌但产品不同的情况要人工确认再映射到同一个统一 ID。OneWidget 已核实的 Android `applicationId` 和 HarmonyOS `bundleName` 均为 `tech.onenice.onewidget`，证据列在 `metadata/platform-overrides.json`。华为 ID 尚未核实，保持 `null`。

## 查找流程

1. 用 `metadata/platform-map.json` 按 Apple bundle ID、App Store 数字 ID、旧统一 ID、Android 包名、HarmonyOS bundle name 或华为 AppGallery ID 找到唯一的 `id`。
2. 取官方图标时读取该行的 `iconPath`，文件在 `icons/official/`。
3. 取某种绘制风格时，再查 `metadata/assets.json`，并读取 `styles/<style>/<id>.png`。

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

新增风格时，在 `metadata/styles.json` 登记新 ID，创建 `styles/<style>/`、`prompts/<style>/` 与 `skills/<style>/SKILL.md`。风格 ID 只用小写英文字母、数字和连字符。

新增风格图标时保存准确提示词、来源及授权，在 `metadata/assets.json` 登记 `appId`、`styleId`、`path`、`prompt`、`source`、`license`。这里的 `appId` 使用新的统一 ID。官方 App Store 图标不登记进 `assets.json`，也不放进 `styles/`；它们由 `scripts/official_icons.py` 下载到 `icons/official/`，来源和校验值写在 `metadata/official-icons.json`。该清单不记载商业授权。运行：

```sh
python3 scripts/catalog.py validate
python3 scripts/official_icons.py verify
```

刷新榜单：

```sh
python3 scripts/catalog.py refresh
```

刷新会生成新的日期快照并重建 `metadata/apps.json`；脚本从 Apple 开发者账号再次查询作者应用，保留已入选应用的人工跨平台标识，并将已发布图标的应用固定在候选中。若非作者应用完全退出当前榜单，脚本会停止并要求人工处理，避免静默丢失映射。刷新后仍应审核与上一版的差异。
