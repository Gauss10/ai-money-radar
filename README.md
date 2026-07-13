# AI Money Radar

AI Money Radar 是一个 AI 变现跟踪 dashboard，用来观察模型用量、路由份额、GPU 租赁价格、Frontier Lab ARR 估算和 AI 数据中心建设节奏。

线上地址：

- 页面：https://gauss10.github.io/ai-money-radar/
- 仓库：https://github.com/gauss10/ai-money-radar

## 本地运行

```powershell
cd "C:\Users\xyzheng\OneDrive\1-资料\鼎晖-PE\ZXY-PA\0-整体思考\3-research-engine-AI\AI Daily\ai-money-radar\scripts"
python update_all.py

cd ..\site
python -m http.server 8000
```

浏览器打开：

```text
http://localhost:8000
```

## 自动更新

GitHub Actions 位于 `.github/workflows/daily.yml`：

- 每天北京时间 **06:30** 自动抓取全部数据并部署；**10:00** 仅补跑 OpenRouter，用于补齐延迟发布的日榜，不覆盖早间生成的 KOL 数据。
- 手动 `Run workflow` 可以立即更新。
- 普通 `push main` 只重新部署页面，不重新抓数。
- OpenRouter 数据依赖 GitHub Secret：`OPENROUTER_API_KEY`。
- OpenRouter 的 `as_of` 是 API 请求时间，`latest_date` 才是实际最新数据日；页面状态显示 `latest_date`。

## 数据文件

| 模块 | 输出文件 | 更新方式 |
|---|---|---|
| OpenRouter 模型用量 | `site/data/openrouter_daily.json` | 自动；需要 API key |
| Vercel AI Gateway 份额 | `site/data/vercel_gateway.json` | 自动；公开页面数据 |
| GPU 租赁价格 | `site/data/gpu_prices.json` | 自动；Ornn 公开 API |
| SDK 下载量 | `site/data/sdk_downloads.json` | 自动；npm / PyPI |
| KOL / X / 播客观点 | `site/data/curated_signals.json` | 自动；先生成本地 feed，再按事件和 URL 去重后筛选 |
| 数据中心新闻 | `site/data/dc_news.json` | 自动；Google News RSS；按事件去重；中英界面分别展示 `title_zh` / `title_en` |
| ARR 估算 | `site/data/arr_checkpoints.json` | 事件驱动；来自 `arr-model/arr_source.json` |
| AI 数据中心容量 | `site/data/datacenters.json` | 半自动；来自 `data_centers/*.csv` |

## 人工维护点

ARR：

- 编辑 `arr-model/arr_source.json`。
- `estimates` 是月度估算锚点。
- `extrapolation` 是年底预测区间。
- `checkpoints` 是公开报道证据点，只用于图上标记，不直接参与拟合。

数据中心：

- 从 Epoch AI 下载最新 `AI Data Centers` CSV。
- 覆盖 `data_centers/*.csv`。
- 运行 `scripts/update_all.py` 生成 `site/data/datacenters.json`。

## 口径边界

- ARR 是综合估算，不是公司披露收入，也不是审计数字。
- OpenRouter / Vercel 反映第三方路由渠道窗口，适合观察边际变化，不代表全市场总量。
- 数据中心 `as_of` 对应当前 CSV 版本，不代表上游每天更新。
- `reports`、`news.pinned`、`news.blocklist` 当前不在 dashboard 展示。
- X 抓取依赖 GitHub Secret：`TWITTER_COOKIES`；cookie 不可用时保留上次有效 `feed-x.json`，不写空缓存。

## 自动筛选规则

OpenRouter：

- 06:30 更新可能早于上游日榜结算，10:00 仅自动补跑 OpenRouter，不需要人工触发。
- 页面和对外截图以 `latest_date` 判断新鲜度，不用 `as_of` 代替数据日期。

KOL / X / 播客：

- 相同 URL 只保留一条。
- 同一人物、同一天、文本高度相似的内容按同一事件处理。
- 不同作者或不同事件即使映射到相同观点摘要也分别保留；相同 URL 或同一人物同一天的高度相似事件仍然去重。
- 英文关键词按完整词或短语匹配，避免 `compute` 误命中 `computer science`。
- 过滤弱相关回复；以 `@` 开头且信号不足的内容不进入展示区。
