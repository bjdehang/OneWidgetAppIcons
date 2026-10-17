# 官方图标与跨平台映射

本目录的 2000 款应用仍以 `metadata/apps.json` 为准，地区和榜单名次不因下载图标而改变。官方图标单独放在 `icons/official/`，不放进 `styles/flat/`。`styles/` 只收后来按风格重新绘制、并在 `metadata/assets.json` 登记的图。

## 统一 ID

统一 ID 由 Apple bundle ID 生成：全部改为小写，把 `.` 和空格换成 `_`，其余字符保留。`app.imone.OneWidget` 得到 `app_imone_onewidget`。文件名使用这个 ID，扩展名按图片实际格式确定，JPEG 保持 `.jpg`，不会改名成 `.png`。

原来的 `app-<App Store 数字 ID>` 保留为 `legacyId`。查询时可以用 `legacy` 平台继续按旧 ID 查找。应用显示名称、bundle ID 和数字 App Store ID 仍是各自的字段，不写进统一 ID。

若两个应用得到同一个统一 ID，下载会停下并为两边记下 `duplicate_id`，不会用后一个文件覆盖前一个。

## 下载

下载脚本按数字 App Store ID 调用 Apple Lookup API（`itunes.apple.com/lookup`）。查询国家来自该应用的上榜地区，中国和美国优先；作者应用没有榜单记录时使用 `us`，没有结果再查 `cn`。返回的 `bundleId` 必须与目录里的值一致，不一致就记为 `bundle_mismatch`，不保存图片。所有候选国家都没有结果时记为 `not_in_store`。

接口通常给出 `artworkUrl512`。脚本把尺寸后缀改成更大的边长，保留原来的 `bb` 标记和扩展名。只有当返回图片的宽和高都小于所请求的边长时才保存，这是 CDN 在原图尺寸处截断的结果；铺满请求尺寸的响应可能是放大图，会继续尝试更小的请求，仍无法确认时记为 `upscale`，不保存。

每条成功记录包含相对路径、来源 URL、查询国家、写入时间、宽高、格式和 SHA-256。这些字段只描述文件从哪里来、是什么字节，不表示本仓库拥有或授予该图标的使用授权。

```sh
python3 scripts/official_icons.py migrate
python3 scripts/official_icons.py download
python3 scripts/official_icons.py verify
```

`download` 把进度写在 `.cache/official-icons/checkpoint.json`。已校验通过的文件不会再次请求，也不会被另一款应用覆盖。网络失败会在后续轮次重试；应用下架和 bundle ID 不一致视为已结束的失败，需要 `--retry-failed` 才会重查。缓存和临时文件不提交。

`metadata/official-icons.json` 的 `status` 为 `incomplete` 时，表示还有应用没有得到图标或仍有可重试的失败。`complete` 表示每款应用要么有一张校验过的图标，要么有一条明确的失败原因。

## 映射

`metadata/platform-map.json` 是查询表。一行对应一款应用，字段为：

| 平台 | 字段 | 查询名 |
| --- | --- | --- |
| 统一 ID | `id` | `id` |
| 旧统一 ID | `legacyId` | `legacy` |
| Apple bundle ID | `bundleId` | `apple-bundle` |
| Apple 数字 ID | `appleAppStoreId` | `apple-store` |
| Android 包名 | `androidPackageName` | `android` |
| HarmonyOS bundle name | `harmonyBundleName` | `harmony` |
| 华为 AppGallery ID | `huaweiAppGalleryId` | `huawei` |

Android、HarmonyOS 和华为是三个独立字段。没有核实过的值保持 `null`，不会把 Apple bundle ID 抄进去。OneWidget 已核实的 Android 包名和 HarmonyOS bundle name 都是 `tech.onenice.onewidget`，证据在 `metadata/platform-overrides.json`。它的华为 AppGallery ID 仍为空。

```sh
python3 scripts/resolve_icon.py apple-bundle app.imone.OneWidget
python3 scripts/resolve_icon.py android tech.onenice.onewidget
python3 scripts/resolve_icon.py legacy app-1527355884
```

找不到映射、同一个平台 ID 命中多款应用、或映射存在但图片文件不在时，命令以非零状态退出，并在标准错误输出说明原因。标准输出同时给出 `missing_mapping`、`duplicate_mapping`、`missing_image` 或 `unknown_platform`。带上风格名时检查的是 `styles/<style>/<统一 ID>.png`，而不是官方图标。

校验：

```sh
python3 -m unittest discover -s tests
python3 scripts/catalog.py validate
python3 scripts/official_icons.py verify
```
