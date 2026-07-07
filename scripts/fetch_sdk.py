# -*- coding: utf-8 -*-
"""
SDK 日下载量 -> site/data/sdk_downloads.json

数据源 (公开, 无需 key):
  npm : https://api.npmjs.org/downloads/range/{start}:{end}/{package}
  PyPI: https://pypistats.org/api/packages/{package}/overall  (取 without_mirrors)

单位 M downloads/day, 0 值日剔除 (上游数据缺口)。
"""
import json, datetime, time
from common import http_get, load_json, save_json

NPM_PKGS = ['@anthropic-ai/sdk', 'openai']
PYPI_PKGS = ['anthropic', 'openai']
M = 1e6


def merge(old, new_pts):
    d = dict(old or [])
    for k, v in new_pts:
        if v > 0:
            d[k] = v
    return sorted(d.items())


def fetch_json_with_retry(url, retries=1):
    last = None
    for i in range(retries + 1):
        try:
            return json.loads(http_get(url))
        except Exception as e:
            last = e
            if i < retries:
                time.sleep(5)
    raise last


def main():
    cur = load_json('sdk_downloads.json') or {}
    today = datetime.date.today()

    npm = cur.get('npm') or {}
    for pkg in NPM_PKGS:
        old = npm.get(pkg) or []
        start = (datetime.date.fromisoformat(old[-1][0]) - datetime.timedelta(days=7)
                 if old else today - datetime.timedelta(days=365))
        url = f'https://api.npmjs.org/downloads/range/{start}:{today}/{pkg}'
        try:
            d = fetch_json_with_retry(url, retries=1)
            pts = [(r['day'], round(r['downloads'] / M, 2)) for r in d.get('downloads', [])]
            npm[pkg] = [[k, v] for k, v in merge(old, pts)]
            print(f'  npm {pkg}: {len(npm[pkg])} days, latest {npm[pkg][-1]}')
        except Exception as e:
            npm[pkg] = old
            print(f'  WARN npm {pkg}: {e}; kept {len(old)} old points')

    pypi = cur.get('pypi') or {}
    for pkg in PYPI_PKGS:
        old = pypi.get(pkg) or []
        try:
            d = fetch_json_with_retry(
                f'https://pypistats.org/api/packages/{pkg}/overall?mirrors=false',
                retries=1,
            )
            pts = [(r['date'], round(r['downloads'] / M, 2))
                   for r in d.get('data', []) if r['category'] == 'without_mirrors']
            pypi[pkg] = [[k, v] for k, v in merge(old, pts)]
            print(f'  pypi {pkg}: {len(pypi[pkg])} days, latest {pypi[pkg][-1]}')
        except Exception as e:
            pypi[pkg] = old
            print(f'  WARN pypi {pkg}: {e}; kept {len(old)} old points')

    out = {
        'as_of': str(today),
        'source': 'npm: api.npmjs.org/downloads/range — PyPI: pypistats.org/api (without_mirrors)',
        'unit': 'M downloads/day',
        'note': 'Developer adoption proxy。周内季节性强，前端画 7DMA。0 值日（上游数据缺口）已剔除。',
        'npm': npm, 'pypi': pypi,
    }
    save_json('sdk_downloads.json', out)


if __name__ == '__main__':
    main()
