"""Regression cases from the Nov 5 original-source coverage audit."""
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from scripts.ai_relevance import add_ai_relevance_fields
from scripts.editorial_focus import editorial_focus
from scripts.focus_sources import load_sources, matched_sources
from scripts.update_news import (
    add_bilingual_fields, apply_public_raw_meta, build_story_record,
    fetch_aihot_focus, make_item_id, merge_story_items, parse_aihot_api_items,
)

NOW = datetime(2026, 11, 5, 4, 3, tzinfo=timezone.utc)
LUMA = 'https://x.com/LumaLabsAI/status/2118161379731677274'
VIGGLE = 'https://x.com/ViggleAI/status/2118012913793290414'
GOOGLE = 'https://x.com/Google/status/2118027058794148099'
REPLY = 'https://x.com/Google/status/2118027061948547270'


def entry(title, url, date='2026-11-04T17:06:16Z', score=54):
    return dict(id=url, title=title, links={'original': url},
                source={'name': 'AIHOT source label'}, score=score,
                selected=False, publishedAt=date,
                summary='今天首次上线新功能', originalTitle='Provider title')


def collect(*pages):
    session = Mock()
    session.get.return_value.json.side_effect = [
        {'schemaVersion': 1, 'items': items, 'page': {
            'hasMore': i < len(pages) - 1, 'nextCursor': str(i + 1),
        }} for i, items in enumerate(pages)
    ]
    return fetch_aihot_focus(session, NOW)


def row(raw):
    record = dict(id=make_item_id(raw.site_id, raw.source, raw.title, raw.url),
                  title=raw.title, url=raw.url, source=raw.source,
                  site_id=raw.site_id, published_at=raw.published_at.isoformat())
    apply_public_raw_meta(record, raw)
    return add_ai_relevance_fields(record)


@pytest.mark.parametrize('title,url,date', [
    ('Luma 推出 Photo Reframe，一张图自动适配多种版式', LUMA, '2026-11-05T02:00:01Z'),
    ('Viggle 发布视频转换 Agent Viggle Remake 并开放权重', VIGGLE, '2026-11-04T16:10:04Z'),
])
def test_product_recognition_and_verified_original_are_independent(title, url, date):
    assert editorial_focus({'title': title, 'url': url}) == 'product'
    [raw] = collect([entry(title, url, date)])
    record = row(raw)
    assert record['ai_is_related'] and record['editorial_focus'] == 'product'
    assert raw.published_at == datetime.fromisoformat(date.replace('Z', '+00:00'))
    assert '用法' in record['title'] and record['provided_title_zh'] == record['title']
    assert '首次上线日期未核验' in record['summary']
    assert '今天首次上线' not in record['summary']


def test_google_exact_match_and_non_product_chatter():
    assert len(load_sources()) == 48
    assert [s['id'] for s in matched_sources({'url': GOOGLE})] == ['supplement-google-official']
    for url in ('https://x.com/Google_fake/status/1', 'https://x.com.fake.test/Google/status/1'):
        assert not matched_sources({'url': url, 'source': 'Google官方账号'})
        assert collect([entry('Gemini 上线语音功能', url)]) == []
    assert collect([entry('Happy holidays!', 'https://x.com/Google/status/1')]) == []
    assert editorial_focus({'title': 'Luma Photo Reframe 扩图评测', 'url': LUMA}) == 'technical'
    assert editorial_focus({'title': 'Viggle Remake 模型评测', 'url': VIGGLE}) == 'technical'


def test_thread_follow_up_collapses_even_across_pages_and_selected_overlap():
    primary = entry('Voice Remixing 上线', GOOGLE, score=80)
    follow_up = entry('Google AI Studio 语音重混功能',
                      REPLY.replace('x.com/Google', 'twitter.com/google') + '?s=20',
                      '2026-11-04T17:06:17Z')
    [raw] = collect([follow_up], [primary])
    [only_reply] = collect([follow_up])
    [selected] = parse_aihot_api_items({'items': [primary]}, NOW)
    actual = row(raw)
    assert actual['id'] == row(only_reply)['id'] == row(selected)['id']
    assert raw.url == GOOGLE and raw.site_id == 'aihot'
    assert raw.published_at == datetime(2026, 11, 4, 17, 6, 16, tzinfo=timezone.utc)
    assert '并排试听' in actual['summary'] and '首次上线日期未核验' in actual['summary']
    enriched, _, _ = add_bilingual_fields([actual], [actual], Mock(), {}, max_new_translations=0)
    story = build_story_record('google-voice', enriched, NOW, 24)
    assert '用法' in story['title']
    assert parse_aihot_api_items({'items': [follow_up]}, NOW) == []


def test_same_event_media_copy_merges_and_distinct_feature_stays_separate():
    [raw] = collect([entry('Voice Remixing 上线', GOOGLE)])
    original = row(raw)
    media = original | {'id': 'media', 'url': 'https://example.com/google-voice-remixing', 'site_id': 'curated_media'}
    distinct = original | {'id': 'distinct', 'url': 'https://x.com/Google/status/123', 'title': 'Gemini 新增团队协作权限管理'}
    stories, _ = merge_story_items([original, media, distinct], NOW, 24)
    assert sorted(s['item_count'] for s in stories) == [1, 2]


PERPLEXITY_CASE = 'https://x.com/perplexity_ai/status/2118035494898704781'
PERPLEXITY_QUOTE = 'https://x.com/AravSrinivas/status/2118037327796973770'
PERPLEXITY_FAST = 'https://x.com/AravSrinivas/status/2118093720243560711'


def test_customer_case_and_founder_quote_share_the_company_original():
    original = entry('Perplexity Computer 助龙虾商广告增效', PERPLEXITY_CASE,
                     '2026-11-04T17:39:47Z', score=40)
    quote = entry('Perplexity智能体广告投放胜过广告公司', PERPLEXITY_QUOTE,
                  '2026-11-04T17:47:04Z', score=62)
    [raw] = collect([quote], [original])
    [selected] = parse_aihot_api_items({'items': [quote]}, NOW)
    record = row(raw)
    assert record['id'] == row(selected)['id']
    assert raw.url == PERPLEXITY_CASE and raw.source == 'X：Perplexity (@perplexity_ai)'
    assert raw.published_at == datetime(2026, 11, 4, 17, 39, 47, tzinfo=timezone.utc)
    assert record['ai_is_related'] and record['editorial_focus'] == 'product'
    assert '客户案例' in record['title'] and '上线' not in record['title']
    assert '测试预算' in record['summary'] and '今天首次上线' not in record['summary']


def test_fast_search_exact_post_is_personal_and_distinct_from_commerce_case():
    from scripts.source_tiers import attach_select_tier
    from scripts.update_news import source_tier_for_record

    items = collect([
        entry('Perplexity 将 Fast Search 接入 Decisions API', PERPLEXITY_FAST,
              '2026-11-04T21:31:09Z', score=47),
        entry('Perplexity Computer 助龙虾商广告增效', PERPLEXITY_CASE,
              '2026-11-04T17:39:47Z', score=40),
        entry('Perplexity 新增协作功能', 'https://x.com/AravSrinivas/status/9'),
    ])
    assert {raw.url for raw in items} == {PERPLEXITY_CASE, PERPLEXITY_FAST}
    raw = next(raw for raw in items if raw.url == PERPLEXITY_FAST)
    [source] = matched_sources({'url': raw.url})
    assert source['identity_kind'] == 'personal_account'
    record = row(raw)
    attach_select_tier(record, site_id=raw.site_id, source=raw.source, meta=raw.meta)
    assert record['select_tier'] == 'T2' and source_tier_for_record(raw.site_id, raw.source) is None
    assert '创始人个人账号' in raw.source and '官方' not in raw.source
    assert raw.published_at == datetime(2026, 11, 4, 21, 31, 9, tzinfo=timezone.utc)
    assert 'web_grounding' in record['summary']
    stories, _ = merge_story_items([row(item) for item in items], NOW, 24)
    assert len(stories) == 2


GROK_TEAM = 'https://x.com/poteto/status/2116576229319233596'
GROK_ROUTINES = 'https://x.com/poteto/status/2116580481236115933'


def test_grok_bot_team_guide_merges_routine_reply_at_the_original_date():
    from scripts.source_tiers import attach_select_tier

    primary = entry('Grok Bot 工程负责人分享创建高质量 bot 与管理 bot 团队的方法',
                    GROK_TEAM, '2026-10-31T17:01:11Z', score=61)
    reply = entry('xAI 工程师分享 Grok Bot 使用技巧：routines 与自动化',
                  GROK_ROUTINES, '2026-10-31T17:18:05Z', score=43)
    unrelated = entry('Some thoughts about managing projects', 'https://x.com/poteto/status/99')
    retelling = entry('Grok Bot 团队管理小指南：少而精、存技能、用语音',
                      'https://x.com/indigox/status/2116690187006971959', '2026-11-01T00:34:01Z')
    [raw] = collect([retelling, unrelated], [reply], [primary])
    [selected] = parse_aihot_api_items({'items': [primary]}, NOW)
    record = row(raw)
    attach_select_tier(record, site_id=raw.site_id, source=raw.source, meta=raw.meta)
    assert record['id'] == row(selected)['id']
    assert raw.url == GROK_TEAM and raw.site_id == 'aihot'
    assert raw.published_at == datetime(2026, 10, 31, 17, 1, 11, tzinfo=timezone.utc)
    assert record['select_tier'] == 'T2' and '个人账号' in raw.source
    assert record['ai_is_related'] and record['editorial_focus'] == 'product'
    assert '用法' in record['title'] and '上线' not in record['title']
    assert all(term in record['summary'] for term in ('技能', 'Slack', 'Routines', 'Notion'))
