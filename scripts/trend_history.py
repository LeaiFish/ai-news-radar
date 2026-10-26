#!/usr/bin/env python3
"""Evidence-bound history derived from immutable public reports, never keyword inference."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import re

try:
    from . import trend_reports as core
except ImportError:
    import trend_reports as core

INDEX = Path('trends/history.json')
ANNOTATIONS = Path('trends/annotations.json')
TYPES = {
    'established': '首次建立', 'continued': '延续', 'strengthened': '加强',
    'shifted': '转向', 'corrected': '纠偏', 'insufficient': '证据不足',
}
STAGES = {'announced': '已宣布', 'preview': '测试或邀测', 'available': '功能可用', 'observed': '使用案例', 'unknown': '阶段未核验'}
DIRECTIONS = core.load(core.ROOT/'config/trend_directions.json')['directions']


def _refs(value, evidence, company=None, allow_empty=False):
    core.require(isinstance(value, list) and len(value)<=15 and len(set(value))==len(value), 'invalid_evolution_refs')
    core.require((allow_empty or value) and set(value)<=evidence.keys(), 'missing_evolution_evidence')
    if company:
        core.require(all(company in evidence[k]['company_ids'] for k in value), 'cross_company_evolution')


def validate_evolution(raw, evolution=None):
    value = raw.get('evolution') if evolution is None else evolution
    core.keys(value, 'companies overview', 'invalid_evolution_fields')
    core.require(isinstance(value['companies'], dict) and set(value['companies'])==set(core.IDS), 'evolution_needs_eight_companies')
    evidence={e['id']:e for e in raw['evidence']}
    for slug,row in value['companies'].items():
        core.keys(row,'type reason evidence_ids signals','invalid_company_evolution')
        core.require(row['type'] in TYPES,'invalid_evolution_type')
        core.clean(row['reason'],600)
        insufficient = row['type']=='insufficient'
        company=raw['companies'][slug]
        core.require(insufficient == (company['state']=='insufficient'),'insufficient_evolution_mismatch')
        _refs(row['evidence_ids'],evidence,slug,allow_empty=insufficient)
        core.require(isinstance(row['signals'],list) and len(row['signals'])<=7,'invalid_direction_signals')
        if insufficient:
            core.require(not row['signals'],'insufficient_cannot_assert_signals')
        if row['type']=='continued':
            core.require(company['judgment'] is None,'continued_cannot_rewrite_judgment')
        if row['type'] in {'shifted','corrected','established'}:
            core.require(company['judgment'] is not None,'transition_needs_new_judgment')
        seen=set()
        for signal in row['signals']:
            core.keys(signal,'direction_id type summary stage evidence_ids','invalid_direction_signal')
            direction=signal['direction_id']
            core.require(direction in DIRECTIONS and direction not in seen,'invalid_direction_id')
            seen.add(direction)
            core.require(signal['type'] in TYPES and signal['type']!='insufficient','invalid_signal_type')
            core.require(signal['stage'] in STAGES,'invalid_signal_stage')
            core.clean(signal['summary'],600)
            _refs(signal['evidence_ids'],evidence,slug)
            core.require(set(signal['evidence_ids'])<=set(row['evidence_ids']),'signal_not_supported_by_evolution')
    themes=(raw.get('overview') or {}).get('themes',[])
    core.require(isinstance(value['overview'],list) and len(value['overview'])==len(themes),'overview_evolution_mismatch')
    seen=set()
    for row,theme in zip(value['overview'],themes):
        core.keys(row,'direction_id type reason evidence_ids','invalid_overview_evolution')
        core.require(row['direction_id'] in DIRECTIONS and row['direction_id'] not in seen,'invalid_direction_id')
        seen.add(row['direction_id'])
        core.require(row['type'] in TYPES and row['type']!='insufficient','invalid_overview_evolution_type')
        core.clean(row['reason'],600)
        _refs(row['evidence_ids'],evidence)
        core.require(set(row['evidence_ids'])<=set(theme['evidence_ids']),'overview_evolution_unsupported')
    return value


def _ordered(data_dir,extra_report=None):
    reports={}
    for kind,pattern in [('daily','????-??-??.json'),('weekly','????-W??.json')]:
        for path in (data_dir/'trends'/kind).glob(pattern):
            stored=core.load(path)
            raw={k:v for k,v in stored.items() if k!='report_id'}
            checked=core.validate_report(raw,now=core.stamp(raw['generated_at']))
            core.require(checked==stored,'invalid_history_archive_hash')
            core.require(core.archive_path(checked)==path.relative_to(data_dir),'history_archive_path_mismatch')
            reports[checked['report_id']]=checked
    if extra_report:
        reports[extra_report['report_id']]=extra_report
    result=[];parent=None
    while reports:
        children=[r for r in reports.values() if r['previous_report_id']==parent]
        core.require(len(children)==1,'history_parent_chain_invalid')
        child=children[0]
        if result:
            core.require(core.stamp(child['generated_at'])>=core.stamp(result[-1]['generated_at']),'history_time_regression')
        result.append(child);parent=child['report_id'];del reports[parent]
    return result


def _baseline(data_dir):
    path=data_dir.parent/'config/trend_baseline.json'
    value=core.load(path if path.exists() else core.ROOT/'config/trend_baseline.json')
    core.clean(json.dumps(value,ensure_ascii=False),500_000)
    for row in value['companies'].values():
        for url in row['judgment']['sources']: core.public_url(url)
    return value


def build_history(data_dir,extra_report=None):
    data_dir=Path(data_dir)
    reports=_ordered(data_dir,extra_report)
    annotations=core.load(data_dir/ANNOTATIONS,{'schema':'radar_trend_annotations_v1','annotated_at':None,'reports':{}})
    core.keys(annotations,'schema annotated_at reports','invalid_annotations')
    core.require(annotations['schema']=='radar_trend_annotations_v1' and isinstance(annotations['reports'],dict),'invalid_annotations')
    core.clean(json.dumps(annotations,ensure_ascii=False),2_000_000)
    if annotations['annotated_at'] is not None: core.stamp(annotations['annotated_at'])
    core.require(set(annotations['reports'])<={r['report_id'] for r in reports},'annotation_report_missing')
    baseline=_baseline(data_dir)
    states={slug:{'content':{'headline':'初始月度判断','summary':baseline['companies'][slug]['judgment']['text'],'evidence_ids':[]},
                  'generated_at':None,'as_of':baseline['companies'][slug]['as_of'],
                  'sources':baseline['companies'][slug]['judgment']['sources'],'evidence':[], 'review_state':baseline['companies'][slug]['review_state']} for slug in core.IDS}
    overview={'baseline_text':baseline['overview']['text'],'as_of':baseline['overview']['as_of'],'lead':'初始月度首页判断','themes':[], 'generated_at':None,'evidence':[]};snapshots={};index=[];latest_signals={k:{} for k in DIRECTIONS}
    for report in reports:
        rid=report['report_id']
        labels=report.get('evolution')
        provenance='report' if labels else 'unclassified'
        classified=report['generated_at'] if labels else None
        if not labels and rid in annotations['reports']:
            labels=validate_evolution(report,annotations['reports'][rid]);provenance='retrospective';classified=annotations['annotated_at']
            core.require(classified and core.stamp(classified)>=core.stamp(report['generated_at']),'invalid_annotation_time')
        evidence={e['id']:e for e in report['evidence']}
        snapshot={'schema':'radar_trend_history_snapshot_v1','report_id':rid,'previous_report_id':report['previous_report_id'],
                  'kind':report['kind'],'generated_at':report['generated_at'],'period_start':report['period_start'],'period_end':report['period_end'],
                  'companies':{},'overview':None}
        meta={k:snapshot[k] for k in ['report_id','kind','generated_at','period_start','period_end']}
        meta.update(path=core.archive_path(report).as_posix(),companies={},overview=[])
        for slug,row in report['companies'].items():
            before=deepcopy(states[slug]);card=row['judgment']
            if card:
                refs=[evidence[k] for k in card['evidence_ids']]
                states[slug]={'content':card,'generated_at':report['generated_at'],'as_of':None,'sources':[], 'evidence':refs,'review_state':'assistant_draft'}
            label=(labels or {}).get('companies',{}).get(slug)
            type_=label['type'] if label else 'unclassified'
            # A first structured judgment may replace a dated baseline, but an existing one cannot be "first" again.
            if type_=='established': core.require(before['generated_at'] is None,'judgment_already_established')
            if type_ in {'shifted','corrected'}: core.require(before['content']!=states[slug]['content'],'transition_without_changed_judgment')
            signals=deepcopy(label['signals']) if label else []
            refs=set(label['evidence_ids']) if label else set()
            for signal in signals: refs.update(signal['evidence_ids'])
            snapshot['companies'][slug]={'before':before,'after':deepcopy(states[slug]),'type':type_,
                'reason':label['reason'] if label else '历史未标注判断变化类型；不从文字或新闻条数推断。',
                'signals':signals,'evidence':[evidence[k] for k in sorted(refs)],'provenance':provenance,'classified_at':classified,
                'state':row['state'],'checked_reason':row['reason']}
            meta['companies'][slug]={'type':type_,'changed':bool(card),'direction_ids':[s['direction_id'] for s in signals]}
            for signal in signals: latest_signals[signal['direction_id']][slug]=rid
        if report['overview']:
            before=deepcopy(overview)
            themes=[]
            for i,theme in enumerate(report['overview']['themes']):
                label=labels['overview'][i] if labels else None
                themes.append({'content':theme,'direction_id':label['direction_id'] if label else None,'type':label['type'] if label else 'unclassified',
                               'reason':label['reason'] if label else '历史未标注方向；不按标题猜测。'})
            refs={k for t in report['overview']['themes'] for k in t['evidence_ids']}
            overview={'lead':report['overview']['lead'],'themes':themes,'generated_at':report['generated_at'],'evidence':[evidence[k] for k in sorted(refs)]}
            snapshot['overview']={'before':before,'after':deepcopy(overview),'provenance':provenance,'classified_at':classified}
            meta['overview']=[{'direction_id':t['direction_id'],'type':t['type']} for t in themes]
        snapshots[rid]=snapshot;index.append(meta)
    manifest={'schema':'radar_trend_history_v1','latest_report_id':reports[-1]['report_id'] if reports else None,
              'directions':DIRECTIONS,'types':{**TYPES,'unclassified':'未标注'},'stages':STAGES,'baseline_as_of':baseline['overview']['as_of'],
              'reports':index,'latest_signals':latest_signals}
    core.clean(json.dumps(manifest,ensure_ascii=False),10_000_000)
    for snapshot in snapshots.values(): core.clean(json.dumps(snapshot,ensure_ascii=False),2_000_000)
    return manifest,snapshots


def write_history(data_dir,payload):
    manifest,snapshots=payload
    folder=Path(data_dir)/'trends/history';folder.mkdir(parents=True,exist_ok=True)
    for rid,value in snapshots.items():
        path=folder/f'{rid}.json'
        # Retrospective sidecar annotations are allowed to revise a derived view, never the original issue.
        temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temporary.replace(path)
    path=Path(data_dir)/INDEX
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');temporary.replace(path)


def history_context(data_dir):
    manifest,snapshots=build_history(data_dir)
    def compact(snapshot):
        return {**{k:snapshot[k] for k in ['report_id','kind','generated_at','period_start','period_end']},
                'companies':{k:{'type':v['type'],'reason':v['reason'],'judgment':v['after']['content'],
                               'judgment_updated_at':v['after']['generated_at'],'signals':v['signals']} for k,v in snapshot['companies'].items()},
                'overview':snapshot['overview']}
    weekly=[s for s in snapshots.values() if s['kind']=='weekly'][-8:]
    changes={slug:[] for slug in core.IDS}
    for meta in reversed(manifest['reports']):
        for slug in core.IDS:
            if (meta['companies'][slug]['changed'] or meta['companies'][slug]['type'] in {'strengthened','shifted','corrected'}) and len(changes[slug])<4:
                row=snapshots[meta['report_id']]['companies'][slug]
                changes[slug].append({'report_id':meta['report_id'],'generated_at':meta['generated_at'],'type':row['type'],
                                     'reason':row['reason'],'before':row['before']['content'],'after':row['after']['content'],'signals':row['signals']})
    return {'previous_weeks':[compact(s) for s in weekly], 'recent_changes':{k:v for k,v in changes.items() if v},
            'warning':'历史只作比较基线，不是本轮已核验事实；缺期不等于无变化。'}


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data-dir',type=Path,default=core.ROOT/'data');p.add_argument('--check',action='store_true')
    args=p.parse_args();payload=build_history(args.data_dir)
    if args.check:
        core.require(core.load(args.data_dir/INDEX)==payload[0],'history_index_out_of_date')
        for rid,snapshot in payload[1].items(): core.require(core.load(args.data_dir/'trends/history'/f'{rid}.json')==snapshot,'history_snapshot_out_of_date')
    else: write_history(args.data_dir,payload)
    print(json.dumps({'status':'validated' if args.check else 'written','reports':len(payload[1]),'latest_report_id':payload[0]['latest_report_id']}))


if __name__=='__main__':
    try: main()
    except (ValueError,KeyError,TypeError,OSError): raise SystemExit('trend_history_validation_failed; original archives retained') from None
