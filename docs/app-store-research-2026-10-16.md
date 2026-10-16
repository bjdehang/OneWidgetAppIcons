# App Store 热门应用研究：2026-10-16

本次研究以 Apple App Store 的免费应用榜为主。采集中国、美国及另外 29 个地区的前 100 名，合计 **3,099 个上榜位置、1,560 个不同的 App Store ID**；中国榜单实际返回 99 项，其余地区各 100 项。目录选出 **1,000 款**。

筛选规则：完整纳入中国和美国榜单；其他地区至少纳入前 20 名；剩余名额按跨地区上榜次数与名次加权排序，中国和美国权重为 2，其他地区为 1。这个规则兼顾中美重点与各地本地应用。它是**榜单快照样本**，不能解释为全球下载量前 1000，也不包含付费榜或仅在其他时段上榜的应用。

31 个地区：CN、US、JP、KR、IN、GB、DE、FR、BR、MX、CA、AU、ID、TR、SA、AE、ES、IT、NL、SE、PL、SG、TH、VN、TW、HK、MY、PH、ZA、NG、EG。

每条入选记录均保留 App Store ID、Apple bundle ID、当时的名称、开发者、分类、上榜地区及名次。原始榜单的精简快照见 `data/app-store-snapshot-2026-10-16.json`；可供各端使用的统一 ID 目录见 `metadata/apps.json`，便于人工查阅的同序表见 `metadata/apps.csv`。同一个 App Store ID 在多个地区出现时，bundle ID 未发现冲突。

## 榜单观察

按本次跨地区榜单分数排序的前 10 款如下。这里的顺序只是本仓库的筛选分数，**不是全球下载量排名**。

| 顺序 | 应用 | 上榜地区数 | 统一 ID |
| --- | --- | ---: | --- |
| 1 | ChatGPT | 29 | `app-6448311069` |
| 2 | Google Gemini | 30 | `app-6477489729` |
| 3 | Claude by Anthropic | 29 | `app-6473753684` |
| 4 | CapCut | 29 | `app-1500855883` |
| 5 | Gmail | 30 | `app-422689480` |
| 6 | Google | 30 | `app-284815942` |
| 7 | Threads | 30 | `app-6446901002` |
| 8 | Google Maps | 29 | `app-585027354` |
| 9 | WhatsApp Messenger | 29 | `app-310633997` |
| 10 | Google Chrome | 29 | `app-535886823` |

中国当时的前 10 名依次是：抖音商城、红果短剧、红果漫剧、大麦、豆包、千问、汽水音乐、学信网、国家网络身份认证、电子税务局。美国当时的前 10 名依次是：Muse from Meta、Vinted、ChatGPT、TikTok Pro、Amazon Prime Video、McDonald's、Claude、Threads、Google Gemini、PineDrama。两地榜单呈现明显不同的本地需求，因此没有只按跨地区重复次数选取。

入选 1000 款中，770 款只在一个采样地区进入前 100，66 款在至少 10 个地区上榜。分类最多的是 Finance（190）、Shopping（143）、Utilities（105）、Entertainment（85）和 Productivity（69）。这些是**入选目录的分类分布**，不能推断整个 App Store 或全球用户的品类偏好。

目前尚未核实这些应用的 Android package name、HarmonyOS bundle name，也未制作图标或生成逐图提示词。跨平台映射和素材制作需按 `docs/catalog-guide.md` 的规则逐项补充。免费榜会随地区和时间变化，因此本快照应标注日期使用。

数据来源：Apple [RSS Builder](https://rss.marketingtools.apple.com/) 生成的各地区免费应用榜，例如 [中国榜](https://itunes.apple.com/cn/rss/topfreeapplications/limit=100/json) 和 [美国榜](https://itunes.apple.com/us/rss/topfreeapplications/limit=100/json)。Apple 的 [iTunes Search API 文档](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/)说明了 ID 查询及应用元数据用途。此仓库只保存榜单文本元数据，不保存 Apple 提供的宣传图标。
