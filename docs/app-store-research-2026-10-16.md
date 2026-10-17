# App Store 热门应用研究：2026-10-16

本次研究以 Apple App Store 的免费应用榜为主。采集中国、美国及另外 57 个地区的前 100 名，合计 **5,899 个上榜位置、2,526 个不同的 App Store ID**；中国榜单实际返回 99 项，其余地区各 100 项。另从 OneWidget 所在的 Apple 开发者账号核实 15 款应用，去重后候选共 **2,541 款**，目录收录 **2,000 款**。此前 1,000 款全部保留。

筛选规则：固定收录 OneWidget 开发者账号的全部 15 款应用；完整纳入中国和美国榜单；其他地区至少纳入前 20 名；剩余名额按跨地区上榜次数与名次加权排序，中国和美国权重为 2，其他地区为 1。它是**榜单快照样本**，不能解释为全球下载量前 2000，也不包含付费榜或仅在其他时段上榜的应用。

59 个地区：CN、US、JP、KR、IN、GB、DE、FR、BR、MX、CA、AU、ID、TR、SA、AE、ES、IT、NL、SE、PL、SG、TH、VN、TW、HK、MY、PH、ZA、NG、EG、AR、CL、CO、PE、UY、PT、BE、CH、AT、DK、NO、FI、IE、NZ、IL、PK、LK、NP、KE、GH、MA、TN、DZ、UA、RO、CZ、HU、GR。孟加拉国榜单本次未返回应用条目，因此未计入地区数。

每条入选记录均保留 App Store ID、Apple bundle ID、当时的名称、开发者、分类及上榜来源。榜单精简快照见 `data/app-store-snapshot-2026-10-16.json`，开发者账号快照见 `data/author-apps-2026-10-16.json`；可供各端使用的统一 ID 目录见 `metadata/apps.json`，便于人工查阅的同序表见 `metadata/apps.csv`。同一个 App Store ID 在多个地区出现时，bundle ID 未发现冲突。

## OneWidget 与作者应用

以 OneWidget 的 App Store ID `1527355884` 查询到 Apple 开发者账号 `1250290964`（Chengdu Reinvent Technology Co., Ltd.），再从该账号的美国和中国商店软件列表取并集，核实以下 15 款。其中 3 款 macOS 应用在“平台”栏标出；作者身份以 Apple 开发者账号为准，不凭应用名称猜测。

| 应用 | App Store ID | 平台 |
| --- | --- | --- |
| OneWidget | `1527355884` | iOS/iPadOS |
| OneBar | `1591163653` | macOS |
| OneBoard | `1263389963` | iOS/iPadOS |
| OneCalendar | `1540421652` | macOS |
| OneClock | `1257395357` | iOS/iPadOS |
| OneCoin | `6502965303` | iOS/iPadOS |
| OneDay | `1250290965` | iOS/iPadOS |
| OneGrow | `1601581768` | iOS/iPadOS |
| OneList | `1449484075` | iOS/iPadOS |
| OneMemory | `6763771883` | iOS/iPadOS |
| OneMockup | `1355476695` | iOS/iPadOS |
| OneMusic | `1631977822` | iOS/iPadOS |
| OneTodo | `1546530435` | iOS/iPadOS |
| OneWall | `1601581616` | macOS |
| Transparent Widget - OneWidget | `1557099892` | iOS/iPadOS |

OneWidget 的统一 ID 现为 `app_imone_onewidget`（由 bundle ID `app.imone.OneWidget` 生成），旧 ID `app-1527355884` 保留为 `legacyId`。对应的 Android `applicationId` 与 HarmonyOS `bundleName` 均为 `tech.onenice.onewidget`，来源及工程提交记录见 `metadata/platform-overrides.json`。这些开发者应用在采样的免费榜中均未上榜，故通过作者账号固定收录，而非伪造榜单名次。

## 榜单观察

除固定收录的作者应用外，按本次跨地区榜单分数排序的前 10 款如下。这只是本仓库的筛选分数，**不是全球下载量排名**。

| 顺序 | 应用 | 上榜地区数 | 统一 ID |
| --- | --- | ---: | --- |
| 1 | ChatGPT | 57 | `app-6448311069` |
| 2 | Google Gemini | 58 | `app-6477489729` |
| 3 | Claude by Anthropic | 57 | `app-6473753684` |
| 4 | CapCut | 56 | `app-1500855883` |
| 5 | Google Maps | 56 | `app-585027354` |
| 6 | Google | 58 | `app-284815942` |
| 7 | Gmail | 58 | `app-422689480` |
| 8 | Threads | 58 | `app-6446901002` |
| 9 | WhatsApp Messenger | 56 | `app-310633997` |
| 10 | Google Chrome | 56 | `app-535886823` |

上表的统一 ID 是本次研究当时使用的 `app-<App Store ID>`。目录后来改为 bundle ID 规则，这些旧 ID 仍可在 `legacyId` 中找到。

中国当时的前 10 名依次是：抖音商城、红果短剧、红果漫剧、大麦、豆包、千问、汽水音乐、学信网、国家网络身份认证、电子税务局。美国当时的前 10 名依次是：Muse from Meta、Vinted、ChatGPT、TikTok Pro、Amazon Prime Video、McDonald's、Claude、Threads、Google Gemini、PineDrama。两地榜单呈现不同的本地需求，因此没有只按跨地区重复次数选取。

入选 2,000 款中，1,599 款只在一个采样地区进入前 100，96 款在至少 10 个地区上榜，15 款为未上榜的作者应用。分类最多的是 Finance（395）、Shopping（291）、Utilities（240）、Travel（157）和 Entertainment（144）。这些是**入选目录的分类分布**，不能推断整个 App Store 或全球用户的品类偏好。

除 OneWidget 外，研究当时尚未核实这些应用的 Android package name 与 HarmonyOS bundle name，也没有逐图提示词。官方图标的后续下载和统一 ID 规则见 `docs/official-icons.md`。免费榜会随地区和时间变化，因此本快照应标注日期使用。

数据来源：Apple [RSS Builder](https://rss.marketingtools.apple.com/) 生成的各地区免费应用榜，例如 [中国榜](https://itunes.apple.com/cn/rss/topfreeapplications/limit=100/json) 和 [美国榜](https://itunes.apple.com/us/rss/topfreeapplications/limit=100/json)；Apple 的 [开发者账号软件列表（美国）](https://itunes.apple.com/lookup?id=1250290964&entity=software&limit=200&country=us) 与 [中国](https://itunes.apple.com/lookup?id=1250290964&entity=software&limit=200&country=cn)。Apple 的 [iTunes Search API 文档](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/)说明了 ID 查询及应用元数据用途。本次榜单快照本身只保存文本。其后下载的原图放在默认风格目录 `styles/original/`，说明见 [官方图标与跨平台映射](official-icons.md)，不记入本快照。
