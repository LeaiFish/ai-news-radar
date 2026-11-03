"""Nov 3 verified originals: product evidence, exact accounts, recap dates."""
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from scripts.ai_relevance import add_ai_relevance_fields
from scripts.editorial_focus import editorial_focus
from scripts.focus_sources import load_sources, matched_sources
from scripts.product_context import product_context
from scripts.update_news import (
    add_bilingual_fields, apply_public_raw_meta, build_story_record,
    fetch_aihot_focus, merge_story_items,
    parse_aihot_api_items,
)

NOW = datetime(2026, 11, 3, 3, 19, tzinfo=timezone.utc)
LUMA = 'https://x.com/LumaLabsAI/status/2117445978320163139'
MUSE = 'https://x.com/Muse/status/2117349439278858715'


def entry(title, url, published='2026-11-03T02:37:16Z', **fields):
    return dict(id=url, title=title, links={'original': url},
                source={'name': 'AIHOT source label'}, score=42, selected=False,
                publishedAt=published, **fields)


def collect(entries):
    session = Mock()
    session.get.return_value.json.return_value = {
        'schemaVersion': 1, 'items': entries, 'page': {'hasMore': False},
    }
    return fetch_aihot_focus(session, NOW)


def record(raw):
    row = dict(id=raw.url, title=raw.title, url=raw.url, source=raw.source,
               site_id=raw.site_id, published_at=raw.published_at.isoformat())
    apply_public_raw_meta(row, raw)
    return add_ai_relevance_fields(row)


@pytest.mark.parametrize('title', [
    'Luma 推出 Expression Sheet 角色表情表',
    'Expression Sheet lets you work through a character’s performance. Now in Luma.',
    'Expression Sheet is now available',
])
def test_luma_concrete_character_creation_function_survives_focus_and_relevance(title):
    raw = collect([entry(title, LUMA)])
    assert len(raw) == 1
    row = record(raw[0])
    assert row['ai_is_related']
    assert editorial_focus(row) == 'product'


def test_muse_exact_official_account_is_supplemental_not_a_name_whitelist():
    assert len(load_sources()) == 48
    sources = matched_sources({'url': MUSE})
    assert [s['id'] for s in sources] == ['supplement-meta-muse']
    assert sources[0]['identity_kind'] == 'institution'
    for url in ['https://x.com/Muse_fake/status/1',
                'https://x.com.attacker.test/Muse/status/1',
                'https://example.com/Muse/status/1']:
        assert not matched_sources({'url': url, 'source': 'Muse官方账号'})
        assert collect([entry('Muse推出与智能体同玩Minecraft方式', url)]) == []


def test_verified_muse_recap_keeps_post_date_and_never_becomes_a_launch_claim():
    published = '2026-11-02T20:13:39Z'
    raw = collect([entry('Muse 推出与智能体同玩 Minecraft 方式', MUSE,
                         published, summary='今天新上线Minecraft功能')])
    assert len(raw) == 1
    row = record(raw[0])
    assert row['ai_is_related']
    assert editorial_focus(row) == 'product'
    assert '回顾' in row['title']
    assert row['provided_title_zh'] == row['title']
    assert '首次上线时间未核验' in row['summary']
    assert '今天新上线' not in row['summary']
    assert raw[0].published_at.isoformat() == '2026-11-02T20:13:39+00:00'
    assert raw[0].site_id == 'aihot'  # Indirect discovery remains indirect.
    # Bilingual enrichment/story projection must not restore a provider's
    # misleading Chinese launch headline after the correction.
    enriched, _, _ = add_bilingual_fields(
        [row | {'provided_title_en': 'Play Minecraft with your Muse'}],
        [row], Mock(), {}, max_new_translations=0)
    assert '回顾' in build_story_record('muse-recap', enriched, NOW, 24)['title']
    # This verified correction is exact-original scoped, not a rule that turns
    # every future Muse launch into a recap, nor a fallback for unknown dates.
    other = collect([entry('Muse新增对话功能', 'https://x.com/Muse/status/999')])
    assert other[0].title == 'Muse新增对话功能'
    assert collect([entry('Muse推出与智能体同玩Minecraft方式', MUSE, None)]) == []
    # Focus all-mode can admit low-score usage material while selected keeps
    # its existing score >=60 requirement.
    assert parse_aihot_api_items({'items': [entry('Muse功能回顾', MUSE)]}, NOW) == []


def test_same_original_and_syndicated_same_event_share_one_story_but_distinct_features_do_not():
    raw = collect([
        entry('Luma 推出 Expression Sheet 角色表情表', LUMA),
        entry('Luma 推出 Expression Sheet 角色表情表', LUMA + '?utm_source=copy'),
    ])
    assert len(raw) == 1
    row = record(raw[0])
    # Selected/all overlap and a media report of the same event use the existing
    # canonical-URL / high-title-similarity merger, not a second event counter.
    selected_copy = row | {'id': 'selected-copy', 'site_id': 'x_bridge'}
    media_copy = row | {'id': 'media-copy', 'site_id': 'curated_media',
                        'url': 'https://example.com/luma-expression-sheet'}
    distinct = row | {'id': 'distinct', 'title': 'Luma新增团队协作空间与成员权限管理',
                      'url': 'https://lumalabs.ai/news/team-workspace'}
    stories, _ = merge_story_items([row, selected_copy, media_copy, distinct], NOW, 24)
    assert len(stories) == 2
    assert sorted(s['item_count'] for s in stories) == [1, 3]


def test_official_account_does_not_promote_chatter_or_model_benchmarks():
    assert collect([entry('Happy holidays!', 'https://x.com/Muse/status/3')]) == []
    technical = {'title': 'Luma Expression Sheet 表情生成效果评测', 'url': LUMA}
    assert editorial_focus(technical) == 'technical'
    assert product_context({'title': 'Expression Sheet is now available',
                            'url': 'https://x.com/LumaLabsAI_fake/status/1'}) is None
