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
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")  # Windows GBK 控制台遇到 emoji 不崩

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


def compact_cover_summary(text, fallback="", max_len=105):
    """Compress a model summary to roughly 2-3 dashboard lines."""
    summary = clean_text(text) or clean_text(fallback)
    if len(summary) <= max_len:
        return summary
    prefix = summary[:max_len]
    min_cut = int(max_len * 0.65)
    for separators in ("。！？；", "，,;"):
        cut = max(prefix.rfind(mark) for mark in separators)
        if cut >= min_cut:
            return prefix[:cut].rstrip("，,；;：: ") + "…"
    return prefix[:-1].rstrip("，,；;：: ") + "…"


def excerpt(text, max_len=600):
    """原文摘录（弹窗展开层用；比 first_sentence 保留更多上下文）"""
    text = clean_text(text)
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "..."
    return text


def deep_source(text, max_len=6000):
    """供在线深读使用的较长材料；不会直接展示到页面。"""
    return excerpt(text, max_len)


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
                "detail": excerpt(text),
                "_score": score + min(int(tweet.get("like_count") or 0) / 50, 3),
                "_source": "x",
                "_raw": first_sentence(text),
                "_theme": theme,
                "_deep_source": deep_source(text),
            })
    return out


def make_podcast_candidates(feed):
    out = []
    for ep in (feed or {}).get("podcasts", []):
        title = clean_text(ep.get("title"))
        desc = clean_text(ep.get("description"))
        channel = ep.get("channel") or "Podcast"
        source_text = f"{title} {desc}"
        transcript = clean_text(ep.get("transcript"))
        source_for_deep = transcript if len(transcript) >= 1200 else source_text
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
            "detail": excerpt(desc or title),
            "_score": score + (2 if ep.get("transcript_available") else 0),
            "_source": "podcast",
            "_raw": first_sentence(desc or title),
            "_theme": theme,
            "_deep_source": deep_source(source_for_deep),
        })
    return out


def public_entry(entry):
    return {k: entry.get(k, "") for k in
            ("date", "who", "via", "via_en", "take", "take_en", "take_zh",
             "url", "detail", "detail_zh")}


def archive_same_event(left, right, day_window=2):
    """归档层语义去重：同一人、日期相近、摘录高度相似 → 同一事件"""
    if left.get("who") != right.get("who"):
        return False
    ld, rd = parse_day(left.get("date")), parse_day(right.get("date"))
    if ld == datetime.date.min or rd == datetime.date.min or abs((ld - rd).days) > day_window:
        return False
    lt, rt = clean_text(left.get("detail") or ""), clean_text(right.get("detail") or "")
    if not lt or not rt:
        return False
    probe = {"date": left.get("date"), "who": left.get("who"), "_raw": lt[:200]}
    other = {"date": left.get("date"), "who": right.get("who"), "_raw": rt[:200]}
    return same_event(probe, other)


TIMELINE_RE = re.compile(r"^\s*(?:时间轴|章节|timestamps?)\s*[:：]?\s*$", re.I)
TIMECODE_RE = re.compile(r"^\s*\d{1,2}:\d{2}(?::\d{2})?\s+")
INTRO_RE = re.compile(
    r"^(?:人物(?:简介)?|栏目(?:与作者|与嘉宾)?|嘉宾(?:简介)?|作者(?:简介)?|机构(?:简介)?|来源背景)"
    r"[:：][^\n]*(?:\n+|$)"
)
OPENROUTER_MODELS = (
    "deepseek/deepseek-v4-flash",
    "nvidia/nemotron-3-ultra-550b-a55b-20260604:free",
    "poolside/laguna-m.1-20260312:free",
)


def normalize_signal_url(url):
    raw = (url or "").strip()
    try:
        parts = urlsplit(raw)
        host = (parts.hostname or "").removeprefix("www.")
        if host == "youtube.com" and parts.path == "/watch":
            video_id = dict(parse_qsl(parts.query)).get("v")
            if video_id:
                return urlunsplit((parts.scheme, parts.netloc, parts.path,
                                   urlencode({"v": video_id}), ""))
        return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
    except ValueError:
        return raw.split("?")[0].rstrip("/")


def get_openrouter_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    try:
        from common import env
        return env("OPENROUTER_API_KEY")
    except Exception:
        return None


def request_model(key, model, prompt, max_tokens):
    import urllib.request

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps({
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        payload = json.loads(response.read())
    return (payload.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()


def clean_generated_summary(value):
    """清理模型偶尔保留的标题、时间轴和推广信息。"""
    lines = []
    for line in (value or "").splitlines():
        text = line.strip()
        if not text or TIMELINE_RE.match(text) or TIMECODE_RE.match(text):
            continue
        if re.search(r"(?:订阅|subscribe).*(?:频道|channel|更多|more)", text, re.I):
            continue
        lines.append(text)
    summary = " ".join(lines)
    summary = re.sub(r"^(?:摘要|要点|核心要点)\s*[:：]\s*", "", summary)
    summary = re.sub(r"\s*#[A-Za-z0-9_\u4e00-\u9fff-]+", "", summary)
    return re.sub(r"\s+", " ", summary).strip()


def summarize_details(items, limit=20, force=False):
    """
    用 OpenRouter 模型把 feed 摘录提炼为中文要点（detail_zh），而非逐句翻译。
    日常只处理新增条目；--refresh-summaries 可强制重做现有摘要。
    无 key / 请求失败时静默跳过，前端回退到中文观点摘要。
    """
    key = get_openrouter_key()
    if not key:
        return 0
    todo = [
        it for it in items
        if (it.get("detail") or "").strip()
        and (force or not (it.get("detail_zh") or "").strip())
    ]
    done = 0
    for it in todo[:limit]:
        prompt = (
            "你是 AI 投资日报编辑。根据下面来自 X 或播客 feed 的原始内容，直接提炼中文要点，不要逐句翻译。\n"
            "要求：\n"
            "1. 用 2-3 句、约 100-220 个中文字概括最重要的事实、数字和观点；\n"
            "2. 保留必要的公司、产品、人名和关键数字，但不复述人物履历；\n"
            "3. 删除欢迎语、宣传语、赞助、订阅、hashtags、时间轴、章节和节目流程；\n"
            "4. 不添加原文没有的事实，也不要输出标题、列表、'摘要'或解释。\n\n"
            f"来源：{it.get('who', '')} · {it.get('via', '')}\n"
            f"原始内容：{it['detail']}"
        )
        for model in OPENROUTER_MODELS:
            try:
                text = clean_generated_summary(request_model(key, model, prompt, 900))
                if text:
                    it["detail_zh"] = text
                    done += 1
                    break
            except Exception:
                continue
    return done


def clean_deep_detail(value):
    text = (value or "").strip()
    while INTRO_RE.match(text):
        text = INTRO_RE.sub("", text, count=1).strip()
    lines = [
        line.strip() for line in text.splitlines()
        if line.strip() and not TIMELINE_RE.match(line) and not TIMECODE_RE.match(line)
    ]
    return "\n\n".join(lines)


def parse_model_json(value):
    text = (value or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def generate_deep_read(item, key):
    source = (item.get("_deep_source") or item.get("detail") or "").strip()
    if len(source) < 280:
        return None
    prompt = (
        "你是 AI Money Radar 的研究编辑。请基于给定材料生成中文深读，风格接近简洁的专业投研日报。\n"
        "只输出 JSON：{\"title\":\"...\",\"bio\":\"...\",\"detail\":\"...\"}\n"
        "要求：\n"
        "1. detail 先用 2 段提炼核心事实、数字和观点，再用‘判断：’开头写 1 段洞察；总计约 280-500 字。\n"
        "2. 判断需解释商业或产业含义、信息局限和后续应跟踪的指标，不能只重复原文。\n"
        "3. 不添加材料没有的事实；删除欢迎语、宣传、赞助、订阅、hashtags、时间轴和节目流程。\n"
        "4. detail 不介绍人物或栏目；人物/栏目背景只写在 bio，控制在 35-80 字。\n"
        "5. title 是 15-35 字的中文要点标题，不带序号。\n\n"
        f"日期：{item.get('date', '')}\n"
        f"作者或栏目：{item.get('who', '')}\n"
        f"来源：{item.get('via', '')}\n"
        f"已有中文要点：{item.get('detail_zh') or item.get('take') or ''}\n"
        f"原始材料：{source}"
    )
    for model in OPENROUTER_MODELS:
        try:
            result = parse_model_json(request_model(key, model, prompt, 1800))
            if not result:
                continue
            detail = clean_deep_detail(result.get("detail"))
            bio = clean_text(result.get("bio"))
            title = clean_text(result.get("title"))
            if len(detail) < 120 or "判断" not in detail or not re.search(r"[一-鿿]{20,}", detail):
                continue
            return {"detail": detail, "bio": bio, "title": title}
        except Exception:
            continue
    return None


def update_online_deep_reads(entries, limit=4):
    key = get_openrouter_key()
    if not key:
        return 0, 0
    current = load_json("signal_details.json") or {}
    details = current.get("details") or {}
    bios = current.get("bios") or {}
    deep_count = 0
    bio_count = 0
    for item in entries[:limit]:
        url = normalize_signal_url(item.get("url"))
        who = item.get("who") or ""
        needs_detail = bool(url) and url not in details
        needs_bio = bool(who) and who not in bios
        if not needs_detail and not needs_bio:
            continue
        generated = generate_deep_read(item, key)
        if not generated:
            continue
        if needs_detail:
            details[url] = {
                "detail": generated["detail"],
                "title": generated["title"],
                "src": f"AI Money Radar 在线深读 {item.get('date') or datetime.date.today()}",
                "origin": "radar-online",
            }
            deep_count += 1
        if needs_bio and generated["bio"]:
            bios[who] = generated["bio"]
            bio_count += 1
    save_json("signal_details.json", {
        "note": "AI Money Radar 云端深读层：GitHub Actions 按 URL 生成 details，并按 who 维护人物/栏目背景 bios。",
        "bios": bios,
        "details": details,
    })
    return deep_count, bio_count


def update_signals_archive(entries):
    """
    site/data/signals_archive.json: 只增不减的全量观点归档（弹窗「更多」层数据源）。
    按 URL 合并（detail/detail_zh 保留更长者）→ 语义去重（同人近日相似内容并条）
    → 缺失中文要点的条目由模型自动提炼。
    展示条目的深读与来源简介由本脚本在线生成到 signal_details.json。
    """
    cur = load_json("signals_archive.json") or {}
    merged = {item.get("url") or f"{item.get('date')}|{item.get('who')}": item
              for item in cur.get("items", [])}
    for entry in entries:
        pub = public_entry(entry)
        key = pub.get("url") or f"{pub.get('date')}|{pub.get('who')}"
        old = merged.get(key)
        if old:
            for f in ("detail", "detail_zh"):
                if len(old.get(f) or "") > len(pub.get(f) or ""):
                    pub[f] = old[f]
        merged[key] = pub
    # 语义级去重：保留摘录更长（信息更多）的那条
    kept = []
    for item in sorted(merged.values(), key=lambda x: -len(x.get("detail") or "")):
        if not any(archive_same_event(item, prior) for prior in kept):
            kept.append(item)
    summarized = summarize_details(kept)
    items = sorted(kept, key=lambda x: (x.get("date", ""), x.get("who", "")), reverse=True)
    save_json("signals_archive.json", {"as_of": str(datetime.date.today()), "items": items})
    return len(items), summarized


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
            "规则打分选取、模型提炼封面摘要）。从 feed 与历史候选的最近 3 天内选择，展示摘要去重；"
            "换下条目进入 kol_archive；全量历史在 signals_archive.json。"
        ),
        "kol": [public_entry(item) for item in display],
        "reports": cur.get("reports") or [],
        "kol_archive": [public_entry(item) for item in archive],
    }
    total, summarized = update_signals_archive(display + archive + candidates)
    archive_data = load_json("signals_archive.json") or {}
    archive_by_url = {item.get("url"): item for item in archive_data.get("items", [])}
    deep_inputs = []
    for item in display:
        enriched = dict(item)
        stored = archive_by_url.get(item.get("url")) or {}
        enriched["detail"] = stored.get("detail") or item.get("detail") or ""
        enriched["detail_zh"] = stored.get("detail_zh") or item.get("detail_zh") or ""
        enriched["take_zh"] = compact_cover_summary(
            enriched["detail_zh"], item.get("take") or ""
        )
        deep_inputs.append(enriched)
    out["kol"] = [public_entry(item) for item in deep_inputs]
    deep_reads, bios = update_online_deep_reads(deep_inputs)
    save_json("curated_signals.json", out)
    display_dates = [item["date"] for item in out["kol"]]
    window_text = f"{min(display_dates)}..{max(display_dates)}" if display_dates else "n/a"
    print(f"  candidates: {len(candidates)}, display_window: {window_text}, display: {len(out['kol'])}, "
          f"archive: {len(out['kol_archive'])}, full_archive: {total}, summarized: {summarized}, "
          f"deep_reads: {deep_reads}, bios: {bios}")
    for item in out["kol"]:
        print(f"  - {item['date']} {item['who']} | {item['via']}")


def refresh_archive_summaries():
    archive = load_json("signals_archive.json") or {}
    items = archive.get("items", [])
    done = summarize_details(items, limit=50, force=True)
    save_json("signals_archive.json", {
        "as_of": archive.get("as_of") or str(datetime.date.today()),
        "items": items,
    })
    print(f"  refreshed summaries: {done}/{sum(bool(item.get('detail')) for item in items)}")


if __name__ == "__main__":
    if "--refresh-summaries" in sys.argv:
        refresh_archive_summaries()
    else:
        main()
