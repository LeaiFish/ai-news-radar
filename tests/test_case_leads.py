from datetime import datetime, timezone
from scripts.collect_case_leads import collect, parse_detail, parse_feed, sanitize

NOW = datetime(2026, 10, 27, tzinfo=timezone.utc)
URL = 'https://agentusecases.ai/use-case/sample'

def feed():
    return f'<rss><channel><item><title>Sort inbox</title><link>{URL}</link><pubDate>Mon, 26 Oct 2026 09:00:00 GMT</pubDate><description>Partial success</description></item></channel></rss>'.encode()

def page(category='Work &amp; Operations', date='Mar 28, 2026', url='https://example.com/original'):
    return f'<main><a href="/category/operations">{category}</a><p>Source: example.com · {date}</p><a href="{url}">Read the original ↗</a></main>'.encode()

def test_collection_time_never_becomes_original_date():
    result = collect(now=NOW, getter=lambda u: feed() if u.endswith('feed.xml') else page())
    row = result['items'][0]
    assert row['collected_at'] == '2026-10-26T09:00:00Z'
    assert row['first_seen_at'] == '2026-10-27T00:00:00Z'
    assert row['original_published_at'] == '2026-03-28'
    assert row['date_source'] == 'case_directory'
    assert 'published_at' not in row  # Cannot be accidentally treated as a news item.

def test_unknown_and_imprecise_dates_are_not_fabricated():
    row = parse_detail(page(date='Undated'))
    assert row['original_published_at'] is None
    assert row['original_date_label'] is None
    row = parse_detail(page(date='Sep 2026'))
    assert row['original_published_at'] is None
    assert row['original_date_precision'] == 'month'
    assert row['original_date_label'] == 'Sep 2026'

def test_only_priority_categories_and_no_related_category_leak():
    assert parse_detail(page(category='Shopping &amp; Errands'))['category'] == 'shopping'
    assert parse_detail(page(category='Life Admin &amp; Home'))['category'] == 'life'
    assert parse_detail(page(category='Money, Bills &amp; Benefits'))['category'] == 'life'
    raw = page(category='Software &amp; DevOps').replace(b'</main>', b'<a href="/category/operations">Work &amp; Operations</a></main>')
    assert parse_detail(raw) is None

def test_untrusted_feed_and_original_urls_are_not_accepted():
    assert parse_feed(feed().replace(URL.encode(), b'https://evil.example/use-case/sample'), NOW) == []
    for url in ['javascript:alert(1)', 'http://127.0.0.1/x', 'https://user:password@example.com/x']:
        assert parse_detail(page(url=url))['original_url'] is None

def test_feed_failure_preserves_previous_items_and_reports_stale_state():
    first = collect(now=NOW, getter=lambda u: feed() if u.endswith('feed.xml') else page())
    def fail(u): raise RuntimeError('request failed')
    second = collect(first, NOW, fail)
    assert second['items'] == first['items']
    assert second['generated_at'] == first['generated_at']
    assert second['status']['ok'] is False
    assert second['status']['partial'] is True

def test_detail_failure_preserves_known_case_and_first_discovery():
    first = collect(now=NOW, getter=lambda u: feed() if u.endswith('feed.xml') else page())
    def get(u):
        if u.endswith('feed.xml'): return feed()
        raise RuntimeError('detail unavailable')
    second = collect(first, NOW, get)
    assert second['items'] == first['items']
    assert second['status']['detail_failures'] == 1
    assert second['status']['partial'] is True
    assert 'secret' not in sanitize({**first['items'][0], 'secret': 'do not publish'})


def test_cli_refreshes_cases_separately_and_failure_export_has_no_unknown_fields(tmp_path, monkeypatch):
    import sys
    from scripts import build_topics, collect_case_leads
    first = collect(now=NOW, getter=lambda u: feed() if u.endswith('feed.xml') else page())
    def fail(u): raise RuntimeError('offline')
    failed = collect({**first, 'raw_body': 'never export'}, NOW, fail)
    assert 'raw_body' not in failed
    assert sanitize({'case_url': URL, 'category': []}) is None
    monkeypatch.setattr(collect_case_leads, 'collect', lambda previous: first)
    monkeypatch.setattr(sys, 'argv', ['build_topics.py', '--data-dir', str(tmp_path)])
    assert build_topics.main() == 0
    import json
    cases = json.loads((tmp_path / 'case-leads.json').read_text())
    topic = json.loads((tmp_path / 'topics/product-entry.json').read_text())
    assert cases['items'][0]['case_url'] == URL
    assert topic['items'] == []
