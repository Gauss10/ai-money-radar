# -*- coding: utf-8 -*-
"""
ARR 拟合脚本 —— AI Money Radar 的 ARR 估算模型。

输入:  arr_source.json  (手工维护的原始估算)
输出:  arr_checkpoints.json  (预渲染格式, 可直接供前端读取)
       并在控制台打印当前隐含指标 (今日 ARR / M/M / Y/Y / 每小时增加额)

模型 (当前前端使用的口径):
  1. 历史段: 月度估算锚点之间做对数线性插值 (等价于分段恒定增速), 7 天采样;
  2. 外推段: 取外推区间的几何中枢 center = sqrt(low*high),
     增速 rC = ln(center / 最新估算) / (目标日 - 最新估算日)  [每毫秒对数增速],
     沿 rC 指数外推, 5 天采样; 不确定带上下沿用 rL/rH (对 low/high 同法计算);
  3. 实时计数器: 前端用 counter{tLast, vLast, rMs} 每 120ms 算
     ARR(now) = vLast * exp(rMs * (now - tLast));
  4. 隐含月环比 M/M = exp(rMs * 30.44天) - 1;  Y/Y 用一年前的插值 yoyDen 做分母。

维护方法: 只需改 arr_source.json ——
  - estimates:     追加/修正月度锚点 {"date":"YYYY-MM-DD","arr_bn":X}
  - extrapolation: {"to":"YYYY-MM-DD","low":X,"high":Y}  年底目标区间
  - checkpoints:   公开报道对照点 {"date","arr_bn","source"} (图上的 ◆)
然后重跑本脚本。
"""
import json, math, calendar, datetime, os

DAY = 86400000
MS_MO = 30.44 * DAY
UTC = datetime.timezone.utc
HERE = os.path.dirname(os.path.abspath(__file__))

def ms(s):
    y, m, d = map(int, s.split('-'))
    return int(datetime.datetime(y, m, d, tzinfo=UTC).timestamp() * 1000)

def dstr(t):
    return datetime.datetime.fromtimestamp(t / 1000, UTC).strftime('%Y-%m-%d')

def geo_interp(pts, t):
    """对数线性(几何)插值, 与前端 interp() 一致"""
    if t <= pts[0][0]:
        return pts[0][1]
    for i in range(1, len(pts)):
        if t <= pts[i][0]:
            a, b = pts[i - 1], pts[i]
            f = (t - a[0]) / (b[0] - a[0])
            return a[1] * (b[1] / a[1]) ** f
    return pts[-1][1]

def build_company(co, now_ms):
    pts = sorted((ms(e['date']), e['arr_bn']) for e in co['estimates'])
    tLast, vLast = pts[-1]
    pj = co['extrapolation']
    pjT, low, high = ms(pj['to']), pj['low'], pj['high']
    center = math.sqrt(low * high)
    rC = math.log(center / vLast) / (pjT - tLast)
    rL = math.log(low / vLast) / (pjT - tLast)
    rH = math.log(high / vLast) / (pjT - tLast)

    est = lambda t, r=rC: geo_interp(pts, t) if t <= tLast else vLast * math.exp(r * (t - tLast))

    hist, t = [], pts[0][0]
    while t < tLast:
        hist.append([t, round(geo_interp(pts, t), 2)])
        t += 7 * DAY
    hist.append([tLast, vLast])

    ext, fan_lo, fan_hi = [], [], []
    t = tLast
    while t <= pjT:
        ext.append([t, round(est(t), 2)])
        fan_lo.append([t, round(est(t, rL), 2)])
        fan_hi.append([t, round(est(t, rH), 2)])
        t += 5 * DAY
    ext.append([pjT, round(center, 1)])
    fan_lo.append([pjT, round(low, 2)])
    fan_hi.append([pjT, round(high, 2)])

    yoyDen = round(est(now_ms - 365 * DAY), 2)
    out = {
        'label': co['label'], 'color': co['color'],
        'hist': hist, 'ext': ext, 'fanLo': fan_lo, 'fanHi': fan_hi,
        'cps': [{'t': ms(c['date']), 'v': c['arr_bn'], 'src': c['source']}
                for c in co.get('checkpoints', [])],
        'counter': {'tLast': tLast, 'vLast': vLast, 'rMs': rC},
        'yoyDen': yoyDen,
    }
    stats = {
        'now_bn': vLast * math.exp(rC * (now_ms - tLast)),
        'mm': math.exp(rC * MS_MO) - 1,
        'hourly': vLast * math.exp(rC * (now_ms - tLast)) * (math.exp(rC * 3600e3) - 1) * 1e9,
        'yoy': vLast * math.exp(rC * (now_ms - tLast)) / yoyDen - 1,
        'center': center,
    }
    return out, stats

def main():
    src = json.load(open(os.path.join(HERE, 'arr_source.json'), encoding='utf-8'))
    now_ms = int(datetime.datetime.now(UTC).timestamp() * 1000)
    out = {'render': True, 'updated': src.get('updated') or dstr(now_ms), 'companies': {}}
    print(f"{'company':<12}{'today ARR':>12}{'M/M':>8}{'Y/Y':>8}{'+$/hr':>12}{'target(center)':>16}")
    for key, co in src['companies'].items():
        built, st = build_company(co, now_ms)
        out['companies'][key] = built
        print(f"{key:<12}{'$%.1fB' % st['now_bn']:>12}{'%+.1f%%' % (st['mm']*100):>8}"
              f"{'%+.0f%%' % (st['yoy']*100):>8}{'$%s' % format(int(st['hourly']), ','):>12}"
              f"{'$%.1fB' % st['center']:>16}")
    dst = os.path.join(HERE, 'arr_checkpoints.json')
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
    print('written:', dst)

if __name__ == '__main__':
    main()
