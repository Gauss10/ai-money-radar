# -*- coding: utf-8 -*-
"""Build Vercel AI Gateway model and lab share data from the official API.

The output schema and model calculations remain compatible with the dashboard.
All history is rebuilt from the API's current coverage window on every run so
that legacy page-scraped values cannot be mixed with official API values.
"""

import json

from common import http_get, save_json


API_URL = 'https://vercel.com/api/ai/leaderboard-export'
TRACKED = [
    'Claude (family)',
    'Claude Fable 5',
    'DeepSeek V4 Flash',
    'DeepSeek V4 Pro',
    'GLM 5.2',
    'Gemini 3 Flash',
    'Claude Sonnet 4.6',
    'Claude Opus 4.8',
]
METRIC_MAP = {'tokens': 'tokens', 'cost': 'cost'}
SNAP_MAP = {
    'tokens': 'token_share',
    'cost': 'spend_share',
    'requests': 'request_share',
}
API_METRICS = {'tokens': 'tokens', 'spend': 'cost', 'requests': 'requests'}
LABS = {
    'Anthropic': 'anthropic',
    'OpenAI': 'openai',
    'Gemini': 'google',
    'Z.ai': 'zai',
    'Kimi': 'moonshotai',
}


def weekly_average(table, dates, metric):
    """Average public daily shares across the selected data dates."""
    if not dates:
        return []
    totals = {}
    for day in dates:
        for model, share in table.get(metric, {}).get(day, []):
            totals[model] = totals.get(model, 0.0) + share
    averages = {model: total / len(dates) for model, total in totals.items()}
    top = sorted(averages.items(), key=lambda item: -item[1])[:10]
    rows = [[model, round(share, 1)] for model, share in top]
    rows.append([
        'Other',
        round(max(0.0, 100 - sum(share for _, share in rows)), 1),
    ])
    return rows


def fetch_dataset(dataset):
    data = json.loads(http_get(f'{API_URL}?dataset={dataset}'))
    rows = data.get('rows')
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f'Vercel export returned no rows for {dataset}')
    return data


def model_rows_to_table(rows):
    """Map official model API rows to the legacy metric/date/model table."""
    table = {}
    for row in rows:
        metric = API_METRICS.get(row.get('metric'))
        if not metric:
            continue
        day = row['date'][:10]
        table.setdefault(metric, {}).setdefault(day, []).append(
            [row['name'], float(row['share_percent'])]
        )
    for metric in table.values():
        for values in metric.values():
            values.sort(key=lambda item: -item[1])
    return table


def build_lab_spend_history(rows):
    """Build official daily Spend shares for the selected model labs."""
    by_day = {}
    for row in rows:
        if row.get('metric') != 'spend':
            continue
        day = row['date'][:10]
        by_day.setdefault(day, {})[row['name'].lower()] = float(
            row['share_percent']
        )
    days = sorted(by_day)
    return {
        'days': days,
        'series': {
            label: [round(by_day[day].get(api_name, 0.0), 2) for day in days]
            for label, api_name in LABS.items()
        },
    }


def build_model_history(table):
    """Rebuild tracked model series solely from the official API window."""
    history = {}
    for metric, history_key in METRIC_MAP.items():
        rows_by_day = {}
        for day, values in table.get(metric, {}).items():
            value_map = dict(values)
            row = {
                name: round(value_map.get(name, 0.0), 2)
                for name in TRACKED
                if name != 'Claude (family)'
            }
            row['Claude (family)'] = round(
                sum(
                    value
                    for name, value in value_map.items()
                    if 'claude' in name.lower()
                ),
                2,
            )
            rows_by_day[day] = row
        days = sorted(rows_by_day)
        history[history_key] = {
            'days': days,
            'series': {
                name: [rows_by_day[day].get(name, 0.0) for day in days]
                for name in TRACKED
            },
        }
    return history


def build_snapshots(table, limit=90):
    """Rebuild daily Top 10 snapshots for dates shared by all three metrics."""
    common_days = set(table.get('tokens', {}))
    for metric in ('cost', 'requests'):
        common_days &= set(table.get(metric, {}))
    days = sorted(common_days)[-limit:]
    snapshots = []
    for day in days:
        snapshot = {'date': day}
        for metric, snapshot_key in SNAP_MAP.items():
            values = table.get(metric, {}).get(day, [])
            top = [
                [name, round(share, 1)]
                for name, share in sorted(
                    values, key=lambda item: -item[1]
                )[:10]
            ]
            top.append([
                'Other',
                round(max(0.0, 100 - sum(share for _, share in top)), 1),
            ])
            snapshot[snapshot_key] = top
        snapshots.append(snapshot)
    return snapshots


def main():
    models = fetch_dataset('models')
    labs = fetch_dataset('labs')
    table = model_rows_to_table(models['rows'])
    lab_spend = build_lab_spend_history(labs['rows'])
    print(f"  API rows: models={len(models['rows'])}, labs={len(labs['rows'])}")

    history = build_model_history(table)
    snapshots = build_snapshots(table)
    all_days = sorted({day for metric in table.values() for day in metric})
    if not all_days:
        raise RuntimeError('Vercel model export contains no supported metric dates')
    today = all_days[-1]

    week_days = sorted(
        set(table.get('tokens', {})) & set(table.get('cost', {}))
    )[-7:]
    latest_7d = {
        'start_date': week_days[0],
        'end_date': week_days[-1],
        'day_count': len(week_days),
        'token_share': weekly_average(table, week_days, 'tokens'),
        'spend_share': weekly_average(table, week_days, 'cost'),
    } if week_days else None

    coverage_start = min(
        history['tokens']['days'][0],
        history['cost']['days'][0],
        lab_spend['days'][0],
    )
    out = {
        'as_of': today,
        'coverage_start': coverage_start,
        'source': (
            'Vercel AI Gateway Leaderboard Export API '
            '(vercel.com/api/ai/leaderboard-export)'
        ),
        'license': models.get('license', 'CC-BY-4.0'),
        'license_url': models.get(
            'license_url',
            'https://creativecommons.org/licenses/by/4.0/',
        ),
        'window_note': (
            'full available daily share history rebuilt from the official '
            'Vercel leaderboard export API'
        ),
        'weekly_note': (
            'arithmetic mean of daily shares across the latest 7 common data '
            'dates; not weighted by absolute token or spend totals'
        ),
        'snapshots': snapshots,
        'latest_7d': latest_7d,
        'history': history,
        'lab_history': {
            'spend': lab_spend,
            'note': (
                'official daily Lab spend shares; Google and Moonshot AI '
                'labs are displayed as Gemini and Kimi'
            ),
        },
    }
    save_json('vercel_gateway.json', out)
    print(
        f"  history: {len(history['tokens']['days'])} days "
        f"({coverage_start} thru {today}); snapshots: {len(snapshots)}"
    )


if __name__ == '__main__':
    main()
