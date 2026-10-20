from datetime import datetime, timezone
from unittest.mock import Mock

from scripts.update_news import OFFICIAL_AI_FEEDS, fetch_feed_as_official_items, parse_curated_ai_media_feed_items, CURATED_AI_MEDIA_FEEDS
from scripts.ai_relevance import score_ai_relevance

NOW = datetime(2026, 10, 20, 8, tzinfo=timezone.utc)


def test_engineering_feed_caps_ai_items_without_filling_with_unrelated_or_undated_posts():
    feed = next(f for f in OFFICIAL_AI_FEEDS if f['title'] == 'Meta Engineering Blog') | {'max_entries': 1}
    session = Mock()
    session.get.return_value.content = b'''<rss><channel>
    <item><title>Office furniture</title><link>https://engineering.fb.com/furniture</link><pubDate>Mon, 19 Oct 2026 10:00:00 GMT</pubDate></item>
    <item><title>AI with no date</title><link>https://engineering.fb.com/undated</link></item>
    <item><title>AI agent architecture</title><link>https://engineering.fb.com/agent</link><pubDate>Mon, 19 Oct 2026 10:00:00 GMT</pubDate></item>
    <item><title>AI model architecture</title><link>https://engineering.fb.com/model</link><pubDate>Mon, 19 Oct 2026 09:00:00 GMT</pubDate></item>
    </channel></rss>'''
    rows = fetch_feed_as_official_items(session, feed, NOW)
    assert [r.url for r in rows] == ['https://engineering.fb.com/agent']


def test_testing_catalog_product_article_survives_fetch_and_relevance():
    feed = next(f for f in CURATED_AI_MEDIA_FEEDS if f['title'] == 'Testing Catalog')
    xml = b'''<rss><channel><item><title>Krea launched Krea 3 for image editing</title>
    <link>https://www.testingcatalog.com/krea-3/</link><pubDate>Mon, 19 Oct 2026 10:00:00 GMT</pubDate>
    </item></channel></rss>'''
    item = parse_curated_ai_media_feed_items(xml, feed, NOW)[0]
    assert score_ai_relevance({'site_id': item.site_id, 'source': item.source, 'title': item.title, 'url': item.url})['is_ai_related']
