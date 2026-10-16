# 应用图标目录与使用规范

## 目录

```text
metadata/apps.json              统一应用目录和各平台标识
metadata/apps.csv               同序、便于表格查看的应用列表
metadata/styles.json            风格列表
metadata/assets.json            已发布图标的来源和授权记录
styles/<style>/<id>.png         运行时图标；一个风格一个文件夹
prompts/<style>/<id>.md         单图标生成提示词
skills/<style>/SKILL.md         该风格的制作流程
data/app-store-snapshot-*.json  App Store 榜单研究快照
design/                         设计文字说明；预览图按项目规则存 OneDrive
docs/                           使用说明和研究报告
```

`<id>` 是不可变的统一 ID，格式为 `app-<Apple App Store ID>`。例如微信的 App Store ID 为 `414478124`，图标文件名就是 `app-414478124.png`。统一 ID 只用于本仓库和 OneWidget 各端取图；不要将它误当成 Android package name 或 Harmony bundle name。应用改名不改统一 ID；不同 App Store ID 的版本视为不同应用，合并前需人工核对。

每个风格目录仅放该风格的 PNG 文件和 Git 占位文件。统一输出为 **1024 × 1024 PNG**，不预裁系统圆角。路径可由风格与统一 ID 直接拼出：

```text
styles/flat/app-414478124.png
```

当前 `flat` 只是计划中的风格，尚未发布任何 PNG。应用目录中的 1000 项表示“可寻址的候选应用”，不表示 1000 张图已经制作。消费者应只使用 `metadata/assets.json` 中登记且文件存在的图标；缺图时使用自己端内的默认图。

## 平台标识

`metadata/apps.json` 每项包含：

- `id`：跨平台统一 ID，稳定文件名。
- `platforms.apple.appStoreId`：Apple 商品 ID，用于 App Store 页面及榜单去重。
- `platforms.apple.bundleId`：Apple 应用 bundle ID，用于 iOS 应用匹配。
- `platforms.android.packageName`：Android 包名；`null` 表示尚未核实。
- `platforms.harmony.bundleName`：HarmonyOS bundle name；`null` 表示尚未核实。
- `charts`：上榜地区与当时名次，供排序和人工审查。它不是永久热度排名。

Android 和 HarmonyOS 标识必须分别从对应官方应用商店、开发者资料或应用包核实后填写；不能从 Apple bundle ID 推导。跨平台同品牌但产品不同的情况要人工确认再映射到同一个统一 ID。

## 查找流程

1. 读取 `metadata/apps.json`，按已知的 Apple bundle ID、App Store ID、Android package name 或 Harmony bundle name 找到 `id`。
2. 用 `metadata/assets.json` 检查目标风格是否已发布图标。
3. 用 `styles/<style>/<id>.png` 读取图片。路径不存在时显示端内默认图。

例如 iOS 端匹配 `com.tencent.xin` 后得到 `app-414478124`；若将来发布了 `flat` 风格，就读取 `styles/flat/app-414478124.png`。

命令行也可查询，返回 JSON 中的 `id` 与 `iconAvailable`：

```sh
python3 scripts/resolve_icon.py apple-bundle com.tencent.xin flat
```

## 新增应用、风格和图标

新增应用时先核实 Apple App Store ID 与 bundle ID，检查目录中是否已有同一产品。目录刷新脚本用于榜单研究；手工维护的跨平台标识在刷新前需保留或合并，不能被榜单快照覆盖。

新增风格时，在 `metadata/styles.json` 登记新 ID，创建 `styles/<style>/`、`prompts/<style>/` 与 `skills/<style>/SKILL.md`。风格 ID 只用小写英文字母、数字和连字符。

新增图标时保存准确提示词、来源及授权，在 `metadata/assets.json` 登记 `appId`、`styleId`、`path`、`prompt`、`source`、`license`。官方 App Store 图标仅作为榜单元数据来源，不直接下载进本图标仓库。运行：

```sh
python3 scripts/catalog.py validate
```

刷新榜单：

```sh
python3 scripts/catalog.py refresh
```

刷新会生成新的日期快照并重建 `metadata/apps.json`；脚本保留已入选应用的人工跨平台标识，并将已发布图标的应用固定在候选中。若这些应用完全退出当前榜单，脚本会停止并要求人工处理，避免静默丢失映射。刷新后仍应审核与上一版的差异。
