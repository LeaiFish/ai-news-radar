from datetime import datetime, timezone
import json

import pytest
import requests

from scripts import wechat_cloud as cloud

NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)
URL = 'https://mp.weixin.qq.com/s/official'


def response(content, *, code=200):
    r = requests.Response()
    r.status_code = code
    r._content = content.encode('utf-8')
    r._content_consumed = True
    r.encoding = 'utf-8'
    return r


def test_utf8_sse_and_public_url_normalization_without_trusting_metadata():
    text = f'官方链接 {URL}?token=PRIVATE，媒体日期昨天。 https://mp.weixin.qq.com.attacker/s/fake'
    body = {'jsonrpc': '2.0', 'id': 1, 'result': {'content': [{'type': 'text', 'text': text}]}}
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return response('event: message\ndata: ' + json.dumps(body, ensure_ascii=False) + '\n\n')
    assert cloud.search_articles('DeepSeek', NOW, post=post) == [URL]
    assert calls[0][0] == cloud.RECENT_SEARCH_URL
    assert 'Authorization' not in calls[0][1]['headers']
    assert calls[0][1]['json']['params']['arguments']['startPublishedDate'] == '2026-09-20'
    assert calls[0][1]['json']['params']['arguments']['includeDomains'] == ['mp.weixin.qq.com']


def test_multiline_sse_json_and_provider_errors():
    data = {'result': {'content': [{'type': 'text', 'text': URL}]}}
    pretty = json.dumps(data, indent=2)
    assert cloud.rpc_result('\n'.join('data: ' + line for line in pretty.splitlines()) + '\n\n') == URL
    assert cloud.rpc_result(json.dumps(data)) == URL
    for value in [{'error': {'code': -1}}, {'result': {'isError': True}}, {'result': {}}]:
        with pytest.raises(ValueError):
            cloud.rpc_result(json.dumps(value))
    with pytest.raises(ValueError):
        cloud.rpc_result('event: ping\n\n')


def test_search_fallback_dedup_and_failed_search_are_distinct():
    def search(account, now, broad=False):
        if account == 'broken':
            raise requests.Timeout()
        return [URL, URL] if broad else []
    result = cloud.discover(NOW, search=search, companies={'deepseek': ['DeepSeek', 'broken']})
    assert result['searches'] == [{'account_name': 'DeepSeek', 'ok': True},
                                  {'account_name': 'broken', 'ok': False, 'error': 'Timeout'}]
    assert result['candidates'] == [{'company_id': 'deepseek', 'account_name': 'DeepSeek', 'url': URL}]
    empty = cloud.discover(NOW, search=lambda *a, **k: [], companies={'deepseek': ['DeepSeek']})
    assert empty['searches'][0]['ok'] is True and not empty['candidates']


def test_rate_limit_stops_new_requests_without_bypassing_it():
    calls = []
    def limited(*args, **kwargs):
        calls.append(True)
        r = response('rate limit', code=429)
        raise requests.HTTPError(response=r)
    data = cloud.discover(NOW, search=limited, companies={'deepseek': [str(i) for i in range(24)]})
    assert len(calls) <= 2
    assert len(data['searches']) == 24 and not any(s['ok'] for s in data['searches'])
    assert not data['candidates']


def test_publication_rejects_old_snapshot_and_accepts_partial_collection_when_deployed():
    stamp = '2026-10-20T00:00:00Z'
    expected = {'last_run': {'at': stamp}}
    clock = [0]
    calls = []
    status = {'site_id': 'wechat_bridge', 'discovery': {'at': stamp}, 'item_count': 0, 'ok': False}
    def get(url, **kwargs):
        calls.append((url, kwargs))
        if url == cloud.SITE_URL:
            return response('')
        actual = status if clock[0] else status | {'discovery': {'at': 'old'}}
        return response(json.dumps({'sites': [actual]}))
    def sleep(seconds):
        clock[0] += seconds
    assert cloud.verify_publication(expected, get=get, clock=lambda: clock[0], sleep=sleep) == status
    assert clock[0] == 10
    assert calls[-1][1]['stream'] is True
    assert all('verify' in kw['params'] for url, kw in calls if url != cloud.SITE_URL)


def test_publication_timeout_does_not_claim_success():
    clock = [0]
    def sleep(seconds):
        clock[0] += seconds
    with pytest.raises(ValueError, match='verification_timeout'):
        cloud.verify_publication({'last_run': {'at': 'new'}}, timeout=20,
            get=lambda *a, **k: response(json.dumps({'sites': []})),
            clock=lambda: clock[0], sleep=sleep)
