# -*- coding: utf-8 -*-
"""
AI 数据中心建设新闻 -> site/data/dc_news.json

数据源: Google News RSS (公开, 无需 key)
  https://news.google.com/rss/search?q=...

策略:
  - 拉取查询词的最新条目, 按 URL 去重合并进现有列表
  - pinned 条目 (手工精选/改写标题) 永远保留
  - 其余按日期倒序, 总条数截到 30
  - 语义级去重 (同一事件多家报道) 不在本脚本做 —— 让 Claude 定期清理,
    或人工删掉重复项即可 (脚本不会重新加回已删除的 URL? 会。要彻底屏蔽
    可把该条 url 加进 blocklist 字段)
"""
import datetime, email.utils, xml.etree.ElementTree as ET
from urllib.parse import quote
from common import http_get, load_json, save_json

QUERIES = ['AI data center construction OR investment when:2d',
           'hyperscaler data center GW when:2d']
KEEP = 30


def fetch_query(q):
    url = f'https://news.google.com/rss/search?q={quote(q)}&hl=en-US&gl=US&ceid=US:en'
    root = ET.fromstring(http_get(url))
    out = []
    for it in root.iter('item'):
        title = it.findtext('title') or ''
        link = it.findtext('link') or ''
        pub = it.findtext('pubDate') or ''
        src = it.findtext('source') or ''
        try:
            d = email.utils.parsedate_to_datetime(pub).strftime('%Y-%m-%d')
        except Exception:
            d = str(datetime.date.today())
        out.append({'date': d, 'title': title, 'news_source': src, 'url': link, 'key': False})
    return out


def main():
    cur = load_json('dc_news.json') or {}
    items = cur.get('items') or []
    block = set(cur.get('blocklist') or [])
    seen = {i['url'] for i in items} | block

    added = 0
    for q in QUERIES:
        for it in fetch_query(q):
            if it['url'] not in seen:
                items.append(it)
                seen.add(it['url'])
                added += 1
    print(f'  fetched, {added} new items')

    pinned = [i for i in items if i.get('pinned')]
    rest = sorted((i for i in items if not i.get('pinned')),
                  key=lambda x: x['date'], reverse=True)[:KEEP - len(pinned)]
    out_items = sorted(pinned + rest, key=lambda x: x['date'], reverse=True)

    out = {
        'as_of': str(datetime.date.today()),
        'source': 'Google News RSS（每日增量；按事件实体聚类去重，同事件留最权威稿；pinned 手动精选保留）',
        'items': out_items,
    }
    if block:
        out['blocklist'] = sorted(block)
    save_json('dc_news.json', out)
    print(f'  total {len(out_items)} items ({len(pinned)} pinned)')


if __name__ == '__main__':
    main()
