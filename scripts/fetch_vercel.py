# -*- coding: utf-8 -*-
"""
Vercel AI Gateway 模型份额 -> site/data/vercel_gateway.json

数据源: https://vercel.com/ai-gateway/leaderboards/models 页面
  SSR HTML 内嵌 Next.js flight data, 其中 "rawData" 数组含约 60 天逐日份额:
  [{"day":"2026-05-08T00:00:00.000Z","metric":"requests|tokens|cost",
    "chef_values":[["Gemini 3 Flash",16.4],...]}, ...]
  chef_values 是当日该口径 top ~10 模型的份额 % (不足 100, 余量为 Other)。

策略: 每次全量解析页面窗口, 与本地历史做并集合并 (窗口外的旧日期保留),
      并追加当日 snapshot (token/spend/request 三口径 Top10 + Other)。
"""
import json, re, datetime
from common import http_get, load_json, save_json

URL = 'https://vercel.com/ai-gateway/leaderboards/models'
# history 里长期跟踪的命名序列 ("Claude (family)" 为所有含 Claude 名目之和)
TRACKED = ['Claude (family)', 'Claude Fable 5', 'DeepSeek V4 Flash', 'DeepSeek V4 Pro',
           'GLM 5.2', 'Gemini 3 Flash', 'Claude Sonnet 4.6', 'Claude Opus 4.8']
METRIC_MAP = {'tokens': 'tokens', 'cost': 'cost'}   # history 的两个口径
SNAP_MAP = {'tokens': 'token_share', 'cost': 'spend_share', 'requests': 'request_share'}


def extract_rawdata(html):
    """从 flight data 中提取 rawData 数组 (转义 JSON, 需两次反转义)"""
    m = re.search(r'\\"rawData\\":\[', html)
    if not m:
        raise RuntimeError('rawData not found — 页面结构可能已改版')
    # 从 [ 开始做括号配平 (在转义文本上, [ ] 不会被转义, 可直接数)
    s = html
    start = m.end() - 1
    depth, i = 0, start
    while i < len(s):
        if s[i] == '[':
            depth += 1
        elif s[i] == ']':
            depth -= 1
            if depth == 0:
                break
        i += 1
    frag = s[start:i + 1]
    frag = frag.replace('\\"', '"').replace('\\\\', '\\')
    return json.loads(frag)


def main():
    html = http_get(URL)
    raw = extract_rawdata(html)
    print(f'  parsed {len(raw)} day-metric rows')

    # 按 metric -> date -> [(model, share)]
    table = {}
    for row in raw:
        d = row['day'][:10]
        table.setdefault(row['metric'], {})[d] = row['chef_values']

    cur = load_json('vercel_gateway.json') or {}
    today = max(d for m in table.values() for d in m)

    # ---- history 合并 ----
    hist = cur.get('history') or {}
    for metric, hkey in METRIC_MAP.items():
        days_map = table.get(metric, {})
        h = hist.get(hkey) or {'days': [], 'series': {k: [] for k in TRACKED}}
        merged = {d: {k: h['series'][k][i] for k in h['series']}
                  for i, d in enumerate(h['days'])}
        for d, vals in days_map.items():
            row = {}
            claude_sum = 0.0
            vd = dict(vals)
            for name in TRACKED:
                if name == 'Claude (family)':
                    continue
                row[name] = round(vd.get(name, 0.0), 2)
            claude_sum = sum(v for k, v in vd.items() if 'claude' in k.lower())
            row['Claude (family)'] = round(claude_sum, 2)
            merged[d] = row
        days = sorted(merged)
        hist[hkey] = {'days': days,
                      'series': {k: [merged[d].get(k, 0.0) for d in days] for k in TRACKED}}
    # ---- snapshot 追加 (最新一天) ----
    snaps = [s for s in (cur.get('snapshots') or []) if s['date'] != today]
    snap = {'date': today}
    for metric, skey in SNAP_MAP.items():
        vals = table.get(metric, {}).get(today, [])
        top = [[k, round(v, 1)] for k, v in sorted(vals, key=lambda x: -x[1])[:10]]
        top.append(['Other', round(100 - sum(v for _, v in top), 1)])
        snap[skey] = top
    snaps.append(snap)
    snaps = snaps[-90:]   # 保留 90 天记录

    out = {
        'as_of': today,
        'source': 'Vercel AI Gateway Leaderboards (vercel.com/ai-gateway/leaderboards/models)',
        'window_note': 'share % per day, parsed from page-embedded daily series',
        'snapshots': snaps,
        'history': hist,
    }
    save_json('vercel_gateway.json', out)
    ndays = len(hist['tokens']['days'])
    print(f'  history: {ndays} days (thru {today}); snapshots: {len(snaps)}')


if __name__ == '__main__':
    main()
