# -*- coding: utf-8 -*-
"""
OpenRouter 日度 token 数据 -> site/data/openrouter_daily.json

数据源: GET https://openrouter.ai/api/v1/datasets/rankings-daily
  - 每日 top-50 模型 + 长尾合计行(permaslug='other'), token = prompt+completion
  - 数据自 2025-01-01 起; 限速 30 req/min, 500 req/day; 需要任意有效 API key
  - 引用要求: "Source: OpenRouter (openrouter.ai/rankings), as of {as_of}."

增量策略: 从现有 daily_totals 最后日期回退 3 天开始拉到今天, 覆盖合并。
"""
import json, datetime
from collections import defaultdict
from common import env, http_get, load_json, save_json

API = 'https://openrouter.ai/api/v1/datasets/rankings-daily'
# watchlist 前缀 -> 对 permaslug 做 startswith 匹配
WATCH = ['anthropic/claude-5-fable', 'anthropic/claude-sonnet', 'openai/gpt-5',
         'google/gemini-3', 'deepseek/', 'x-ai/grok']
B = 1e9


def fetch_window(key, start, end):
    rows = []
    # 单请求窗口最大约 1 年, 分段拉
    s = start
    while s <= end:
        e = min(s + datetime.timedelta(days=200), end)
        url = f'{API}?start_date={s}&end_date={e}'
        d = json.loads(http_get(url, headers={'Authorization': f'Bearer {key}'}))
        rows += d['data']
        meta = d['meta']
        s = e + datetime.timedelta(days=1)
    return rows, meta


def main():
    key = env('OPENROUTER_API_KEY')
    assert key, 'OPENROUTER_API_KEY 未配置 (scripts/.env)'
    cur = load_json('openrouter_daily.json') or {}
    old_totals = dict(cur.get('daily_totals') or [])

    today = datetime.date.today()
    if old_totals:
        start = datetime.date.fromisoformat(max(old_totals)) - datetime.timedelta(days=3)
    else:
        start = datetime.date(2025, 1, 1)
    rows, meta = fetch_window(key, start, today)
    print(f'  fetched {len(rows)} rows, {start} -> {today}')

    # 按日聚合
    by_day = defaultdict(list)   # date -> [(slug, tokens)]
    for r in rows:
        by_day[r['date']].append((r['model_permaslug'], int(r['total_tokens'])))

    # 1. daily_totals (含长尾)
    for d, items in by_day.items():
        old_totals[d] = round(sum(t for _, t in items) / B, 2)
    totals = sorted(old_totals.items())

    # 2. lab_share: 沿用现有 lab 列表; 'other' 行 -> long-tail, 未列出的厂商 -> others
    ls = cur.get('lab_share') or {'dates': [], 'labs': {}}
    labs = ls['labs'] or {k: [] for k in
        ['anthropic', 'google', 'openai', 'deepseek', 'x-ai', 'z-ai', 'minimax', 'qwen',
         'moonshotai', 'mistralai', 'meta-llama', 'nvidia', 'others', 'long-tail']}
    idx = {d: i for i, d in enumerate(ls['dates'])}
    for d in sorted(by_day):
        agg = defaultdict(float)
        for slug, t in by_day[d]:
            if slug == 'other':
                agg['long-tail'] += t
            else:
                author = slug.split('/')[0]
                agg[author if author in labs else 'others'] += t
        if d in idx:
            i = idx[d]
            for k in labs:
                labs[k][i] = round(agg.get(k, 0) / B, 2)
        else:
            ls['dates'].append(d)
            for k in labs:
                labs[k].append(round(agg.get(k, 0) / B, 2))
    ls['labs'] = labs

    # 3. watchlist (前缀匹配, 只记 >0 的日子)
    wl = cur.get('watchlist') or {k: [] for k in WATCH}
    for wkey in WATCH:
        series = dict(wl.get(wkey) or [])
        for d in sorted(by_day):
            s = sum(t for slug, t in by_day[d] if slug != 'other' and slug.startswith(wkey))
            if s > 0:
                series[d] = round(s / B, 2)
            elif d in series and s == 0:
                pass  # 保留历史值不清零
        wl[wkey] = sorted(series.items())

    # 4. top models
    latest = max(by_day)
    top_latest = sorted(((s, t) for s, t in by_day[latest] if s != 'other'),
                        key=lambda x: -x[1])[:15]
    week_days = sorted(by_day)[-7:]
    agg7 = defaultdict(int)
    for d in week_days:
        for s, t in by_day[d]:
            if s != 'other':
                agg7[s] += t
    top7 = sorted(agg7.items(), key=lambda x: -x[1])[:15]

    out = {
        'sample': False,
        'as_of': meta['as_of'],
        'citation': f"Source: OpenRouter (openrouter.ai/rankings), as of {meta['as_of']}.",
        'tokenizer_note': "Token counts use each provider's own tokenizer — "
                          "cross-provider comparisons are approximate.",
        'daily_totals': [[d, v] for d, v in totals],
        'daily_totals_unit': 'B tokens/day',
        'lab_share': ls,
        'watchlist': {k: [[d, v] for d, v in v_] for k, v_ in wl.items()},
        'top_models_latest': [{'slug': s, 'tokens_b': round(t / B, 2)} for s, t in top_latest],
        'top_models_7d': [{'slug': s, 'tokens_b': round(t / B, 2)} for s, t in top7],
        'latest_date': latest,
    }
    save_json('openrouter_daily.json', out)
    print(f'  daily_totals: {len(totals)} days (thru {latest}), '
          f'latest total {totals[-1][1]}B tokens/day')


if __name__ == '__main__':
    main()
