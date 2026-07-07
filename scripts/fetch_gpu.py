# -*- coding: utf-8 -*-
"""
GPU 租赁价格指数 (Ornn OCPI) -> site/data/gpu_prices.json

数据源: GET https://api.ornnai.com/api/gpu/{name}/index-history   (公开, 无需 key)
  返回 {"success":true,"gpu_type":name,"data":[{"timestamp":ISO,"index_value":x},...]}
  日期取 timestamp 前 10 位。
  注意: 部分型号只返回滚动 ~90 天窗口, 所以必须与本地历史合并, 不能整体覆盖。
"""
import json, datetime
from urllib.parse import quote
from common import http_get, load_json, save_json

GPUS = ['H100 SXM', 'H200', 'B200', 'A100 SXM4', 'RTX 5090']


def main():
    cur = load_json('gpu_prices.json') or {}
    series = cur.get('series') or {}
    for name in GPUS:
        d = json.loads(http_get(f'https://api.ornnai.com/api/gpu/{quote(name)}/index-history'))
        pts = {p['timestamp'][:10]: p['index_value']
               for p in d.get('data', []) if p.get('index_value') is not None}
        merged = dict(series.get(name) or [])
        merged.update(pts)
        series[name] = sorted(merged.items())
        print(f'  {name}: {len(series[name])} days, latest {series[name][-1]}')
    out = {
        'as_of': str(datetime.date.today()),
        'source': 'Ornn Compute Price Index (OCPI) — api.ornnai.com / dashboard.ornnai.com',
        'unit': 'USD per GPU-hour (index value)',
        'series': {k: [[d, v] for d, v in v_] for k, v_ in series.items()},
    }
    save_json('gpu_prices.json', out)


if __name__ == '__main__':
    main()
