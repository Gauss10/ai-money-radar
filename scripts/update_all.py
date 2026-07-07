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
  signals     日更   fetch_signals.py (AI Signal 中央 X + 播客 feed)
  gpu         日更   fetch_gpu.py (Ornn 公开 API)
  arr         事件驱动  改 ../arr-model/arr_source.json 后自动重建
  datacenters ~月更  Epoch CSV, 暂手动 (见本地数据说明文档)
"""
import os, shutil, subprocess, sys, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def run(name):
    print(f'== {name} ==')
    try:
        subprocess.run([sys.executable, os.path.join(HERE, name)], check=True)
        return True
    except Exception:
        traceback.print_exc()
        return False


def main():
    ok = {}
    for s in ['fetch_openrouter.py', 'fetch_vercel.py', 'fetch_gpu.py',
              'fetch_sdk.py', 'fetch_news.py', 'fetch_signals.py',
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
