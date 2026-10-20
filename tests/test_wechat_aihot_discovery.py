from datetime import datetime, timezone
import requests
from scripts.wechat_cloud import aihot_candidates

NOW = datetime(2026, 10, 20, 8, tzinfo=timezone.utc)
URL = 'https://mp.weixin.qq.com/s?__biz=BIZ&mid=1&idx=1&sn=abc'


def test_aihot_only_supplies_allowlisted_urls_and_does_not_import_its_metadata():
    calls = []
    def get(url, **kwargs):
        calls.append(kwargs)
        r = requests.Response();r.status_code = 200
        import json
        r._content = json.dumps({'schemaVersion': 1, 'items': [
            {'source': {'name': '公众号：千问APP（阿里）'}, 'links': {'original': URL},
             'title': 'Unverified title', 'publishedAt': NOW.isoformat()},
            {'source': {'name': '公众号：千问APP冒牌'}, 'links': {'original': URL}},
            {'source': {'name': '公众号：千问APP'}, 'links': {'original': 'https://example.com/fake'}},
        ], 'page': {'hasMore': True, 'nextCursor': 'page2'} if len(calls)==1 else {'hasMore': False}}).encode()
        return r
    result = aihot_candidates(NOW, companies={'qwen': ['千问APP']}, get=get)
    assert result['candidates'] == [{'company_id': 'qwen', 'account_name': '千问APP', 'url': URL}]
    assert result['ok'] is True and result['pages'] == 2 and not result['truncated']
    assert calls[1]['params']['cursor'] == 'page2'
    assert calls[0]['params']['mode'] == 'all'


def test_aggregator_failure_is_reported_and_does_not_trigger_paid_or_legacy_fallback():
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        raise requests.Timeout()
    result = aihot_candidates(NOW, companies={'qwen': ['千问APP']}, get=get)
    assert not result['ok'] and result['error'] == 'Timeout' and not result['candidates']
    assert calls == ['https://aihot.news/api/v1/items']
