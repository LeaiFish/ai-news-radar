from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from scripts import trend_history as history
from scripts.trend_reports import IDS, LATEST, ROOT, digest, iso, periods, validate_report, write_report, load, prepare, bind_input, archive_path
from test_trend_reports import report, updated


def evolution(raw):
    raw['evolution'] = {'companies': {}, 'overview': []}
    for slug, c in raw['companies'].items():
        refs=[e['id'] for e in raw['evidence'] if slug in e['company_ids']]
        raw['evolution']['companies'][slug] = {'type':'strengthened' if c['judgment'] else 'insufficient', 'reason':'补充网页交付证据' if refs else '证据不足，保留原判断', 'evidence_ids':refs, 'signals':[]}
    return raw


def test_old_replay_never_guesses_type_and_preserves_original_archive(tmp_path, report):
    updated(report)
    write_report(tmp_path, report)
    archive=tmp_path/archive_path(validate_report(report))
    before=archive.read_bytes()
    index,snapshots=history.build_history(tmp_path)
    row=snapshots[index['latest_report_id']]['companies']['doubao']
    assert row['type']=='unclassified'
    assert row['after']['content']==report['companies']['doubao']['judgment']
    assert row['after']['generated_at']==report['generated_at']
    assert archive.read_bytes()==before


def test_retrospective_label_is_dated_without_rewriting_issue(tmp_path, report):
    updated(report); write_report(tmp_path, report)
    id=digest(report)
    labels=evolution(deepcopy(report))['evolution']
    (tmp_path/'trends/annotations.json').write_text(json.dumps({'schema':'radar_trend_annotations_v1','annotated_at':report['generated_at'],'reports':{id:labels}}))
    index,snapshots=history.build_history(tmp_path)
    row=snapshots[id]['companies']['doubao']
    assert row['type']=='strengthened' and row['provenance']=='retrospective'
    assert row['classified_at']==report['generated_at']
    assert 'evolution' not in load(tmp_path/archive_path(validate_report(report)))


def test_insufficient_retains_before_after_and_original_judgment_date(tmp_path, report):
    updated(report);write_report(tmp_path, report)
    first=digest(report); next=deepcopy(report)
    source=datetime.fromisoformat(report['source_snapshot_at'].replace('Z','+00:00'))+timedelta(days=1)
    start,end=periods('daily',source)
    next.update(previous_report_id=first,period_start=iso(start),period_end=iso(end),source_snapshot_at=iso(source),generated_at=iso(source+timedelta(minutes=5)))
    next['evidence']=[]
    for c in next['companies'].values(): c.update(state='insufficient',judgment=None,changes=None,digest=None,events=[])
    evolution(next);write_report(tmp_path,next,now=source+timedelta(minutes=5))
    _,snapshots=history.build_history(tmp_path)
    row=snapshots[digest(next)]['companies']['doubao']
    assert row['type']=='insufficient' and row['before']==row['after']
    assert row['after']['generated_at']==report['generated_at']


@pytest.mark.parametrize('mutation', ['unknown_direction','cross_company','no_evidence','continued_rewrite','sensitive'])
def test_invalid_evolution_cannot_publish(report,mutation):
    evolution(updated(report)); c=report['evolution']['companies']['doubao']
    c['signals']=[{'direction_id':'shared-deliverables','type':'strengthened','summary':'网页可以分享','stage':'available','evidence_ids':['doubao-1']}]
    if mutation=='unknown_direction': c['signals'][0]['direction_id']='made-up'
    if mutation=='cross_company': report['evidence'][0]['company_ids']=['qwen']
    if mutation=='no_evidence': c['evidence_ids']=[]
    if mutation=='continued_rewrite': c['type']='continued'
    if mutation=='sensitive': c['reason']='Bearer private-value'
    with pytest.raises(ValueError): validate_report(report)


def test_broken_archive_parent_fails_closed(tmp_path, report):
    updated(report);checked=validate_report(report)
    checked['previous_report_id']='b'*64
    checked['report_id']=digest({k:v for k,v in checked.items() if k!='report_id'})
    path=tmp_path/archive_path(checked);path.parent.mkdir(parents=True);path.write_text(json.dumps(checked))
    with pytest.raises(ValueError,match='history_parent'): history.build_history(tmp_path)


def test_prepare_requires_explicit_future_labels_and_has_previous_weeks(tmp_path,report):
    updated(report);write_report(tmp_path,report)
    (tmp_path/'topics.json').write_text(json.dumps({'generated_at':report['source_snapshot_at']}))
    bundle=prepare(tmp_path,'daily')
    assert bundle['history_context']['recent_changes']
    assert bundle['evolution_contract']['types']['strengthened']
    new=deepcopy(report)
    for k in ['kind','period_start','period_end','source_snapshot_at','previous_report_id','input_id']: new[k]=bundle[k]
    with pytest.raises(ValueError,match='evolution_required'): bind_input(new,bundle)
    evolution(new);bind_input(new,bundle)


def test_unknown_annotations_or_changed_hash_are_rejected(tmp_path,report):
    write_report(tmp_path,report)
    (tmp_path/'trends/annotations.json').write_text(json.dumps({'schema':'radar_trend_annotations_v1','annotated_at':report['generated_at'],'reports':{'a'*64:evolution(report)['evolution']}}))
    with pytest.raises(ValueError,match='annotation_report'): history.build_history(tmp_path)


def test_online_latest_alone_is_not_history_deployment(monkeypatch):
    from scripts.publish_trend_report import verify
    class Response:
        def __init__(self,value): self.value=value
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self,*args): return json.dumps(self.value).encode()
    def open_(request,**kwargs):
        url=request.full_url if hasattr(request,'full_url') else request
        return Response({'latest_report_id':'b'*64} if 'history.json' in url else {'report_id':'a'*64})
    monkeypatch.setattr('urllib.request.urlopen',open_)
    assert not verify('a'*64,timeout=.01)


def test_homepage_initial_baseline_is_preserved(tmp_path,report):
    updated(report)
    report['evidence'][0]['company_ids']=['doubao','openai']
    report['overview']={'reason':'首次建立结构化首页','lead':'办公成果可交接','themes':[{'headline':'成果可分享','summary':'两家公司围绕已有成果继续工作','company_ids':['doubao','openai'],'evidence_ids':['doubao-1']}]}
    write_report(tmp_path,report)
    _,snapshots=history.build_history(tmp_path)
    before=snapshots[digest(report)]['overview']['before']
    assert before['baseline_text']==load(ROOT/'config/trend_baseline.json')['overview']['text']
    assert before['as_of']=='2026-10-19'


def test_context_keeps_strengthening_without_resetting_judgment(tmp_path,report):
    evolution(updated(report))
    report['companies']['doubao'].update(state='unchanged',judgment=None,changes=None)
    write_report(tmp_path,report)
    context=history.history_context(tmp_path)
    assert context['recent_changes']['doubao'][0]['type']=='strengthened'
    assert context['recent_changes']['doubao'][0]['evidence'][0]['url']=='https://www.doubao.com/work'
