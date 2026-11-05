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
