from datetime import datetime,timezone
from types import SimpleNamespace
import json
from pathlib import Path
import pytest
import requests
import yaml
from scripts.wechat_wemprss import (SingleAccountReader,collect_session,merge_result,persist_renewed_session)
from scripts.publish_wechat_snapshot import public_snapshot

NOW=datetime(2026,10,22,8,tzinfo=timezone.utc)
JOB={'company_id':'deepseek','account_name':'DeepSeek','book_id':'MP_WXS_123'}
OLD='wr_vid=123; wr_skey=PRIVATE-old; wr_rt=PRIVATE-refresh'

def sdk():
 obj=SimpleNamespace(_weread_cookies=OLD)
 obj._weread_headers=lambda **kwargs:{'Cookie':obj._weread_cookies}
 return obj

def response(data,updates=None):
 jar=requests.cookies.RequestsCookieJar()
 for k,v in (updates or {}).items():jar.set(k,v)
 return SimpleNamespace(json=lambda:data,raise_for_status=lambda:None,cookies=jar)

def discovery(*args,**kwargs):return {'ok':True,'truncated':False,'candidates':[]}

def content_get(calls):
 def get(url,**kwargs):
  calls.append((url,kwargs))
  if url.endswith('/articles'):return response({'reviews':[]})
  raise AssertionError('unexpected_request')
 return get

def test_normal_renewal_uses_false_ql_and_preserves_refresh_credential():
 calls=[];obj=sdk()
 def post(url,**kwargs):
  calls.append((url,kwargs));return response({'succ':1},{'wr_skey':'PRIVATE-new'})
 reader=SingleAccountReader(obj,post=post);reader.renew_session()
 assert len(calls)==1 and calls[0][1]['json']=={'rq':'%2Fweb%2Fbook%2Fread','ql':False}
 assert calls[0][1]['allow_redirects'] is False
 assert 'wr_rt=PRIVATE-refresh' in obj._weread_cookies
 assert 'wr_skey=PRIVATE-new' in obj._weread_cookies

@pytest.mark.parametrize('data',[{'errcode':-2013},{'succ':0},{'succ':True},{},[]])
def test_rejected_renewal_cannot_succeed_from_old_cookie_jar(data):
 obj=sdk();reader=SingleAccountReader(obj,post=lambda *a,**k:response(data,{'wr_skey':'PRIVATE-old'}))
 with pytest.raises(ValueError):reader.renew_session()
 assert obj._weread_cookies==OLD


def test_renewal_failure_stops_every_private_request_without_account_rotation():
 gets=[];posts=[];saves=[]
 def post(*args,**kwargs):posts.append(1);return response({'errcode':-2013})
 other=JOB|{'company_id':'qwen','account_name':'千问APP','book_id':'MP_WXS_456'}
 result=collect_session(sdk(),[JOB,other],NOW,get=content_get(gets),post=post,
  save=lambda *x:saves.append(x),delay=lambda _:None,public_discovery=discovery)
 assert len(posts)==1 and not gets and not saves
 assert all(c['state']=='blocked' for c in result['account_coverage'])
 clean=public_snapshot(merge_result(result,None,[JOB,other],NOW),NOW)
 assert 'PRIVATE' not in json.dumps(clean)
 assert any(e['error']=='wemprss_api_-2013' for e in clean['last_run']['errors'])


def test_normal_success_without_cookie_rotation_does_not_write_session():
 gets=[];saves=[]
 result=collect_session(sdk(),[JOB],NOW,get=content_get(gets),post=lambda *a,**k:response({'succ':1}),
  save=lambda *x:saves.append(x),delay=lambda _:None,public_discovery=discovery)
 assert result['coverage_complete'] and len(gets)==1
 assert not saves


def verified_collect(monkeypatch,rows):
 monkeypatch.setattr('scripts.wechat_wemprss.collect',lambda *a,**k:{'rows':rows,'errors':[],'coverage_complete':True})


def test_rotated_session_saved_only_after_article_verification(monkeypatch):
 saves=[]
 for rows in ([],[{'public':'verified'}]):
  verified_collect(monkeypatch,rows)
  collect_session(sdk(),[JOB],NOW,post=lambda *a,**k:response({'succ':1},{'wr_skey':'PRIVATE-new'}),
    save=lambda *x:saves.append(x))
 assert len(saves)==1
 assert saves[0][0]==OLD and 'PRIVATE-new' in saves[0][1]


def test_failed_persistence_is_explicit_and_never_logs_credentials(monkeypatch):
 verified_collect(monkeypatch,[{'public':'verified'}])
 def save(*args):raise PermissionError('PRIVATE')
 result=collect_session(sdk(),[JOB],NOW,post=lambda *a,**k:response({'succ':1},{'wr_skey':'PRIVATE-new'}),save=save)
 assert result['coverage_complete'] is False
 assert result['errors']==[{'error':'wemprss_renewal_persist_failed'}]
 assert 'PRIVATE' not in json.dumps(result)


def test_renewal_cannot_change_reader_account():
 obj=sdk();reader=SingleAccountReader(obj,post=lambda *a,**k:response({'succ':1},{'wr_vid':'other'}))
 with pytest.raises(ValueError):reader.renew_session()
 assert obj._weread_cookies==OLD


@pytest.mark.parametrize('string_format',[False,True])
def test_atomic_session_save_preserves_unrelated_private_data_and_rejects_stale_writes(tmp_path,string_format):
 path=tmp_path/'wx.lic'
 auth={'accounts':[{'cookie':OLD,'vid':'123','name':'PRIVATE-name'}],'other':'PRIVATE-setting'}
 document={'weread_data':json.dumps(auth) if string_format else auth,'unrelated':{'setting':'PRIVATE'}}
 path.write_text(yaml.safe_dump(document))
 persist_renewed_session(OLD,'PRIVATE-new',path)
 saved=yaml.safe_load(path.read_text());stored=saved['weread_data']
 if string_format:stored=json.loads(stored)
 assert stored['accounts'][0]['cookie']=='PRIVATE-new'
 assert stored['accounts'][0]['name']=='PRIVATE-name'
 assert saved['unrelated']==document['unrelated'] and stored['other']=='PRIVATE-setting'
 assert path.stat().st_mode & 0o777==0o600
 with pytest.raises(ValueError,match='session_changed_concurrently'):
  persist_renewed_session(OLD,'PRIVATE-stale',path)
 assert list(tmp_path.iterdir())==[path]
