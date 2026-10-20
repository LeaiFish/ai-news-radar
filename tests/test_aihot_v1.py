from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from scripts.update_news import parse_aihot_api_items, fetch_aihot

NOW = datetime(2026, 10, 20, 8, tzinfo=timezone.utc)


def test_v1_fields_keep_original_url_source_bilingual_title_and_unknown_date():
    rows = parse_aihot_api_items({'schemaVersion': 1, 'items': [
        {'id': 'v1', 'title': '产品更新', 'originalTitle': 'Product update',
         'source': {'name': 'Official Product'}, 'links': {'original': 'https://example.com/app', 'aihot': 'https://aihot.news/items/v1'},
         'score': 78, 'selected': True, 'publishedAt': None, 'discoveredAt': NOW.isoformat()},
        {'title': 'Broken link', 'links': {'aihot': 'https://aihot.news/items/missing'}, 'score': 90},
        {'title': 'Invalid score', 'links': {'original': 'https://example.com/nan'}, 'score': 'NaN'},
    ]}, NOW)
    assert len(rows) == 1
    assert rows[0].url == 'https://example.com/app'
    assert rows[0].source == 'Official Product'
    assert rows[0].published_at is None
    assert rows[0].meta['provided_title_en'] == 'Product update'


def test_fetch_rejects_wrong_envelope_instead_of_silent_success():
    session = Mock()
    session.get.return_value.json.return_value = {'items': [], 'schemaVersion': 2, 'page': {}}
    with pytest.raises(ValueError, match='AIHOT'):
        fetch_aihot(session, NOW)
