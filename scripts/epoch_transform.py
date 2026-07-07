# -*- coding: utf-8 -*-
"""
Epoch AI 'AI Data Centers' CSV -> site/data/datacenters.json

输入: ../data_centers/ 下的 CSV (从 https://epoch.ai/data/ai-data-centers 下载解压)
  - data_centers.csv           当前状态表: 每站点当前 H100e / IT power(MW) / Owner / Users / 地址
  - data_center_timelines.csv  时间线: 每站点各时点的 IT power / H100e (含未来预测)

口径:
  - 'Current power (MW)' 即 IT power
  - totals 汇总全部站点; 0 MW = pre-operational, 无贡献
  - industry_timeline: 每站点取 <= 月末的最近一次非空读数, 跨站点求和 (前向填充);
    从未有读数的站点计 0
  - Owner/Users 的证据标签 (#confident/#likely/#speculative) 剔除;
    空 Owner 归组为 'Unattributed (colo)'
  - status: 当前 IT power > 0 = operational (源数据无显式状态列)

用法: python epoch_transform.py   (Epoch 数据 ~月更, 下载新 CSV 覆盖后重跑)
"""
import csv, datetime, os, re
from common import ROOT, save_json

SRC = os.path.join(ROOT, 'data_centers')
DATASET_AS_OF = '2026-07-06'  # Epoch AI page: "Updated Jul. 6, 2026"
TAG = re.compile(r'\s*#\w+')
US_STATE = re.compile(r',\s*([A-Z]{2})\s+\d{5}')

NOTES = [
    "'Current power (MW)' in the snapshot CSV is IT power (matches 'IT power (MW)' in the timelines file).",
    "totals sum all sites in data_centers.csv; sites with 0 MW are pre-operational (planned/under construction) and add nothing.",
    "industry_timeline: per-site most recent non-null timeline reading at or before each month end, summed across sites (months with no coverage for a site count it at its last known value; sites never observed operational count 0).",
    "timelines coverage ends 2030-05-26; snapshot 'current' values are more recent than the last timeline event, so the last timeline month understates the current totals.",
    "Owner/Users evidence tags (#confident/#likely/#speculative) stripped; blank owners grouped as 'Unattributed (colo)' (QTS/DayOne/STACK/Vantage/Stream campuses).",
    "status derived from current IT power (>0 = operational); the source has no explicit status column.",
]


def clean(s):
    return TAG.sub('', s or '').strip()


def location(country, address):
    if country == 'United States':
        m = US_STATE.search(address or '')
        return f'{m.group(1)}, US' if m else 'United States'
    return country


def month_ends(first, last):
    out, (y, m) = [], (int(first[:4]), int(first[5:7]))
    while (y, m) <= (int(last[:4]), int(last[5:7])):
        nxt = datetime.date(y + (m == 12), m % 12 + 1, 1)
        out.append((f'{y:04d}-{m:02d}', str(nxt - datetime.timedelta(days=1))))
        y, m = nxt.year, nxt.month
    return out


def main():
    sites = list(csv.DictReader(open(os.path.join(SRC, 'data_centers.csv'),
                                     encoding='utf-8-sig')))
    tl = list(csv.DictReader(open(os.path.join(SRC, 'data_center_timelines.csv'),
                                  encoding='utf-8-sig')))

    # ---- totals ----
    mw_all = sum(float(r['Current power (MW)'] or 0) for r in sites)
    h100_all = sum(float(r['Current H100 equivalents'] or 0) for r in sites)
    totals = {'sites': len(sites), 'it_power_gw': round(mw_all / 1000, 1),
              'h100_eq_m': round(h100_all / 1e6, 1)}

    # ---- by_owner (top 8 by MW) ----
    agg = {}
    for r in sites:
        o = clean(r['Owner']) or 'Unattributed (colo)'
        a = agg.setdefault(o, {'owner': o, 'mw': 0.0, 'sites': 0})
        a['mw'] += float(r['Current power (MW)'] or 0)
        a['sites'] += 1
    by_owner = sorted(agg.values(), key=lambda x: -x['mw'])[:8]
    for a in by_owner:
        a['mw'] = round(a['mw'])

    # ---- top_sites (top 15 by MW) ----
    top = sorted(sites, key=lambda r: -float(r['Current power (MW)'] or 0))[:15]
    top_sites = [{
        'name': r['Name'],
        'owner': clean(r['Owner']) or 'Unattributed (colo)',
        'user': clean(r['Users']),
        'location': location(r['Country'], r['Address']),
        'status': 'operational' if float(r['Current power (MW)'] or 0) > 0 else 'planned',
        'mw': round(float(r['Current power (MW)'] or 0)),
        'h100e_k': round(float(r['Current H100 equivalents'] or 0) / 1000, 1),
    } for r in top]

    # ---- industry_timeline (月末前向填充求和) ----
    per_site = {}
    for r in tl:
        it, h = r['IT power (MW)'], r['H100 equivalents']
        if it == '' and h == '':
            continue
        per_site.setdefault(r['Data center'], []).append(
            (r['Date'], float(it or 0), float(h or 0)))
    for v in per_site.values():
        v.sort()
    last_date = max(r['Date'] for r in tl)
    timeline = []
    for label, eom in month_ends('2024-01', last_date):
        mw = h100 = 0.0
        for readings in per_site.values():
            cur = None
            for d, it, h in readings:
                if d <= eom:
                    cur = (it, h)
                else:
                    break
            if cur:
                mw += cur[0]
                h100 += cur[1]
        timeline.append([label, round(mw), round(h100 / 1000, 1)])

    out = {
        'as_of': DATASET_AS_OF,
        'source': "Epoch AI, 'AI Data Centers' (https://epoch.ai/data/ai-data-centers), CC-BY 4.0",
        'generated_by': 'epoch_transform.py',
        'totals': totals,
        'industry_timeline': timeline,
        'by_owner': by_owner,
        'top_sites': top_sites,
        'notes': NOTES,
    }
    save_json('datacenters.json', out)
    print(f"  sites {totals['sites']} | {totals['it_power_gw']} GW | "
          f"{totals['h100_eq_m']}M H100e | timeline {len(timeline)} months")


if __name__ == '__main__':
    main()
