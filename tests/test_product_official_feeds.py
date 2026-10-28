from datetime import datetime, timezone
from unittest.mock import Mock
from xml.sax.saxutils import escape

import pytest

from scripts.ai_relevance import add_ai_relevance_fields, score_ai_relevance
from scripts.build_topics import is_curated_record
from scripts.editorial_focus import editorial_focus
from scripts.source_tiers import attach_select_tier
from scripts.update_news import (
    OFFICIAL_AI_FEEDS, apply_public_raw_meta, build_story_record,
    fetch_feed_as_official_items, merge_story_items, normalize_url,
)

NOW = datetime(2026, 10, 28, 3, tzinfo=timezone.utc)
DATE = 'Tue, 27 Oct 2026 12:30:00 GMT'
CASES = [
    ('Lovable Blog', 'Your workspace has undead apps',
     'https://lovable.dev/blog/your-workspace-has-undead-apps',
     'Forgotten projects can stay published, connected to data, and unowned. '
     'This Halloween, hunt them down in our free game, and see how Enterprise admins can clean up abandoned projects automatically.'),
    ('n8n Blog', 'Introducing n8n 3.0',
     'https://blog.n8n.io/introducing-n8n-v3/',
     'n8n 3.0 beta is out, focused on reliability, stability and security. Here is what is changing and how to get ready.'),
]


def item(title, url, summary='', date=DATE):
    return ('<item><title>' + escape(title) + '</title><link>' + escape(url) + '</link>'
            + ('<pubDate>' + date + '</pubDate>' if date else '')
            + '<description>' + escape(summary) + '</description></item>')


def fetch(name, entries, **overrides):
    feed = next(f for f in OFFICIAL_AI_FEEDS if f['title'] == name) | overrides
    session = Mock()
    session.get.return_value.content = ('<rss><channel>' + ''.join(entries) + '</channel></rss>').encode()
    return fetch_feed_as_official_items(session, feed, NOW)


def record(raw):
    row = dict(id=raw.url, title=raw.title, url=raw.url, source=raw.source,
               site_id=raw.site_id, site_name=raw.site_name, published_at=raw.published_at.isoformat())
    apply_public_raw_meta(row, raw)
    attach_select_tier(row, site_id=raw.site_id, source=raw.source, meta=raw.meta)
    return add_ai_relevance_fields(row)


@pytest.mark.parametrize('name,title,url,summary', CASES)
def test_real_product_headlines_survive_archive_relevance_and_curated_story(name, title, url, summary):
    raw = fetch(name, [item(title, url, summary)])[0]
    row = record(raw)
    assert row['title'] == title
    assert row['published_at'].startswith('2026-10-27')
    assert row['summary'] == summary
    assert row['select_tier'] == 'T1'
    assert row['ai_is_related']
    assert editorial_focus(row) == 'product'
    story = build_story_record('official-product', [row], NOW, 24)
    assert story['editorial_focus'] == 'product'
    assert is_curated_record(story, set())
    # An AIHOT copy of the same URL is one event, not a second launch.
    duplicate = row | {'id':'aihot-copy', 'site_id':'aihot'}
    stories, _ = merge_story_items([row, duplicate], now=NOW, window_hours=24)
    assert len(stories) == 1
    assert len({normalize_url(r['url']) for r in stories[0]['items']}) == 1


def test_product_priority_scans_beyond_benchmark_flood_with_cap_and_url_deduplication():
    name, title, url, summary = CASES[0]
    rows = fetch(name, [
        *[item('Lovable inference benchmark ' + str(i), f'https://lovable.dev/blog/eval-{i}') for i in range(9)],
        item(title, url + '?utm_source=aihot', summary), item(title, url, summary),
        item('Lovable adds a team collaboration workspace', 'https://lovable.dev/blog/teams'),
        item('Old undated feature', 'https://lovable.dev/blog/undated', date=None),
        item(title, 'https://lovable.dev/blog/future', summary, 'Thu, 29 Oct 2026 12:30:00 GMT'),
    ], max_entries=6)
    records = [record(r) for r in rows]
    assert [editorial_focus(r) for r in records] == ['product', 'product', 'technical', 'technical']
    assert sum(normalize_url(r['url']) == url for r in records) == 1
    assert all(r.published_at <= NOW for r in rows)


def test_source_summary_rescue_requires_exact_official_publisher_and_host():
    name, title, url, summary = CASES[0]
    row = dict(site_id='official_ai', source=name, title=title, url=url, summary=summary)
    assert score_ai_relevance(row)['is_ai_related']
    for changed in [row | {'url':'https://lovable.dev.example.org/blog/story'},
                    row | {'site_id':'newsnow'}, row | {'source':'Unknown Feed'}]:
        assert not score_ai_relevance(changed)['is_ai_related']


def test_new_official_feed_failures_have_individual_status(monkeypatch):
    import scripts.update_news as update
    # Exercise the real collector registration, while all unrelated sources are inert.
    for name in [n for n in dir(update) if n.startswith('fetch_')]:
        if name != 'fetch_feed_as_official_items':
            monkeypatch.setattr(update, name, lambda *args, **kwargs: [])
    monkeypatch.setattr(update, 'APP_SOURCES', ())
    def probe(session, feed, now):
        if feed['title'] == 'Lovable Blog':
            raise ValueError('RSS unavailable')
        return []
    monkeypatch.setattr(update, 'fetch_feed_as_official_items', probe)
    _, statuses = update.collect_all(Mock(), NOW)
    by_id = {s['site_id']:s for s in statuses}
    assert by_id['official_feed_lovable']['ok'] is False
    assert by_id['official_feed_n8n']['ok'] is True


@pytest.mark.parametrize('name,title,url,summary', CASES)
def test_product_feed_reaches_existing_topic_and_public_curated_projection(name, title, url, summary, tmp_path):
    import importlib.util
    import json
    from pathlib import Path
    from scripts.build_topics import build_topics_payload, load_topic_config
    row = record(fetch(name, [item(title, url, summary)])[0])
    story = build_story_record('official-product', [row], NOW, 24)
    config = load_topic_config(Path(__file__).parents[1] / 'config/topics.json')
    topics = build_topics_payload(config, {'stories':[story], 'latest':[row]}, generated_at=NOW.isoformat())
    details = topics.pop('_details')
    (tmp_path / 'topics').mkdir()
    for ident, data in details.items():
        (tmp_path / 'topics' / (ident + '.json')).write_text(json.dumps(data))
    for filename, data in [('topics.json', topics), ('latest-24h-all.json', {'items_all':[row]}),
                           ('stories-merged.json', {'stories':[story]}), ('daily-brief.json', {'items':[]})]:
        (tmp_path / filename).write_text(json.dumps(data))
    module_spec = importlib.util.spec_from_file_location('product_feed_export', Path(__file__).parents[1] / 'scripts/export-public-news.py')
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    module.NEWS = tmp_path
    public = module.export()
    rows = [x for x in public['items'] if x['links']['original'] == url]
    assert len(rows) == 1
    assert rows[0]['selected'] is True
    assert rows[0]['source']['name'] == name
    assert rows[0]['publishedAt'].startswith('2026-10-27')
    assert rows[0]['summary'] == summary
