from datetime import datetime, timezone
import json
import requests
import pytest

from scripts.wechat_http import retry
from scripts import wechat_cloud as cloud
from scripts import wechat_sources as sources

NOW = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)


def failure(code, hint=None):
    r = requests.Response(); r.status_code = code; r._content_consumed = True
    if hint is not None:
        r.headers['Retry-After'] = hint
    return requests.HTTPError(response=r)


def test_retry_recovers_from_rate_limit_and_honors_retry_after():
    waits, calls = [], []
    def work():
        calls.append(True)
        if len(calls) == 1:
            raise failure(429, '7')
        return 'recovered'
    assert retry(work, sleep=waits.append) == 'recovered'
    assert waits == [7] and len(calls) == 2


@pytest.mark.parametrize('code', [401, 403, 404])
def test_auth_denial_and_missing_pages_are_not_retried(code):
    waits = []
    with pytest.raises(requests.HTTPError):
        retry(lambda: (_ for _ in ()).throw(failure(code)), sleep=waits.append)
    assert not waits


def test_long_retry_after_and_exhausted_retries_stop():
    waits = []
    with pytest.raises(requests.HTTPError):
        retry(lambda: (_ for _ in ()).throw(failure(429, '3600')), sleep=waits.append)
    assert waits == []
    with pytest.raises(requests.Timeout):
        retry(lambda: (_ for _ in ()).throw(requests.Timeout()), sleep=waits.append)
    assert waits == [2, 8]


def test_qwen_search_terms_share_canonical_identity_without_approving_other_accounts():
    def search(*args, **kwargs):
        return ['https://mp.weixin.qq.com/s/pilot']
    result = cloud.discover(NOW, search=search, companies={'qwen': ['通义千问', '通义实验室']})
    assert {c['account_name'] for c in result['candidates']} == {'通义实验室'}
    assert {s['account_name'] for s in result['searches']} == {'通义千问', '通义实验室'}
    assert sources.identity('quark', '通义千问') is None


def test_mismatch_is_rejection_not_failure_but_identity_is_checked_before_fetch():
    names = [n for names in sources.targets().values() for n in names]
    data = {'searches': [{'account_name': n, 'ok': True} for n in names], 'candidates': [
        {'company_id': 'qwen', 'account_name': '千问APP',
         'url': 'https://mp.weixin.qq.com/s?__biz=wrong&mid=1&idx=1&sn=abc'}]}
    def no_fetch(*args):
        pytest.fail('Known different publisher should be rejected before fetching')
    result = sources.sync(data, None, NOW, verifier=no_fetch)
    assert result['last_run']['ok'] and result['last_run']['rejected'] == 1
    assert not result['last_run']['errors']
    data['searches'][0] = {'account_name': names[0], 'ok': False, 'error': 'search_rate_limited'}
    result = sources.sync(data, None, NOW, verifier=no_fetch)
    assert result['last_run']['errors'][0]['error'] == 'search_rate_limited'


def test_partial_collection_is_not_fatal_but_all_sources_unavailable_is():
    assert cloud.collection_state({'searched_accounts': 1, 'candidates': 5, 'verified': 1, 'errors': [{'error': 'http_429'}]}, {}) == 'partial'
    assert cloud.collection_state({'searched_accounts': 0, 'candidates': 0, 'verified': 0, 'errors': [{}]}, {}) == 'failed'
    assert cloud.collection_state({'searched_accounts': 1, 'candidates': 0, 'verified': 0, 'errors': []}, {}) == 'complete'


def test_recent_discovery_keeps_budget_before_historical_search(tmp_path, monkeypatch):
    fresh = {'company_id': 'qwen', 'account_name': '千问APP', 'url': 'https://mp.weixin.qq.com/s/today'}
    historical = [fresh | {'url': f'https://mp.weixin.qq.com/s/old{i}'} for i in range(10)]
    monkeypatch.setattr(cloud, 'discover', lambda now: {'searches': [{'account_name': '千问APP', 'ok': True}], 'candidates': historical})
    monkeypatch.setattr(cloud, 'aihot_candidates', lambda *a, **kw: {'ok': True, 'candidates': [fresh]})
    output = tmp_path / 'candidates.json'
    monkeypatch.setattr('sys.argv', ['wechat_cloud.py', '--output', str(output)])
    assert cloud.main() == 0
    rows = json.loads(output.read_text())['candidates']
    assert rows[0] == fresh and len(rows) == 10


def test_recent_24h_is_not_the_number_of_newly_archived_posts():
    names = [n for names in sources.targets().values() for n in names]
    data = {'searches': [{'account_name': n, 'ok': True} for n in names], 'candidates': [
        {'company_id': 'qwen', 'account_name': '千问APP', 'url': 'https://mp.weixin.qq.com/s/history'}]}
    def verify(candidate, now):
        return dict(candidate, title='Historical article', account_verified=True,
                    published='2026-10-15T09:54:00Z', verified_at=sources.iso(now), evidence_url=candidate['url'])
    run = sources.sync(data, None, NOW, verifier=verify)['last_run']
    assert run['added'] == 1 and run['recent_24h'] == 0
    assert run['pilot_recent_7d']['千问APP'] == 1
