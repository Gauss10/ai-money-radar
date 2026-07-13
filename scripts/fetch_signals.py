# -*- coding: utf-8 -*-
"""
Local X / podcast feeds -> site/data/curated_signals.json

数据源:
  feeds/feed-x.json
  feeds/feed-podcasts.json

策略:
  - 读取本仓库 GitHub Actions 生成的 X / podcast feed。
  - 用关键词打分筛选与 AI 变现相关的信号：token spend、GPU / compute、
    agent workflow、model routing、eval、moat 等。
  - 展示最新且候选数足够的一天；旧展示项进入 kol_archive；reports 原样保留。

说明:
  这是自动化 KOL 卡片，不替代人工深读。它优先保证每日线上更新不断档。
"""
import datetime
import difflib
import html
import json
import os
import re

from common import ROOT, load_json, save_json

FEEDS_DIR = os.path.join(ROOT, "feeds")
DISPLAY_LIMIT = 4
DISPLAY_LOOKBACK_DAYS = 3
ARCHIVE_LIMIT = 40

PEOPLE = [
    "Guillermo Rauch", "Dylan Patel", "Boris Cherny", "Cat Wu", "Amjad Masad",
    "Alessio Fanelli", "Greg Brockman", "Sam Altman", "Dario Amodei",
    "Demis Hassabis", "Jensen Huang", "Karen Hao", "Pat Dorsey",
    "Andrej Karpathy", "Sundar Pichai", "Satya Nadella", "Mark Zuckerberg",
]

RULES = [
    {
        "name": "token spend / model routing",
        "score": 9,
        "keywords": [
            "token spend", "spend share", "$ spend", "ai gateway", "gateway",
            "leaderboard", "trillions of tokens", "routing", "usage share",
        ],
        "take": "模型商业化要看真实路由和 $ spend 份额，而不是只看 benchmark；渠道份额能更早暴露谁在生产流量里变现。",
        "take_en": "Model monetization is better tracked through real routing and $ spend share than benchmarks; channel share reveals who is monetizing production traffic.",
    },
    {
        "name": "compute / GPU financing",
        "score": 8,
        "keywords": [
            "gpu", "compute", "debt", "offtake", "datacenter", "datacenters",
            "data center", "data centers",
            "neocloud", "capex", "nvidia backstop", "energy grid", "watts",
        ],
        "take": "算力竞争正在变成资本结构问题；GPU、数据中心、offtake 和融资成本共同决定哪些公司能参与 AI 扩张。",
        "take_en": "AI compute is becoming a capital-structure problem: GPUs, datacenters, offtake and financing costs decide who can scale.",
    },
    {
        "name": "agent workflow",
        "score": 8,
        "keywords": [
            "claude code", "coding agent", "autonomous coding", "agent manager",
            "symphony", "linear", "agents", "agentic", "workflow",
            "self-improving", "closed the loop", "coding ai", "shipping faster",
            "software as a whole", "apps and games",
        ],
        "take": "agent 价值正在从一次性生成转向长期工作流；状态管理、成本归因、工具调用和反馈闭环会决定 token 消耗与产品粘性。",
        "take_en": "Agent value is moving from one-shot generation to durable workflows; state, cost attribution, tool use and feedback loops drive token usage and stickiness.",
    },
    {
        "name": "model eval / switching",
        "score": 6,
        "keywords": [
            "eval", "benchmark", "llm-as-judge", "judge", "model review",
            "sonnet", "opus", "gemini", "gpt-5", "rubric",
        ],
        "take": "模型切换会越来越依赖团队自己的 eval；真实任务、人工偏好和失败模式比通用榜单更接近采购与路由决策。",
        "take_en": "Model switching will depend on team-specific evals; real tasks, human preferences and failure modes are closer to buying and routing decisions than generic leaderboards.",
    },
    {
        "name": "model ecosystem",
        "score": 5,
        "keywords": [
            "open model", "open-weight", "nemotron", "icml", "research",
            "datasets", "cuda", "nvidia papers",
        ],
        "take": "模型、数据集和研究工具会强化平台默认值；基础设施公司的 moat 正在从硬件延伸到研究与开发工作流。",
        "take_en": "Models, datasets and research tools reinforce platform defaults; infrastructure moats are extending from hardware into research and developer workflows.",
    },
    {
        "name": "AI moat / business model",
        "score": 5,
        "keywords": [
            "moat", "switching cost", "switching costs", "network effect",
            "network effects", "capital allocation", "reinvestment", "pricing",
            "unit economics", "revenue", "arr", "monetization",
        ],
        "take": "AI 应用最终仍要回到 moat、定价权和再投资空间；只靠模型调用或短期增长，很难形成可持续变现。",
        "take_en": "AI apps still need moats, pricing power and reinvestment runway; model access and short-term growth alone rarely create durable monetization.",
    },
]


def load_feed(filename):
    path = os.path.join(FEEDS_DIR, filename)
    if not os.path.exists(path):
        raise RuntimeError(f"missing local feed: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def clean_text(value):
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def first_sentence(text, max_len=120):
    text = clean_text(text)
    parts = re.split(r"(?<=[。！？.!?])\s+", text)
    out = parts[0] if parts and parts[0] else text
    if len(out) > max_len:
        out = out[:max_len].rstrip() + "..."
    return out


def has_keyword(text, keyword):
    pattern = rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def classify(text):
    lower = clean_text(text).lower()
    best = None
    score = 0
    for rule in RULES:
        hits = sum(1 for kw in rule["keywords"] if has_keyword(lower, kw))
        if hits:
            cur = rule["score"] + hits
            score += cur
            if best is None or cur > best[0]:
                best = (cur, rule)
    if any(mark in lower for mark in ("$7t", "7t", "$", "trillion", "b tokens")):
        score += 3
    if len(lower) < 240 and any(mark in lower for mark in ("thanks", "coming right up", "means a lot")) and score < 10:
        score -= 5
    return score, (best[1] if best else None)


TAKE_VARIANTS = {
    "compute / GPU financing": [
        {
            "key": "energy",
            "keywords": ("energy", "watts", "electron", "power grid", "electricity"),
            "take": "AI 基础设施的约束正向能源侧移动；当芯片和集群继续扩张，电网容量、供电周期与单位能耗会决定新增 token 供给。",
            "take_en": "AI infrastructure is becoming energy-constrained; grid capacity, power lead times and energy efficiency increasingly determine new token supply.",
        },
        {
            "key": "financing",
            "keywords": ("debt", "offtake", "financing", "loan", "backstop", "capital structure"),
            "take": "算力竞争正在变成资本结构问题；GPU、数据中心、offtake 和融资成本共同决定哪些公司能参与 AI 扩张。",
            "take_en": "AI compute is becoming a capital-structure problem: GPUs, datacenters, offtake and financing costs decide who can scale.",
        },
        {
            "key": "buildout",
            "keywords": ("datacenter", "datacenters", "data center", "data centers", "capex", "trillion", "ai factory"),
            "take": "AI 数据中心扩张已进入超大规模建设阶段；资本开支、供电和上线周期将共同约束推理供给的释放速度。",
            "take_en": "AI datacenter expansion is entering a hyperscale buildout phase; capex, power and commissioning timelines jointly constrain inference supply.",
        },
        {
            "key": "hardware",
            "keywords": ("gpu", "compute", "nvidia", "chip"),
            "take": "模型能力仍受底层计算效率与供给约束；硬件、系统软件和推理优化共同决定可交付的速度与成本。",
            "take_en": "Model economics still depend on compute efficiency and supply; hardware, systems software and inference optimization jointly determine speed and cost.",
        },
    ],
    "agent workflow": [
        {
            "key": "browser",
            "keywords": ("browser", "website", "web page", "read, click", "open any site"),
            "take": "浏览器正在成为 coding agent 的标准执行面；价值不只在读取网页，而在受控 sandbox 中完成点击、验证与跨应用操作。",
            "take_en": "The browser is becoming a standard execution surface for coding agents; the value lies in controlled clicking, validation and cross-app action inside a sandbox.",
        },
        {
            "key": "ui",
            "keywords": ("ui", "design system", "frontend", "prototype", "typeset"),
            "take": "AI 产品界面正在同时服务人类与 agent；可组合的设计系统和结构化 UI 会降低生成、修改与验证前端的成本。",
            "take_en": "AI interfaces increasingly serve both humans and agents; composable design systems and structured UI lower the cost of generating, editing and validating frontends.",
        },
        {
            "key": "runtime",
            "keywords": ("runtime", "formal spec", "deterministic", "resilient", "sandbox"),
            "take": "agent 越能自主改代码，底层 runtime 越需要确定性、隔离与恢复能力；更快的生成速度反而提高了工程约束的重要性。",
            "take_en": "As agents gain autonomy over code, runtimes need more determinism, isolation and recovery; faster generation raises the value of engineering constraints.",
        },
    ],
}


def take_for(rule, text):
    lower = clean_text(text).lower()
    for variant in TAKE_VARIANTS.get(rule["name"], []):
        if any(has_keyword(lower, keyword) for keyword in variant["keywords"]):
            return variant["take"], variant["take_en"], f"{rule['name']}:{variant['key']}"
    return rule["take"], rule["take_en"], rule["name"]


def short_name(name):
    name = re.sub(r"\s*\(.*?\)", "", name or "").strip()
    return name or "Unknown"


def guess_person(title, channel):
    text = f"{title} {channel}"
    for person in PEOPLE:
        if person.lower() in text.lower():
            return person
    m = re.search(r"\|\s*([^|(]+)", title or "")
    if m:
        return m.group(1).strip()
    return channel or "Podcast"


def date_part(value):
    return (value or str(datetime.date.today()))[:10]


def make_x_candidates(feed):
    out = []
    for account in (feed or {}).get("x", []):
        who = short_name(account.get("name") or account.get("handle"))
        for tweet in account.get("tweets", []):
            text = clean_text(tweet.get("text"))
            score, rule = classify(text)
            if not rule or score < 8:
                continue
            if text.startswith("@") and score < 12:
                continue
            take, take_en, theme = take_for(rule, text)
            out.append({
                "date": date_part(tweet.get("created_at")),
                "who": who,
                "via": f"X · {rule['name']}",
                "via_en": f"X · {rule['name']}",
                "take": take,
                "take_en": take_en,
                "url": tweet.get("url") or "",
                "_score": score + min(int(tweet.get("like_count") or 0) / 50, 3),
                "_source": "x",
                "_raw": first_sentence(text),
                "_theme": theme,
            })
    return out


def make_podcast_candidates(feed):
    out = []
    for ep in (feed or {}).get("podcasts", []):
        title = clean_text(ep.get("title"))
        desc = clean_text(ep.get("description"))
        channel = ep.get("channel") or "Podcast"
        source_text = f"{title} {desc}"
        score, rule = classify(source_text)
        if not rule or score < 7:
            continue
        take, take_en, theme = take_for(rule, source_text)
        who = guess_person(title, channel)
        short_title = first_sentence(title, 54)
        out.append({
            "date": date_part(ep.get("pub_date")),
            "who": who,
            "via": f"{channel} · {short_title}",
            "via_en": f"{channel} · {short_title}",
            "take": take,
            "take_en": take_en,
            "url": ep.get("link") or "",
            "_score": score + (2 if ep.get("transcript_available") else 0),
            "_source": "podcast",
            "_raw": first_sentence(desc or title),
            "_theme": theme,
        })
    return out


def public_entry(entry):
    return {k: entry.get(k, "") for k in ("date", "who", "via", "via_en", "take", "take_en", "url")}


SEMANTIC_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "can", "for", "from", "has",
    "in", "is", "it", "now", "of", "on", "or", "that", "the", "this", "to",
    "with", "your", "you", "ai", "agent", "agents",
}


def semantic_tokens(entry):
    text = clean_text(f"{entry.get('who', '')} {entry.get('_raw', '')}").lower()
    return {
        token for token in re.findall(r"[a-z0-9]+(?:[.+-][a-z0-9]+)*", text)
        if len(token) > 2 and token not in SEMANTIC_STOPWORDS
    }


def same_event(left, right):
    if parse_day(left.get("date")) != parse_day(right.get("date")):
        return False
    if left.get("who") != right.get("who"):
        return False
    if not clean_text(left.get("_raw")) or not clean_text(right.get("_raw")):
        return False
    left_tokens, right_tokens = semantic_tokens(left), semantic_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    jaccard = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    sequence = difflib.SequenceMatcher(None, left.get("_raw", ""), right.get("_raw", "")).ratio()
    return jaccard >= 0.35 or sequence >= 0.72


def dedupe(entries, unique_take=False):
    seen_urls = set()
    seen_takes = set()
    out = []
    for entry in entries:
        key = entry.get("url") or f"{entry.get('date')}|{entry.get('who')}|{entry.get('via')}"
        take_key = clean_text(entry.get("take")).casefold()
        if key in seen_urls or any(same_event(entry, prior) for prior in out):
            continue
        if unique_take and take_key and take_key in seen_takes:
            continue
        seen_urls.add(key)
        if take_key:
            seen_takes.add(take_key)
        out.append(entry)
    return out


def parse_day(value):
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return datetime.date.min


def effective_score(entry):
    score = float(entry.get("_score", 0))
    day = parse_day(entry.get("date"))
    today = datetime.date.today()
    age = max((today - day).days, 0) if day != datetime.date.min else 999
    if age <= 2:
        score += 3
    elif age <= 5:
        score += 1
    elif age > 5:
        score -= min((age - 5) * 4, 18)
    return score


def sort_key(entry):
    return (effective_score(entry), entry.get("date", ""), entry.get("who", ""))


def recent_display_pool(candidates, lookback_days=DISPLAY_LOOKBACK_DAYS):
    days = [parse_day(item.get("date")) for item in candidates]
    days = [day for day in days if day != datetime.date.min]
    if not days:
        return []
    latest_day = max(days)
    cutoff = latest_day - datetime.timedelta(days=lookback_days - 1)
    pool = [
        item for item in candidates
        if cutoff <= parse_day(item.get("date")) <= latest_day
    ]
    return sorted(
        pool,
        key=lambda item: (parse_day(item.get("date")), effective_score(item)),
        reverse=True,
    )


def select_display(candidates, historical=()):
    merged = dedupe(list(candidates) + list(historical))
    return dedupe(recent_display_pool(merged), unique_take=True)[:DISPLAY_LIMIT]


def main():
    x_feed = load_feed("feed-x.json")
    podcast_feed = load_feed("feed-podcasts.json")
    cur = load_json("curated_signals.json") or {}

    candidates = make_x_candidates(x_feed) + make_podcast_candidates(podcast_feed)
    candidates = dedupe(sorted(candidates, key=sort_key, reverse=True))

    old_display = cur.get("kol") or []
    old_archive = cur.get("kol_archive") or []
    display = select_display(candidates, old_display + old_archive)
    display_urls = {item.get("url") for item in display}

    archive_seed = [item for item in old_display if item.get("url") not in display_urls]
    archive_seed += old_archive
    archive_seed += [item for item in candidates if item.get("url") not in display_urls]
    archive = dedupe(archive_seed)[:ARCHIVE_LIMIT]

    out = {
        "as_of": str(datetime.date.today()),
        "note": (
            "自动 curated 的 KOL / podcast 观点（源：本仓库 Actions 生成的 X + 播客 feed；"
            "规则打分生成）。从 feed 与历史候选的最近 3 天内选择，展示摘要去重；"
            "换下条目进入 kol_archive。"
        ),
        "kol": [public_entry(item) for item in display],
        "reports": cur.get("reports") or [],
        "kol_archive": [public_entry(item) for item in archive],
    }
    save_json("curated_signals.json", out)
    display_dates = [item["date"] for item in out["kol"]]
    window_text = f"{min(display_dates)}..{max(display_dates)}" if display_dates else "n/a"
    print(f"  candidates: {len(candidates)}, display_window: {window_text}, display: {len(out['kol'])}, archive: {len(out['kol_archive'])}")
    for item in out["kol"]:
        print(f"  - {item['date']} {item['who']} | {item['via']}")


if __name__ == "__main__":
    main()
