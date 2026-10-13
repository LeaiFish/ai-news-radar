import json,subprocess,importlib.util
from pathlib import Path
ROOT=Path(__file__).parents[1]

def test_research_requires_multiple_reports_and_excludes_old_duplicates():
    script='''require('./assets/research-analysis.js');
const end=Date.parse('2026-10-13T00:00:00Z');
const rows=[
 {title:'Qwen Agent 上线',published_at:'2026-10-12T00:00:00Z',source:'Official'},
 {title:'Qwen Agent 上线',published_at:'2026-10-12T00:00:00Z',source:'Relay'},
 {title:'智能体产品公测',published_at:'2026-10-10T00:00:00Z',source:'News'},
 {title:'Agent release',published_at:'2026-08-10T00:00:00Z',source:'Old'}];
console.log(JSON.stringify(globalThis.radarAnalyzeResearch(rows,end)));
console.log(JSON.stringify(globalThis.radarAnalyzeResearch(rows.slice(0,1),end)));'''
    output=subprocess.check_output(['node','-e',script],cwd=ROOT,text=True).splitlines()
    result=json.loads(output[0]);assert result['total']==2
    assert result['themes'][0]['id']=='agent' and result['themes'][0]['count']==2
    assert len(result['themes'][0]['evidence'])==2
    assert json.loads(output[1])['themes']==[]

def test_free_domestic_summary_translation_and_retry(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('domestic_translation',ROOT/'scripts/translate-domestic-summaries.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    (tmp_path/'topics').mkdir()
    rows=[{'url':'https://example.com/translated','summary':'Qwen is launching a personal agent in its app.'},{'url':'https://example.com/retry','summary':'A new model has been released by the company.'}]
    (tmp_path/'topics/qwen.json').write_text(json.dumps({'items':rows}))
    monkeypatch.setattr(module,'write_topics_payload',lambda _:None)
    monkeypatch.setattr(module,'translate_to_zh_cn',lambda _,text:'千问正在应用中推出个人智能体。' if text.startswith('Qwen') else None)
    module.backfill(tmp_path)
    cache=json.loads((tmp_path/'news-summary-cache.json').read_text())
    assert cache[rows[0]['url']]['summary_zh']=='千问正在应用中推出个人智能体。'
    assert rows[1]['url'] not in cache
    assert module.chinese('千问正在应用中推出个人智能体。')
    assert not module.chinese('Qwen APP On October 13 released a message about 千问')
