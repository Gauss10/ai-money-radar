# -*- coding: utf-8 -*-
"""
AI Signal 日报 -> site/data/signal_details.json（本地增强层，仅本地运行）

按 URL 把日报里的深读内容（来源背景 + 核心要点 + 判断/洞察/启发）匹配到
signals_archive.json / curated_signals.json 里的条目上。弹窗展开时，
有深读的条目优先显示深读，没有的显示 feed 原文摘录。

设计约束:
  - 云端 Actions 不运行本脚本、不写 signal_details.json，避免写冲突。
  - 输出按 URL 键控，日报重复覆盖时保留最新日报的版本。
  - 手动在 signal_details.json 里加 "lock": true 的条目不会被覆盖。

用法: python enrich_signals_from_digests.py
      （日报目录默认为仓库同级的 ../ai-signal/digests，可用 DIGESTS_DIR 环境变量覆盖）
"""
import glob
import json
import os
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from common import ROOT, load_json, save_json

DIGESTS_DIR = os.environ.get(
    "DIGESTS_DIR",
    os.path.normpath(os.path.join(ROOT, "..", "ai-signal", "digests")),
)

URL_RE = re.compile(r"\((https?://[^)\s]+)\)")
HEAD_RE = re.compile(r"^###\s+(.+)$", re.M)
BOUNDARY_RE = re.compile(r"^#{2,3}\s+.+$", re.M)
VERDICT_RE = re.compile(r"^\*\*(判断|洞察|启发)[:：]\*\*", re.M)
INTRO_RE = re.compile(
    r"^(?:人物(?:简介)?|栏目(?:与作者|与嘉宾)?|嘉宾(?:简介)?|作者(?:简介)?|机构(?:简介)?|来源背景)"
    r"[:：][^\n]*(?:\n+|$)"
)


def normalize_url(url):
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


def clean_deep_detail(value):
    text = (value or "").strip()
    while INTRO_RE.match(text):
        text = INTRO_RE.sub("", text, count=1).strip()
    return text


def parse_digest(path):
    """返回 [{urls, title, body}]，body = 正文段落 + 判断段（去掉来源/链接行）"""
    with open(path, encoding="utf-8") as digest_file:
        text = digest_file.read()
    date = os.path.basename(path)[:10]
    sections = []
    heads = list(HEAD_RE.finditer(text))
    for i, m in enumerate(heads):
        start = m.end()
        next_boundary = BOUNDARY_RE.search(text, m.end())
        end = next_boundary.start() if next_boundary else len(text)
        block = text[start:end]
        urls = [normalize_url(u) for u in URL_RE.findall(block)]
        if not urls:
            continue
        lines = []
        for para in block.split("\n"):
            p = para.strip()
            if not p or p.startswith(("来源", "**链接", "链接")):
                continue
            # 去掉行内 markdown 链接，保留文字
            p = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", p)
            lines.append(p)
        body = clean_deep_detail("\n".join(lines))
        if not body:
            continue
        title = re.sub(r"^[\d.]+\s*", "", m.group(1)).strip()
        sections.append({"urls": urls, "title": title, "body": body, "date": date})
    return sections


def main():
    files = sorted(glob.glob(os.path.join(DIGESTS_DIR, "*-ai-signal.md")))
    if not files:
        raise RuntimeError(f"no digests found in {DIGESTS_DIR}")
    by_url = {}
    for path in files:  # 时间升序，后面的日报覆盖前面的
        for sec in parse_digest(path):
            for url in sec["urls"]:
                by_url[url] = {
                    "detail": sec["body"],
                    "title": sec["title"],
                    "src": f"AI Signal 日报 {sec['date']}",
                }

    # 只保留与观点条目匹配的 URL，控制文件体积
    archive = (load_json("signals_archive.json") or {}).get("items", [])
    signals = load_json("curated_signals.json") or {}
    entries = archive + (signals.get("kol") or []) + (signals.get("kol_archive") or [])
    known = {normalize_url(e.get("url")) for e in entries}

    cur = load_json("signal_details.json") or {}
    details = {
        normalize_url(url): info
        for url, info in cur.get("details", {}).items()
        if normalize_url(url) in known
    }
    bios = cur.get("bios", {})   # 人物/栏目背景库：只增，enrich 不覆盖已有条目
    matched = 0
    for url, info in by_url.items():
        if url not in known:
            continue
        old = details.get(url)
        if old and old.get("lock"):
            continue
        details[url] = info
        matched += 1
    missing_bios = sorted({e.get("who") for e in entries if e.get("who")} - set(bios))
    save_json("signal_details.json", {
        "note": "本地增强层：AI Signal 日报深读（details，按 URL 键控）+ 人物/栏目背景（bios，按 who 键控）；"
                "云端不写此文件。details 条目加 lock:true 可防覆盖。",
        "bios": bios,
        "details": details,
    })
    print(f"  digests: {len(files)}, sections with url: {len(by_url)}, matched -> details: {matched}, total details: {len(details)}")
    if missing_bios:
        print(f"  [提醒] 以下来源还没有背景介绍（bios）: {', '.join(missing_bios)}")


if __name__ == "__main__":
    main()
