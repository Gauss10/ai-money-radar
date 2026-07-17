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

from common import ROOT, load_json, save_json

DIGESTS_DIR = os.environ.get(
    "DIGESTS_DIR",
    os.path.normpath(os.path.join(ROOT, "..", "ai-signal", "digests")),
)

URL_RE = re.compile(r"\((https?://[^)\s]+)\)")
HEAD_RE = re.compile(r"^###\s+(.+)$", re.M)
VERDICT_RE = re.compile(r"^\*\*(判断|洞察|启发)[:：]\*\*", re.M)


def normalize_url(url):
    return (url or "").split("?")[0].rstrip("/")


def parse_digest(path):
    """返回 [{urls, title, body}]，body = 正文段落 + 判断段（去掉来源/链接行）"""
    text = open(path, encoding="utf-8").read()
    date = os.path.basename(path)[:10]
    sections = []
    heads = list(HEAD_RE.finditer(text))
    for i, m in enumerate(heads):
        start = m.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
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
        body = "\n".join(lines).strip()
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
    details = cur.get("details", {})
    matched = 0
    for url, info in by_url.items():
        if url not in known:
            continue
        old = details.get(url)
        if old and old.get("lock"):
            continue
        details[url] = info
        matched += 1
    save_json("signal_details.json", {
        "note": "本地增强层：AI Signal 日报深读，按 URL 匹配观点条目；云端不写此文件。lock:true 可防覆盖。",
        "details": details,
    })
    print(f"  digests: {len(files)}, sections with url: {len(by_url)}, matched -> details: {matched}, total details: {len(details)}")


if __name__ == "__main__":
    main()
