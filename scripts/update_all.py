# -*- coding: utf-8 -*-
"""
一键更新全部数据 -> site/data/*.json

用法:  python update_all.py
之后:  cd ../site && python -m http.server 8000  ->  http://localhost:8000

各数据块:
  openrouter  日更   fetch_openrouter.py (需 OPENROUTER_API_KEY)
  vercel      日更   fetch_vercel.py
  sdk         日更   fetch_sdk.py
  news        日更   fetch_news.py
  compute     日更   fetch_compute_deals.py (官方页面发现；模型结构化提取)
  signal_feed 日更   generate_signal_feed.py (本仓库生成 X + 播客 feed)
  signals     日更   fetch_signals.py (本仓库 X + 播客 feed 二次筛选)
  gpu         日更   fetch_gpu.py (Ornn 公开 API)
  arr         事件驱动  改 ../arr-model/arr_source.json 后自动重建
  datacenters ~月更  Epoch CSV, 暂手动 (见本地数据说明文档)
"""
import os, shutil, subprocess, sys, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


# 单个脚本的最长运行时间（秒）。上游源卡死（例如 X cookie 失效后 twscrape
# 每 15 分钟无限重试）时，超时放弃该源并继续跑其余源，避免整个 job 被
# GitHub 的 6 小时上限杀掉、导致当天所有数据都不更新。
STEP_TIMEOUT = {
    'generate_signal_feed.py': 15 * 60,
    'fetch_openrouter.py': 20 * 60,
}
DEFAULT_TIMEOUT = 10 * 60


def run(name):
    print(f'== {name} ==')
    limit = STEP_TIMEOUT.get(name, DEFAULT_TIMEOUT)
    try:
        subprocess.run([sys.executable, os.path.join(HERE, name)],
                       check=True, timeout=limit)
        return True
    except subprocess.TimeoutExpired:
        print(f'  [TIMEOUT] {name} 超过 {limit // 60} 分钟未完成，已跳过（其余数据源继续）')
        return False
    except Exception:
        traceback.print_exc()
        return False


def main():
    ok = {}
    for s in ['generate_signal_feed.py',
              'fetch_openrouter.py', 'fetch_vercel.py', 'fetch_gpu.py',
              'fetch_sdk.py', 'fetch_news.py', 'fetch_compute_deals.py', 'fetch_codex_adoption.py', 'fetch_signals.py',
              'epoch_transform.py']:
        ok[s] = run(s)
    # ARR: 重建并拷贝进 site/data
    print('== arr-model/build_arr.py ==')
    try:
        subprocess.run([sys.executable, os.path.join(ROOT, 'arr-model', 'build_arr.py')],
                       check=True)
        shutil.copy(os.path.join(ROOT, 'arr-model', 'arr_checkpoints.json'),
                    os.path.join(ROOT, 'site', 'data', 'arr_checkpoints.json'))
        print('  copied arr_checkpoints.json -> site/data/')
        ok['arr'] = True
    except Exception:
        traceback.print_exc()
        ok['arr'] = False
    print('\n==== SUMMARY ====')
    for k, v in ok.items():
        print(f"  {'OK ' if v else 'FAIL'}  {k}")


if __name__ == '__main__':
    main()
