# -*- coding: utf-8 -*-
"""Scan OpenAI's official news feed for disclosed Codex adoption milestones."""
import datetime as dt
import email.utils
import html
import re
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit, urlunsplit

from common import http_get, load_json, save_json


OPENAI_RSS = "https://openai.com/news/rss.xml"
SCAN_LIMIT = 100
USAGE_TERMS = (
    "weekly active user", "weekly user", "weekly codex user", "users every week", "users each week",
    "using codex every week", "using codex each week",
    "monthly active user", "monthly user", "active user",
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True, errors="replace")


def canonical_url(url):
    parts = urlsplit((url or "").strip())
    return urlunsplit((parts.scheme or "https", parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def strip_html(value):
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_date(value):
    if not value:
        return ""
    try:
        return email.utils.parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        match = re.search(r"20\d{2}-\d{2}-\d{2}", value)
        return match.group(0) if match else ""


def discover():
    root = ET.fromstring(http_get(OPENAI_RSS))
    rows = []
    for item in root.findall(".//item")[:SCAN_LIMIT]:
        rows.append({
            "url": canonical_url(item.findtext("link")),
            "title": strip_html(item.findtext("title") or ""),
            "summary": strip_html(item.findtext("description") or ""),
            "date": parse_date(item.findtext("pubDate")),
        })
    return rows


def fetch_article(item):
    # Jina is transport only; the citation remains the official OpenAI page.
    url = item["url"]
    raw = http_get("https://r.jina.ai/http://" + url.removeprefix("https://"))
    title_match = re.search(r"^Title:\s*(.+)$", raw, flags=re.M)
    return {
        **item,
        "title": strip_html(title_match.group(1)) if title_match else item.get("title", ""),
        "text": raw[:24000],
    }


def relevant(text):
    value = (text or "").lower()
    return "codex" in value and any(term in value for term in USAGE_TERMS)


def to_millions(number, unit):
    value = float(number.replace(",", ""))
    unit = unit.lower()
    if unit in {"b", "billion"}:
        return value * 1000
    if unit in {"k", "thousand"}:
        return value / 1000
    return value


def qualifier_label(qualifier, value_m):
    q = (qualifier or "").lower().strip()
    prefix = ">" if q in {"more than", "over", "at least"} else "~" if q in {"about", "approximately", "around", "nearly"} else ""
    return f"{prefix}{value_m:g}M"


def scope_for(context):
    text = context.lower()
    combined = "chatgpt" in text and bool(re.search(
        r"(?:chatgpt\s*(?:and|with|\+|&|/)\s*codex|codex\s*(?:and|with|\+|&|/)\s*chatgpt|combined|together|integrat)",
        text,
    ))
    if combined:
        return {
            "metric_key": "codex_chatgpt_combined_wau",
            "scope_zh": "ChatGPT + Codex\uff08\u5408\u5e76\u53e3\u5f84\uff09",
            "scope_en": "ChatGPT + Codex (combined)",
        }
    return {
        "metric_key": "codex_wau",
        "scope_zh": "Codex\uff08\u72ec\u7acb\u53e3\u5f84\uff09",
        "scope_en": "Codex (standalone)",
    }


def extract_points(item):
    text = re.sub(r"\s+", " ", item.get("text", ""))
    if not relevant(text):
        return []
    number = r"(?P<qual>more than|over|at least|about|approximately|around|nearly|~)?\s*(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>million|billion|thousand|[MBK])"
    synthetic = []
    for pattern in (
        re.compile(rf"weekly Codex users[^.\n]{{0,180}}?\bto\s+{number}", re.I),
        re.compile(rf"using Codex every week[^\n]{{0,220}}?that number[^.\n]{{0,100}}?(?:to\s+)?{number}", re.I),
    ):
        for match in pattern.finditer(text):
            qualifier = (match.group("qual") or "").strip()
            synthetic.append(f"Codex now has {qualifier} {match.group('num')} {match.group('unit')} weekly users.")
    if synthetic:
        text += " " + " ".join(synthetic)
    cadence = r"(?P<cadence>weekly active users|weekly users|monthly active users|monthly users|active users)"
    patterns = (
        re.compile(rf"(?P<context>(?:ChatGPT|Codex)[^.\n]{{0,220}}?){number}\s+{cadence}", re.I),
        re.compile(rf"{number}\s+(?:developers|people|users)?\s*(?P<context>[^.\n]{{0,120}}?Codex[^.\n]{{0,100}}?)(?P<cadence>every week|each week)", re.I),
    )
    found = []
    found_keys = set()
    for pattern in patterns:
        for match in pattern.finditer(text):
            context = match.group(0)
            if "codex" not in context.lower():
                continue
            value_m = to_millions(match.group("num"), match.group("unit"))
            cadence_value = match.group("cadence").lower()
            weekly = "week" in cadence_value
            scope = scope_for(context)
            if "chatgpt" in context.lower() and scope["metric_key"] == "codex_wau":
                # Both products appear, but the sentence does not explicitly say
                # the figure is combined. Ambiguous numbers must not be plotted.
                continue
            if not weekly:
                scope["metric_key"] = scope["metric_key"].replace("_wau", "_mau")
            point = {
                "date": item.get("date") or dt.date.today().isoformat(),
                "value_m": round(value_m, 3),
                "label": qualifier_label(match.group("qual"), value_m),
                "metric_key": scope["metric_key"],
                "period": "weekly_active_users" if weekly else "monthly_active_users",
                "scope_zh": scope["scope_zh"],
                "scope_en": scope["scope_en"],
                "source_title": f"OpenAI - {item.get('title', '').strip()}",
                "url": item["url"],
                "auto_discovered": True,
            }
            key = (point["metric_key"], point["date"], point["value_m"])
            if key not in found_keys:
                found_keys.add(key)
                found.append(point)
    best = {}
    for point in found:
        key = point["metric_key"]
        if key not in best or point["value_m"] > best[key]["value_m"]:
            best[key] = point
    return list(best.values())


def normalize_existing(payload):
    changed = False
    defaults = {
        "metric_key": "codex_wau",
        "period": "weekly_active_users",
        "scope_zh": "Codex\uff08\u72ec\u7acb\u53e3\u5f84\uff09",
        "scope_en": "Codex (standalone)",
    }
    for point in payload.get("points", []):
        for key, value in defaults.items():
            if key not in point:
                point[key] = value
                changed = True
    notes = {
        "note_zh": "\u4ec5\u8bb0\u5f55 OpenAI \u5b98\u65b9\u7684\u79bb\u6563\u62ab\u9732\u70b9\u3002\u4e0d\u540c\u4ea7\u54c1\u8303\u56f4\u6216\u7edf\u8ba1\u5468\u671f\u5206\u6210\u72ec\u7acb\u5e8f\u5217\uff0c\u4e0d\u8de8\u53e3\u5f84\u8fde\u7ebf\uff0c\u4e5f\u4e0d\u5bf9\u65e5\u671f\u63d2\u503c\u3002",
        "note_en": "Records only discrete official OpenAI disclosures. Product scopes and reporting periods remain separate series, with no cross-scope connection or date interpolation.",
    }
    for key, value in notes.items():
        if payload.get(key) != value:
            payload[key] = value
            changed = True
    return changed


def main():
    payload = load_json("codex_wau.json") or {"points": []}
    changed = normalize_existing(payload)
    state = load_json("codex_adoption_scan.json")
    rows = discover()

    if not state:
        state = {
            "as_of": dt.datetime.now(dt.timezone.utc).isoformat(),
            "seen": sorted(row["url"] for row in rows if row.get("url")),
            "pending": [],
            "source": OPENAI_RSS,
        }
        if changed:
            save_json("codex_wau.json", payload)
        save_json("codex_adoption_scan.json", state)
        print(f"  initialized with {len(state['seen'])} official links")
        return

    seen = set(state.get("seen", []))
    pending_urls = set(state.get("pending", []))
    by_url = {row["url"]: row for row in rows if row.get("url")}
    for url in pending_urls:
        by_url.setdefault(url, {"url": url, "title": "", "summary": "", "date": ""})

    additions = []
    next_pending = []
    for url, row in by_url.items():
        if url in seen and url not in pending_urls:
            continue
        try:
            article = fetch_article(row)
        except Exception as exc:
            print(f"  article failed: {url} | {exc}")
            next_pending.append(url)
            continue
        additions.extend(extract_points(article))
        seen.add(url)

    existing = {
        (point.get("metric_key", "codex_wau"), point["date"], point["value_m"], canonical_url(point["url"]))
        for point in payload.get("points", [])
    }
    additions = [point for point in additions if (
        point["metric_key"], point["date"], point["value_m"], canonical_url(point["url"])
    ) not in existing]
    if additions:
        payload["points"] = sorted(payload.get("points", []) + additions, key=lambda point: (point["date"], point["metric_key"]))
        payload["as_of"] = max(point["date"] for point in payload["points"])
        changed = True
        for point in additions:
            print(f"  new adoption point: {point['date']} {point['label']} {point['scope_en']}")
    if changed:
        save_json("codex_wau.json", payload)

    save_json("codex_adoption_scan.json", {
        "as_of": dt.datetime.now(dt.timezone.utc).isoformat(),
        "seen": sorted(seen),
        "pending": sorted(set(next_pending))[:100],
        "source": OPENAI_RSS,
    })
    print(f"  checked {len(by_url)} links; added {len(additions)}; pending {len(next_pending)}")


if __name__ == "__main__":
    main()
