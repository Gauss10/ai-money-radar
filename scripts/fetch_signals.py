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
import html
import json
import os
import re

from common import ROOT, load_json, save_json

FEEDS_DIR = os.path.join(ROOT, "feeds")
DISPLAY_LIMIT = 4
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
            "gpu", "compute", "debt", "offtake", "datacenter", "data center",
            "neocloud", "capex", "nvidia backstop", "infrastructure",
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


def classify(text):
    lower = clean_text(text).lower()
    best = None
    score = 0
    for rule in RULES:
        hits = sum(1 for kw in rule["keywords"] if kw in lower)
        if hits:
            cur = rule["score"] + hits
            score += cur
            if best is None or cur > best[0]:
                best = (cur, rule)
    if any(mark in lower for mark in ("$7t", "7t", "$", "trillion", "b tokens")):
        score += 3
    if any(mark in lower for mark in ("thanks", "coming right up", "means a lot")) and score < 10:
        score -= 5
    return score, (best[1] if best else None)


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
            score, rule = classify(f"{who} {text}")
            if not rule or score < 8:
                continue
            out.append({
                "date": date_part(tweet.get("created_at")),
                "who": who,
                "via": f"X · {rule['name']}",
                "via_en": f"X · {rule['name']}",
                "take": rule["take"],
                "take_en": rule["take_en"],
                "url": tweet.get("url") or "",
                "_score": score + min(int(tweet.get("like_count") or 0) / 50, 3),
                "_source": "x",
                "_raw": first_sentence(text),
            })
    return out


def make_podcast_candidates(feed):
    out = []
    for ep in (feed or {}).get("podcasts", []):
        title = clean_text(ep.get("title"))
        desc = clean_text(ep.get("description"))
        channel = ep.get("channel") or "Podcast"
        score, rule = classify(f"{channel} {title} {desc}")
        if not rule or score < 7:
            continue
        who = guess_person(title, channel)
        short_title = first_sentence(title, 54)
        out.append({
            "date": date_part(ep.get("pub_date")),
            "who": who,
            "via": f"{channel} · {short_title}",
            "via_en": f"{channel} · {short_title}",
            "take": rule["take"],
            "take_en": rule["take_en"],
            "url": ep.get("link") or "",
            "_score": score + (2 if ep.get("transcript_available") else 0),
            "_source": "podcast",
            "_raw": first_sentence(desc or title),
        })
    return out


def public_entry(entry):
    return {k: entry.get(k, "") for k in ("date", "who", "via", "via_en", "take", "take_en", "url")}


def dedupe(entries):
    seen = set()
    out = []
    for entry in entries:
        key = entry.get("url") or f"{entry.get('date')}|{entry.get('who')}|{entry.get('via')}"
        if key in seen:
            continue
        seen.add(key)
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


def target_display_day(candidates):
    days = sorted({parse_day(item.get("date")) for item in candidates}, reverse=True)
    days = [day for day in days if day != datetime.date.min]
    for day in days:
        if sum(1 for item in candidates if parse_day(item.get("date")) == day) >= DISPLAY_LIMIT:
            return day
    return days[0] if days else None


def main():
    x_feed = load_feed("feed-x.json")
    podcast_feed = load_feed("feed-podcasts.json")
    cur = load_json("curated_signals.json") or {}

    candidates = make_x_candidates(x_feed) + make_podcast_candidates(podcast_feed)
    candidates = dedupe(sorted(candidates, key=sort_key, reverse=True))
    display_day = target_display_day(candidates)
    display_pool = [
        item for item in candidates
        if display_day is None or parse_day(item.get("date")) == display_day
    ]

    old_display = cur.get("kol") or []
    old_archive = cur.get("kol_archive") or []
    display = dedupe(display_pool)[:DISPLAY_LIMIT]
    display_urls = {item.get("url") for item in display}

    archive_seed = [item for item in old_display if item.get("url") not in display_urls]
    archive_seed += old_archive
    archive_seed += [item for item in candidates if item.get("url") not in display_urls]
    archive = dedupe(archive_seed)[:ARCHIVE_LIMIT]

    out = {
        "as_of": str(datetime.date.today()),
        "note": (
            "自动 curated 的 KOL / podcast 观点（源：本仓库 Actions 生成的 X + 播客 feed；"
            "规则打分生成）。展示最新且候选数足够的一天；换下条目进入 kol_archive。"
        ),
        "kol": [public_entry(item) for item in display],
        "reports": cur.get("reports") or [],
        "kol_archive": [public_entry(item) for item in archive],
    }
    save_json("curated_signals.json", out)
    day_text = display_day.isoformat() if display_day else "n/a"
    print(f"  candidates: {len(candidates)}, display_day: {day_text}, display: {len(out['kol'])}, archive: {len(out['kol_archive'])}")
    for item in out["kol"]:
        print(f"  - {item['date']} {item['who']} | {item['via']}")


if __name__ == "__main__":
    main()
