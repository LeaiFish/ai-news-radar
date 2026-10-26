from datetime import datetime, timezone
from types import SimpleNamespace
import json

from scripts.wechat_wemprss import collect, merge_result
from scripts.publish_wechat_snapshot import merged_snapshot, public_snapshot

NOW = datetime(2026, 10, 22, 4, tzinfo=timezone.utc)
JOB = {'company_id': 'deepseek', 'account_name': 'DeepSeek', 'book_id': 'MP_WXS_123'}

def response(body):
    def not_json(): raise ValueError()
    return SimpleNamespace(text=body, encoding='utf-8', raise_for_status=lambda: None, json=not_json)

def body(token, date='2026-10-22 11:00', name='DeepSeek'):
    return f'<h1 id="activity-name">AI update {token}</h1><a id="js_name">{name}</a><em id="publish_time">{date}</em>'

def page(*tokens):
    return {'reviews': [{'subReviews': [{'review': {'reviewId': JOB['book_id']+'_'+t}} for t in tokens]}]}

class Reader:
    def __init__(self, pages=None, bodies=None, list_error=None):
        self.pages = pages or [page('one', 'two', 'three'), {'reviews': []}]
        self.bodies = bodies or {}
        self.list_error = list_error
        self.list_calls = []; self.content_calls = []; self.cover_calls = 0
    def _get_mp_articles_page(self, book, offset=0):
        self.list_calls.append((book, offset))
        if self.list_error: raise self.list_error
        return self.pages[len(self.list_calls)-1]
    def _get_mp_cover(self, book):
        self.cover_calls += 1
        return {'name': 'DeepSeek', 'reviewId': book+'_one'}
    def _weread_http_get(self, url, *, params, **kwargs):
        token=params['reviewId'].removeprefix(JOB['book_id']+'_')
        self.content_calls.append(token)
        return response(self.bodies.get(token, body(token)))

def discover(*args, **kwargs):
    return {'ok': True, 'truncated': False, 'candidates': []}

def run(reader, **kwargs):
    return collect(reader, [JOB], NOW, delay=lambda _: None, public_discovery=discover, **kwargs)

def test_lists_expand_all_subarticles_and_offset_counts_groups():
    reader=Reader()
    result=run(reader)
    assert len(result['rows']) == 3
    assert reader.list_calls == [('MP_WXS_123',0),('MP_WXS_123',1)]
    assert reader.cover_calls == 0
    snapshot=merge_result(result,None,[JOB],NOW)
    assert snapshot['last_run']['verified'] == 3
    assert snapshot['last_run']['coverage_complete'] is True
    assert snapshot['last_run']['ok'] is True

def test_old_entry_does_not_hide_later_new_subarticle_in_same_page():
    reader=Reader(pages=[page('old','new'),{'reviews':[]}], bodies={'old':body('old','2026-10-19 11:00')})
    result=run(reader)
    assert any(r['title']=='AI update new' for r in result['rows'])
    assert len(reader.list_calls)==2

def test_recent_articles_survive_candidate_and_archive_caps():
    tokens=[f'new{i}' for i in range(25)]
    reader=Reader(pages=[page(*tokens),{'reviews':[]}])
    snapshot=merge_result(run(reader),None,[JOB],NOW)
    assert snapshot['last_run']['verified']==25
    assert snapshot['last_run']['recent_24h']==25
    assert len(snapshot['accounts']['deepseek'])==25
    remote=public_snapshot(snapshot,NOW)
    merged=merged_snapshot(snapshot,remote,NOW)
    assert len(merged['accounts']['deepseek'])==25
    assert merged['last_run']['added']==remote['last_run']['added']

def test_page_cap_is_visible_and_keeps_verified_rows():
    result=run(Reader(),max_pages=1)
    snapshot=merge_result(result,None,[JOB],NOW)
    assert snapshot['last_run']['verified']==3
    assert snapshot['last_run']['ok'] is False
    assert snapshot['last_run']['coverage_complete'] is False
    assert any(e['error']=='wemprss_list_limit' for e in snapshot['last_run']['errors'])

def test_denied_list_falls_back_to_multiple_public_candidates_without_leaking_errors():
    error=RuntimeError('PRIVATE upstream credentials'); error.code=-2041
    reader=Reader(list_error=error)
    urls=['https://mp.weixin.qq.com/s/extra1','https://mp.weixin.qq.com/s/extra2']
    def discovery(*args,**kwargs):
        return {'ok':True,'truncated':False,'candidates':[dict(JOB,url=u) for u in urls]}
    def verify(candidate,job,now):
        from scripts.wechat_sources import parse_article
        row=parse_article(body('public'),'DeepSeek',candidate['url'],now)
        return row|{'company_id':'deepseek','evidence_url':candidate['url']}
    result=collect(reader,[JOB],NOW,delay=lambda _:None,public_discovery=discovery,public_verifier=verify)
    snapshot=merge_result(result,None,[JOB],NOW)
    assert snapshot['last_run']['verified']==3
    assert snapshot['last_run']['coverage_complete'] is False
    assert snapshot['last_run']['collection_state']=='partial'
    assert 'PRIVATE' not in json.dumps(result)
    clean=public_snapshot(snapshot,NOW)
    assert clean['last_run']['account_coverage'][0]['state']=='fallback'
    assert any(e['error']=='wemprss_list_api_-2041' for e in clean['last_run']['errors'])

def test_rate_limit_stops_private_requests_and_never_rotates_accounts():
    error=RuntimeError('PRIVATE');error.code=429
    reader=Reader(list_error=error)
    other=JOB|{'account_name':'千问APP','company_id':'qwen','book_id':'MP_WXS_456'}
    result=collect(reader,[JOB,other],NOW,delay=lambda _:None,public_discovery=discover)
    assert len(reader.list_calls)==1
    assert reader.cover_calls==0 and reader.content_calls==[]
    assert 'PRIVATE' not in json.dumps(result)
    snapshot=merge_result(result,None,[JOB,other],NOW)
    assert snapshot['last_run']['collection_state']=='failed'

def test_unknown_html_date_does_not_become_list_time_or_now():
    reader=Reader(pages=[page('one'),{'reviews':[]}],bodies={'one':'<h1 id="activity-name">AI news</h1><a id="js_name">DeepSeek</a>'})
    snapshot=merge_result(run(reader),None,[JOB],NOW)
    assert snapshot['accounts']['deepseek'][0]['published'] is None
    assert snapshot['last_run']['recent_24h']==0
    assert snapshot['last_run']['coverage_complete'] is False

def test_coverage_allowlist_drops_credentials_and_unknown_fields():
    snapshot=merge_result(run(Reader()),None,[JOB],NOW)
    snapshot['last_run']['account_coverage'][0]['cookie']='PRIVATE'
    snapshot['last_run']['account_coverage'].append({'account_name':'PRIVATE','state':'complete'})
    clean=public_snapshot(snapshot,NOW)
    assert 'PRIVATE' not in json.dumps(clean)
    assert len(clean['last_run']['account_coverage'])==1

def test_time_budget_retains_partial_results_and_marks_remaining_work():
    ticks=iter([0,0,0,0,0,0,0,100,100,100,100,100,100,100,100,100,100,100,100,100])
    result=collect(Reader(),[JOB],NOW,delay=lambda _:None,public_discovery=discover,
                   clock=lambda:next(ticks,100),max_seconds=50)
    snapshot=merge_result(result,None,[JOB],NOW)
    assert not snapshot['last_run']['coverage_complete']
    assert any(e['error']=='wemprss_budget_exceeded' for e in snapshot['last_run']['errors'])

def test_private_transport_uses_one_session_and_no_account_failover():
    from scripts.wechat_wemprss import SingleAccountReader
    calls=[]
    sdk=SimpleNamespace(_weread_headers=lambda **kwargs:{'Cookie':'PRIVATE'})
    def get(url,**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'errCode':-2041})
    with __import__('pytest').raises(ValueError):
        SingleAccountReader(sdk,get=get)._get_mp_articles_page('MP_WXS_123')
    assert len(calls)==1
    assert calls[0]['allow_redirects'] is False

def test_public_discovery_flattens_pages_and_does_not_trust_list_date():
    from scripts.wechat_wemprss import discover_public
    calls=[]
    def get(url,**kwargs):
        calls.append(kwargs)
        more=len(calls)==1
        data={'schemaVersion':1,'items':[{'source':{'name':'公众号：DeepSeek'},
            'links':{'original':'https://mp.weixin.qq.com/s/'+str(len(calls))},'publishedAt':'PRIVATE'}],
            'page':{'hasMore':more,'nextCursor':'page2' if more else None}}
        return SimpleNamespace(raise_for_status=lambda:None,json=lambda:data)
    result=discover_public([JOB],NOW,get=get)
    assert len(result['candidates'])==2 and result['ok'] and not result['truncated']
    assert 'PRIVATE' not in json.dumps(result)
    assert calls[1]['params']['cursor']=='page2'
    assert all(c['params']['window']=='7d' and 'headers' not in c for c in calls)

def test_public_original_does_not_forward_credentials_or_follow_challenge():
    from scripts.wechat_wemprss import verify_public
    calls=[]
    def get(url,**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(status_code=302,headers={'Location':'https://mp.weixin.qq.com/mp/verify?token=PRIVATE'},raise_for_status=lambda:None)
    with __import__('pytest').raises(ValueError):
        verify_public({'url':'https://mp.weixin.qq.com/s?__biz=a&mid=1&idx=1&sn=a'},JOB,NOW,get=get)
    assert len(calls)==1
    assert set(calls[0]['headers'])=={'User-Agent'}

def test_list_denial_circuit_is_shared_across_publishers():
    error=RuntimeError('PRIVATE');error.code=-2041
    reader=Reader(list_error=error)
    other=JOB|{'company_id':'qwen','account_name':'千问APP','book_id':'MP_WXS_456'}
    # Return each requested publisher's real name; no private profile/shelf reads.
    reader._get_mp_cover=lambda book:{'name':'DeepSeek' if book=='MP_WXS_123' else '千问APP','reviewId':book+'_one'}
    result=collect(reader,[JOB,other],NOW,delay=lambda _:None,public_discovery=discover)
    assert len(reader.list_calls)==1
    assert not result['coverage_complete']
    assert any(e['error']=='wemprss_list_backend_unavailable' for e in result['errors'])

def test_public_service_failure_stops_remaining_original_requests():
    import requests
    error=RuntimeError('PRIVATE');error.code=-2041
    reader=Reader(list_error=error)
    calls=[]
    def discovery(*args,**kwargs):
        return {'ok':True,'truncated':False,'candidates':[
            dict(JOB,url='https://mp.weixin.qq.com/s/'+token) for token in ('extra1','extra2')]}
    def verify(candidate,job,now):
        calls.append(candidate['url'])
        raise requests.HTTPError(response=SimpleNamespace(status_code=503))
    result=collect(reader,[JOB],NOW,delay=lambda _:None,public_discovery=discovery,public_verifier=verify)
    assert len(calls)==1
    assert any(e['error']=='wemprss_http_503' for e in result['errors'])
    assert not result['coverage_complete']


def test_verified_friday_page_does_not_stop_monday_before_weekend_is_checked():
    monday=NOW.replace(day=26)
    reader=Reader(pages=[page('friday'),page('weekend'),{'reviews':[]}],
                  bodies={'friday':body('friday','2026-10-23 10:00'),
                          'weekend':body('weekend','2026-10-24 10:00')})
    result=collect(reader,[JOB],monday,delay=lambda _:None,public_discovery=discover)
    assert {'AI update friday','AI update weekend'} <= {r['title'] for r in result['rows']}
    assert len(reader.list_calls)==3


def test_public_leads_scan_seven_days_with_existing_caps():
    from scripts.wechat_wemprss import discover_public
    calls=[]
    def get(url,**kwargs):
        calls.append(kwargs['params'])
        return SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'schemaVersion':1,'items':[],
                               'page':{'hasMore':False,'nextCursor':None}})
    r=discover_public([JOB],NOW,get=get)
    assert r['ok'] and not r['truncated']
    assert calls[0]['window']=='7d' and calls[0]['mode']=='all'
