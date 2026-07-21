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
| Vercel AI Gateway 份额 | `site/data/vercel_gateway.json` | 自动；官方公开 Export API，无需 key |
| GPU 租赁价格 | `site/data/gpu_prices.json` | 自动；Ornn 公开 API |
| SDK 下载量 | `site/data/sdk_downloads.json` | 自动；npm / PyPI |
| Codex / ChatGPT Agent 用户里程碑 | `site/data/codex_wau.json` | 自动；每日扫描 OpenAI 官方 RSS 与文章 |
| KOL / X / 播客观点 | `site/data/curated_signals.json` | 自动；按 URL、事件和展示摘要去重，从最近 3 天补足 |
| KOL 全量归档（弹窗「更多」） | `site/data/signals_archive.json` | 自动；按 URL 合并；`detail` 保留 feed 原文，`detail_zh` 保存模型提炼的中文要点 |
| KOL 深读（弹窗增强层） | `site/data/signal_details.json` | 自动；Radar 在 GitHub Actions 中为每日展示条目生成“摘要 + 判断/洞察”和来源简介 |
| 数据中心新闻 | `site/data/dc_news.json` | 自动；Google News RSS；按事件去重；中英界面分别展示 `title_zh` / `title_en` |
| ARR 估算 | `site/data/arr_checkpoints.json` | 事件驱动；来自 `arr-model/arr_source.json` |
| AI 数据中心容量 | `site/data/datacenters.json` | 半自动；来自 `data_centers/*.csv` |
| 算力订单 | `site/data/compute_deals.json` | 自动扫描 OpenAI RSS / Anthropic Newsroom；官方原文结构化提取 |

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

Codex 周活与算力订单：

- 每天扫描 OpenAI 官方 RSS；文章明确披露 Codex 或合并后的 ChatGPT/Codex 活跃用户数据时，自动更新 `site/data/codex_wau.json`。
- 算力订单由北京时间 06:30 的任务扫描 OpenAI 官方 RSS 与 Anthropic Newsroom；新官方文章通过模型按固定 JSON 口径提取并追加到逐笔表。
- 每个数据点保留产品范围与统计周期。纯 Codex、ChatGPT + Codex 合并口径，以及周活/月活不会被连接为同一序列；离散披露点之间不插值。
- 自动发现的新订单默认不计入 GW 汇总；确认合同状态、基础设施层级和重复口径后，再将 `capacity_counted` 改为 `true`。

## 口径边界

- ARR 是综合估算，不是公司披露收入，也不是审计数字。
- OpenRouter / Vercel 反映第三方路由渠道窗口，适合观察边际变化，不代表全市场总量。
- Vercel 模型榜保持每日 Top 10、Other 和最近 7 个数据日算术平均口径；模型历史、每日快照及 Lab 趋势均按官方 API 当前覆盖窗口全量重建，不混用旧页面抓取值。Lab Spend 图中的 Kimi 对应官方 `moonshotai` Lab 口径。
- 数据中心 `as_of` 对应当前 CSV 版本，不代表上游每天更新。
- Compute Deals 的 GW 是合同或合作容量，不代表已经投运；站点/云租约与芯片/系统框架可能重叠，不可跨层相加。金额也混合算力采购、租约和基础设施投资，不展示简单合计。
- `reports`、`news.pinned`、`news.blocklist` 当前不在 dashboard 展示。
- X 抓取依赖 GitHub Secret：`TWITTER_COOKIES`；cookie 不可用时保留上次有效 `feed-x.json`，不写空缓存。

## 自动筛选规则

OpenRouter：

- 06:30 更新可能早于上游日榜结算，10:00 仅自动补跑 OpenRouter，不需要人工触发。
- 页面和对外截图以 `latest_date` 判断新鲜度，不用 `as_of` 代替数据日期。

KOL / X / 播客：

- 卡片默认 4 条一句话；点卡片右上「更多 ▸」弹窗查看全量归档（每条保留可追溯原文，
  有 Radar 深读的条目标 📓 并优先显示深读；深读只有中文，卡片一句话保持中英双语）。
- 中文封面由模型基于当条最长可用材料单独提炼为 1–2 个完整句子（约 2–3 行），自然收尾且不做机械截断；X 使用完整推文，播客优先 transcript/节目页、缺失时退回 feed 简介。生成失败时依次退回已有完整中文摘要和固定主题判断。
- 「更多」弹窗正文始终优先显示中文：Radar 在线深读 > 模型提炼的中文要点 > 中文观点摘要；英文界面同样如此。
- 中文要点不是逐句翻译：保留核心事实、数字和观点，删除时间轴、章节、宣传、赞助和节目流程。
- 人物、演讲者或栏目介绍只在标题下方显示一行灰色小字；深读正文不重复“人物：”“栏目：”等背景介绍。
- Radar 每日在线为当期展示条目补充“核心摘要 + 判断/洞察”和人物/栏目简介，并将结果随数据一起提交、发布；不依赖本地文件或其他任务。
- 相同 URL 只保留一条；YouTube 链接保留 `v` 视频 ID，避免不同视频被错误合并。
- 同一人物、同一天、文本高度相似的内容按同一事件处理。
- 展示区按 URL、事件和观点摘要去重；当最新一天不足 4 条时，从 feed 最新日期起的最近 3 天候选与 archive 中补足。
- 英文关键词按完整词或短语匹配，避免 `compute` 误命中 `computer science`。
- 过滤弱相关回复；以 `@` 开头且信号不足的内容不进入展示区。
