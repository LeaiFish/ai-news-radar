from datetime import datetime, timezone
from xml.sax.saxutils import escape

from scripts.ai_relevance import score_ai_relevance
from scripts.editorial_focus import editorial_focus
from scripts.update_news import (
    CURATED_AI_MEDIA_FEEDS, parse_curated_ai_media_feed_items,
    normalize_url, merge_story_items,
)

NOW = datetime(2026, 10, 26, 3, tzinfo=timezone.utc)
FEED = next(f for f in CURATED_AI_MEDIA_FEEDS if f['title'] == 'IT之家')
WORKBUDDY = '腾讯 WorkBuddy 接入模型 Kimi-K3.1-Pro，支持 100 万上下文'
URL = 'https://www.ithome.com/1/017/412.htm'


def item(title, url, date='Sat, 24 Oct 2026 07:59:12 GMT'):
    return f'<item><title>{escape(title)}</title><link>{escape(url)}</link>' + (
        f'<pubDate>{date}</pubDate>' if date else '') + '</item>'


def parse(items, **overrides):
    xml = ('<rss><channel>' + ''.join(items) + '</channel></rss>').encode()
    return parse_curated_ai_media_feed_items(xml, FEED | overrides, NOW)


def test_product_updates_survive_technical_flood_and_canonical_url_duplicates():
    rows = parse([
        *[item(f'DeepSeek 模型评测榜单第{i}名', f'https://www.ithome.com/eval{i}') for i in range(9)],
        item('华为路由AI Mesh新品首销', 'https://www.ithome.com/router'),
        item('AI显卡限时促销', 'https://www.ithome.com/sale'),
        item(WORKBUDDY, URL + '?utm_source=aihot'),
        item('腾讯 WorkBuddy 接入模型 Kimi-K3.1-Pro', URL),
        item('Claude 桌面应用推出新版界面', 'https://www.ithome.com/claude'),
        item('千问新增功能：可将表格做成长期应用', 'https://www.ithome.com/qwen'),
        item('Kimi 就会员限流致歉，为所有订阅会员进行重置', 'https://www.ithome.com/kimi'),
        item('我用 WorkBuddy 把文章做成知识库', 'https://www.ithome.com/usage'),
    ], max_entries=6)
    assert len(rows) == 6
    titles = [r.title for r in rows]
    assert WORKBUDDY in titles
    assert len([r for r in rows if normalize_url(r.url) == URL]) == 1
    focuses = [editorial_focus({'title':r.title, 'url':r.url, 'source':r.source, 'site_id':r.site_id}) for r in rows]
    assert focuses == ['product'] * 5 + ['technical']
    assert all(score_ai_relevance({'title':r.title, 'url':r.url, 'source':r.source, 'site_id':r.site_id})['is_ai_related'] for r in rows)
    assert all('Mesh' not in t and '促销' not in t for t in titles)


def test_technical_cap_and_invalid_dates_do_not_fill_the_feed():
    rows = parse([
        *[item('DeepSeek 推理评测', f'https://www.ithome.com/t{i}') for i in range(6)],
        item(WORKBUDDY, URL, date=None),
        item(WORKBUDDY, URL, 'Tue, 27 Oct 2026 08:00:00 GMT'),
        item(WORKBUDDY, URL, 'Tue, 01 Sep 2026 08:00:00 GMT'),
    ])
    assert len(rows) == 2
    assert all(r.published_at <= NOW for r in rows)


def test_same_original_from_aihot_and_ithome_merges_into_one_event():
    rows = []
    for ident, source, site, title in [
        ('rss', 'IT之家', 'curated_media', WORKBUDDY),
        ('aihot', 'IT之家·人工智能', 'aihot', '腾讯 WorkBuddy 接入 Kimi-K3.1-Pro，支持 100 万上下文'),
    ]:
        rows.append({'id':ident, 'title':title, 'url':URL, 'source':source, 'site_id':site,
                     'published_at':'2026-10-24T07:59:12Z', 'ai_score':0.82, 'ai_is_related':True})
    stories, _ = merge_story_items(rows, now=NOW, window_hours=72)
    assert len(stories) == 1
    assert len({normalize_url(r['url']) for r in stories[0]['items']}) == 1


PRODUCT_EXAMPLES = [
    '蚂蚁灵光 2.0 发布：全新升级“能管事的 AI 助理”，突破单次对话限制',
    'Mac 版 Ollama 新增离线生成 AI 语音：数据不出门，速度比原方案最高快 35%',
    '苹果 Siri AI 即日起支持法语、日语、韩语等语言，繁体中文得等到年底前',
    '字节跳动旗下即梦 AI 短剧工作室上线，提供自研剧本、图片、分镜模型',
    '部分微软 Edge 浏览器用户反馈侧边栏 Copilot“失联”，官方称迁移需几天',
    'OpenAI 开放 ChatGPT 新插件：苹果用户授权后可充当 AI 管家，管理 iCloud 邮件、日程等',
]


def test_real_function_usage_and_availability_titles_survive_the_ithome_gate():
    rows = parse([item(t, f'https://www.ithome.com/product-{i}') for i, t in enumerate(PRODUCT_EXAMPLES)])
    assert {r.title for r in rows} == set(PRODUCT_EXAMPLES)
    assert all(editorial_focus({'site_id':r.site_id, 'source':r.source,
                               'title':r.title, 'url':r.url}) == 'product' for r in rows)


def test_function_rescue_does_not_promote_benchmarks_promotions_or_general_business():
    rows = parse([
        item('Ollama 推理评测榜单第一', 'https://www.ithome.com/ollama-eval'),
        item('Siri 多语言识别基准测试', 'https://www.ithome.com/siri-eval'),
        item('蚂蚁灵光融资新进展，AI 行业估值提升', 'https://www.ithome.com/funding'),
        item('苹果 Siri 联名手机壳新品促销', 'https://www.ithome.com/case-sale'),
        item('生活里的一次灵光乍现，AI 会改变一切', 'https://www.ithome.com/phrase'),
    ])
    assert {r.url for r in rows} == {'https://www.ithome.com/ollama-eval', 'https://www.ithome.com/siri-eval'}
    assert all(editorial_focus({'title':r.title, 'url':r.url}) == 'technical' for r in rows)
