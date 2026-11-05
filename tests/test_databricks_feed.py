"""Official RSS intake and a dated integration guide, not a new launch."""
from datetime import datetime, timezone
from unittest.mock import Mock
from xml.sax.saxutils import escape

import pytest

from scripts.ai_relevance import add_ai_relevance_fields, score_ai_relevance
from scripts.editorial_focus import editorial_focus
from scripts.product_context import product_context
from scripts.update_news import (
    OFFICIAL_AI_FEEDS, apply_public_raw_meta, fetch_feed_as_official_items,
    merge_story_items, add_bilingual_fields,
)

NOW = datetime(2026, 11, 5, 4, tzinfo=timezone.utc)
GUIDE = 'https://www.databricks.com/blog/claude-platform-now-supports-native-opentelemetry-observability-databricks-mlflow'
TITLE = 'Claude Platform now supports native OpenTelemetry observability in Databricks MLflow'
DATE = 'Tue, 03 Nov 2026 21:00:00 GMT'


def item(title, url, summary='', date=DATE):
    return ('<item><title>' + escape(title) + '</title><link>' + escape(url)
            + '</link>' + ('<pubDate>' + date + '</pubDate>' if date else '')
            + '<description>' + escape(summary) + '</description></item>')


def fetch(entries):
    feed = next(f for f in OFFICIAL_AI_FEEDS if f['title'] == 'Databricks Blog')
    session = Mock()
    session.get.return_value.content = ('<rss><channel>' + ''.join(entries) + '</channel></rss>').encode()
    return fetch_feed_as_official_items(session, feed, NOW)


def record(raw):
    row = {'id': raw.url, 'url': raw.url, 'title': raw.title, 'site_id': raw.site_id,
           'site_name': raw.site_name, 'source': raw.source,
           'published_at': raw.published_at.isoformat()}
    apply_public_raw_meta(row, raw)
    return add_ai_relevance_fields(row)


def test_verified_guide_preserves_rss_date_and_explains_prior_capability():
    raw = fetch([item(TITLE, GUIDE)])[0]
    row = record(raw)
    assert raw.published_at.isoformat() == '2026-11-03T21:00:00+00:00'
    assert raw.meta['select_tier'] == 'T1'
    assert raw.site_id == 'official_ai'
    assert '指南' in row['title']
    assert '首次上线' in row['summary']
    assert row['ai_is_related']
    assert editorial_focus(row) == 'product'
    enriched, _, _ = add_bilingual_fields([row], [row], Mock(), {}, 0)
    assert '指南' in enriched[0]['title_bilingual']
    assert enriched[0]['title_original'] == TITLE
    assert fetch([item(TITLE, GUIDE, date=None)]) == []
    session = Mock()
    session.get.return_value.content = (
        '<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>' + TITLE
        + '</title><link href="' + GUIDE + '"/><updated>2026-11-04T21:00:00Z</updated>'
        + '</entry></feed>').encode()
    feed = next(f for f in OFFICIAL_AI_FEEDS if f['title'] == 'Databricks Blog')
    assert fetch_feed_as_official_items(session, feed, NOW) == []


def test_product_guidance_wins_over_technical_flood_without_whitelisting_sql():
    rows = fetch([
        *[item(f'Databricks AI inference benchmark {i}', f'https://www.databricks.com/blog/benchmark-{i}') for i in range(9)],
        item(TITLE, GUIDE + '?utm_source=aihot'), item(TITLE, GUIDE),
        item('How to build AI agent workflows with Genie', 'https://www.databricks.com/blog/genie-workflows'),
        item('Declare and optimize UNIQUE constraints', 'https://www.databricks.com/blog/constraints',
             'Maintain database constraints and column indexes.'),
        item('How to use SQL to maintain tables', 'https://www.databricks.com/blog/sql-guide'),
        item('Future Claude API guide', 'https://www.databricks.com/blog/future', date='Fri, 06 Nov 2026 01:00:00 GMT'),
    ])
    assert len(rows) == 4
    assert [editorial_focus(record(r)) for r in rows] == ['product', 'product', 'technical', 'technical']
    assert rows[0].url.split('?')[0] == GUIDE
    assert all('constraints' not in r.url and 'sql-guide' not in r.url for r in rows)
    assert len({r.url.split('?')[0] for r in rows}) == len(rows)


def test_official_summary_product_evidence_requires_ai_and_exact_feed_host():
    row = {'title': 'Your team can now work together', 'url': 'https://www.databricks.com/blog/genie',
           'site_id': 'official_ai', 'source': 'Databricks Blog',
           'summary': 'Genie AI agents now support team workspaces and shared workflows.'}
    assert editorial_focus(row) == 'product'
    assert score_ai_relevance(row)['is_ai_related']
    for fields in [{'url': 'https://databricks.com.attacker/blog/genie'},
                   {'site_id': 'newsnow'}, {'source': 'Copied publisher'}]:
        assert product_context(row | fields) is None
    assert product_context(row | {'title': 'How to use SQL tables', 'summary': 'Manage table constraints.'}) is None


def test_same_guide_url_and_same_event_media_copy_merge_once():
    row = record(fetch([item(TITLE, GUIDE)])[0])
    rows, _, _ = add_bilingual_fields([row], [row], Mock(), {}, 0)
    primary = rows[0]
    copy = primary | {'id': 'aihot-copy', 'site_id': 'aihot', 'url': GUIDE + '?utm_source=aihot'}
    media = primary | {'id': 'media-copy', 'site_id': 'curated_media', 'url': 'https://example.com/claude-mlflow-guide'}
    distinct = primary | {'id': 'distinct', 'title_original': 'Claude adds image editing in chat',
                          'title': 'Claude adds image editing in chat', 'url': 'https://example.com/another-feature'}
    stories, _ = merge_story_items([primary, copy, media, distinct], NOW, 48)
    assert len(stories) == 2
    assert sorted(s['item_count'] for s in stories) == [1, 3]


def test_independent_health_and_html_response_failure(monkeypatch):
    import scripts.update_news as update
    feed = next(f for f in OFFICIAL_AI_FEEDS if f['title'] == 'Databricks Blog')
    assert feed['xml_url'] == 'https://www.databricks.com/feed'
    assert feed['status_id'] == 'official_feed_databricks'
    assert feed['max_entries'] == 6 and feed['max_technical_entries'] == 2
    session = Mock()
    session.get.return_value.content = b'<html>Challenge</html>'
    with pytest.raises(ValueError, match='RSS/Atom'):
        fetch_feed_as_official_items(session, feed, NOW)
    for name in [n for n in dir(update) if n.startswith('fetch_')]:
        monkeypatch.setattr(update, name, lambda *a, **kw: [])
    def failed(*args):
        raise ValueError('RSS unavailable')
    monkeypatch.setattr(update, 'OFFICIAL_AI_FEEDS', (feed,))
    monkeypatch.setattr(update, 'fetch_feed_as_official_items', failed)
    monkeypatch.setattr(update, 'APP_SOURCES', ())
    _, statuses = update.collect_all(Mock(), NOW)
    assert next(s for s in statuses if s['site_id'] == 'official_feed_databricks')['ok'] is False


def test_historical_guide_reaches_public_topics_without_rewriting_date(tmp_path):
    import importlib.util
    import json
    from pathlib import Path
    from scripts.build_topics import build_topics_payload, load_topic_config
    from scripts.source_tiers import attach_select_tier
    raw = fetch([item(TITLE, GUIDE)])[0]
    row = record(raw)
    attach_select_tier(row, site_id=raw.site_id, source=raw.source, meta=raw.meta)
    config = load_topic_config(Path(__file__).parents[1] / 'config/topics.json')
    # This two-day-old guide belongs to historical/topic coverage, not today's
    # 24-hour window. The topic builder and export must still preserve it.
    topics = build_topics_payload(config, {'archive': [row], 'latest': []}, generated_at=NOW.isoformat())
    details = topics.pop('_details')
    (tmp_path / 'topics').mkdir()
    for key, payload in details.items():
        (tmp_path / 'topics' / (key + '.json')).write_text(json.dumps(payload))
    for name, payload in [('topics.json', topics), ('latest-24h-all.json', {'items_all': []}),
                          ('stories-merged.json', {'stories': []}), ('daily-brief.json', {'items': []})]:
        (tmp_path / name).write_text(json.dumps(payload))
    spec = importlib.util.spec_from_file_location('databricks_public_export', Path(__file__).parents[1] / 'scripts/export-public-news.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.NEWS = tmp_path
    public = module.export()
    hits = [r for r in public['items'] if r['links']['original'] == GUIDE]
    assert len(hits) == 1
    assert hits[0]['publishedAt'] == row['published_at']
    assert '指南' in hits[0]['title']
    assert any(hits[0]['id'] in t['itemIds'] for t in public['topics'])
