# -*- coding: utf-8 -*-
"""公共工具: 路径、HTTP、.env 读取"""
import json, os, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'site', 'data')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')


def env(key):
    """环境变量优先, 其次 scripts/.env"""
    if os.environ.get(key):
        return os.environ[key]
    envfile = os.path.join(HERE, '.env')
    if os.path.exists(envfile):
        for line in open(envfile, encoding='utf-8'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                if k.strip() == key:
                    return v.strip()
    return None


def http_get(url, headers=None, timeout=60):
    req = urllib.request.Request(url, headers={'User-Agent': UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', errors='replace')


def load_json(name):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


def save_json(name, obj):
    json.dump(obj, open(os.path.join(DATA, name), 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    print(f'  saved {name}')
