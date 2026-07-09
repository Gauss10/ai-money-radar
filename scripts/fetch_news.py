# -*- coding: utf-8 -*-
"""
AI 数据中心建设新闻 -> site/data/dc_news.json

数据源: Google News RSS (公开, 无需 key)
  https://news.google.com/rss/search?q=...

策略:
  - 拉取查询词的最新条目, 按 URL 去重合并进现有列表
  - 为标题生成中文 title_zh；英文原文 title 保留
  - pinned 条目 (手工精选/改写标题) 永远保留
  - 其余按日期倒序, 总条数截到 30
  - 语义级去重 (同一事件多家报道) 不在本脚本做 —— 让 Claude 定期清理,
    或人工删掉重复项即可 (脚本不会重新加回已删除的 URL? 会。要彻底屏蔽
    可把该条 url 加进 blocklist 字段)
"""
import datetime, email.utils, json, re, xml.etree.ElementTree as ET
from urllib.parse import quote, urlencode
from common import http_get, load_json, save_json

QUERIES = ['AI data center construction OR investment when:2d',
           'hyperscaler data center GW when:2d']
KEEP = 30
TRANSLATE_API = 'https://translate.googleapis.com/translate_a/single'
HAS_CJK = re.compile(r'[\u4e00-\u9fff]')
TITLE_ZH_OVERRIDES = {
    'Meta to build $13B data centre north of Edmonton, its first in Canada':
        'Meta 将在埃德蒙顿以北建设约 130 亿加元数据中心，为其加拿大首个数据中心',
    'Meta is building its first big Canadian data center as AI expansion crosses the border':
        '随着 AI 扩张跨境推进，Meta 正在加拿大建设首个大型数据中心',
    'The ‘time-consuming’ permits dozens of data centers are skipping':
        '数十个数据中心正在绕开的“耗时”许可流程',
    'Meta plans billions for first AI data center in Canada, largest outside the US':
        'Meta 计划斥资数十亿美元在加拿大建设首个 AI 数据中心，规模为美国以外最大',
    'Data centers dominate construction’s latest economic reports':
        '最新建筑业经济报告：数据中心成为主线',
    'Pa. faces data center boom as dozens of massive projects emerge':
        '宾夕法尼亚州迎来数据中心热潮，数十个大型项目浮现',
    'Wyoming tightens wastewater rules after Meta datacenter contractor flushed contaminated water':
        'Meta 数据中心承包商排放受污染废水后，怀俄明州收紧废水规则',
    'Sunrun wants to pay you to turn your home into an AI data center':
        'Sunrun 想付钱让你把自家房屋变成 AI 数据中心',
    'Report Forecasts US Growth Regions for Data Centers':
        '报告预测美国数据中心增长区域',
    'Breaking Ground on Meta’s First Data Center in Canada':
        'Meta 加拿大首个数据中心破土动工',
    'AI demand is increasing labor shortages and skills pressure in data center construction - report':
        '报告：AI 需求加剧数据中心建设的劳动力短缺和技能压力',
    'Second Major Virginia Data Center Project Dies, Raising AI Site Selection Stakes':
        '弗吉尼亚州第二个大型数据中心项目告吹，AI 选址门槛上升',
    'Real Estate & Construction News Roundup (7/8/26) – Data Centers Negotiate Flexibility for Speed, Hotel Deal Activities Focus on Luxury, and DC Sues Apartment Owners':
        '房地产与建筑新闻综述：数据中心为提速寻求更灵活交易条件',
    'Right-wing media figures are split on AI and data centers':
        '右翼媒体人士在 AI 与数据中心问题上分歧明显',
    'Data center moratorium in Santa Rosa County up for debate on Thursday':
        '圣罗莎县将于周四讨论数据中心暂停令',
    'TeraWulf-Anthropic Deal Paves Way for Kentucky Data Center Constr...':
        'TeraWulf-Anthropic 交易为肯塔基数据中心建设铺路',
    'Meta Plans First Major Canadian Data Center for AI Push':
        'Meta 计划在加拿大建设首个大型数据中心，支撑 AI 扩张',
    'AI data center owners are straining U.S. warehouse market':
        'AI 数据中心业主正在推高美国仓储市场压力',
    'Meta breaks ground on first Canadian data center in CA$13 billion Alberta build':
        'Meta 耗资 130 亿加元在阿尔伯塔省建设的加拿大首个数据中心破土动工',
    'Is QUALCOMM’s AI Pivot and Index Exit Altering The Investment Case For QUALCOMM (QCOM)?':
        '高通 AI 转型和退出指数是否改变其投资逻辑？',
    'National Grid Ventures To Invest $1.75 Billion In Joulent To Power U.S. Data Centers And AI':
        'National Grid Ventures 将向 Joulent 投资 17.5 亿美元，为美国数据中心和 AI 供电',
    'Meta begins work on 1GW Alberta data center in major AI infrastructure push (META:NASDAQ)':
        'Meta 启动阿尔伯塔省 1GW 数据中心建设，支撑 AI 基础设施扩张',
    'Texas Poised To Become The Next Epicenter Of AI-Driven Builds':
        '德州有望成为 AI 建设项目的下一个中心',
    'Grid Constraints Slow AI Data Center Buildout':
        '电网约束拖慢 AI 数据中心建设',
    'ChemTreat Introduces Operational Readiness Framework for Day-One Reliability in AI Data Center Cooling Systems':
        'ChemTreat 推出 AI 数据中心冷却系统上线可靠性框架',
    'Nscale secures $900 million for AI data center expansion':
        'Nscale 获得 9 亿美元，用于扩建 AI 数据中心',
    'Ohio’s warped energy policy: 10 natural gas plants are being built or planned to power AI':
        '俄亥俄能源政策扭曲：10 座天然气电厂正在建设或规划中，为 AI 供电',
}


def title_without_source(title, source):
    title = (title or '').strip()
    source = (source or '').strip()
    if not title or not source:
        return title
    lower = title.lower()
    for sep in (' - ', ' – ', ' — '):
        suffix = f'{sep}{source}'.lower()
        if lower.endswith(suffix):
            return title[:-len(suffix)].strip()
    return title


def translate_title(title, source):
    text = title_without_source(title, source)
    if text in TITLE_ZH_OVERRIDES:
        return TITLE_ZH_OVERRIDES[text]
    if not text or HAS_CJK.search(text):
        return text
    try:
        qs = urlencode({'client': 'gtx', 'sl': 'en', 'tl': 'zh-CN', 'dt': 't', 'q': text})
        data = json.loads(http_get(f'{TRANSLATE_API}?{qs}', timeout=20))
        translated = ''.join(part[0] for part in data[0] if part and part[0]).strip() or text
        return polish_title_zh(translated, title)
    except Exception as exc:
        print(f'  translate failed: {source} | {text[:80]} | {exc}')
        return ''


def polish_title_zh(value, title):
    value = value or ''
    if 'Meta' in (title or ''):
        value = value.replace('元数据中心', 'Meta 数据中心')
        value = value.replace('元数据', 'Meta')
        value = value.replace('元计划', 'Meta 计划')
    replacements = {
        '人工智能数据中心': 'AI 数据中心',
        '人工智能基础设施': 'AI 基础设施',
        '人工智能驱动建筑': 'AI 驱动建设',
        '人工智能': 'AI',
        '艾伯塔省': '阿尔伯塔省',
        '国家电网风险投资公司': 'National Grid Ventures',
        '网格限制': '电网约束',
        '第一天可靠性': '上线首日可靠性',
    }
    for src, dst in replacements.items():
        value = value.replace(src, dst)
    value = re.sub(r'([\u4e00-\u9fff])AI', r'\1 AI', value)
    value = re.sub(r'AI([\u4e00-\u9fff])', r'AI \1', value)
    return value.strip()


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
    translated = 0
    for item in out_items:
        base_title = title_without_source(item.get('title'), item.get('news_source'))
        if base_title in TITLE_ZH_OVERRIDES:
            item['title_zh'] = TITLE_ZH_OVERRIDES[base_title]
        elif not item.get('title_zh'):
            item['title_zh'] = translate_title(item.get('title'), item.get('news_source'))
            if item.get('title_zh'):
                translated += 1
        else:
            item['title_zh'] = polish_title_zh(item.get('title_zh'), item.get('title'))

    out = {
        'as_of': str(datetime.date.today()),
        'source': 'Google News RSS（每日增量；按事件实体聚类去重，同事件留最权威稿；pinned 手动精选保留；中文界面展示 title_zh）',
        'items': out_items,
    }
    if block:
        out['blocklist'] = sorted(block)
    save_json('dc_news.json', out)
    print(f'  total {len(out_items)} items ({len(pinned)} pinned), translated {translated}')


if __name__ == '__main__':
    main()
