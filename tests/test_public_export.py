import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('public_export',Path(__file__).parents[1]/'scripts/export-public-news.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_public_projection_drops_internal_metric_rows():
    assert not module.safe_row({'title':'x','metrics':{'doubao_dau':12345}})
    assert not module.safe_row({'title':'x','private':True})
    assert not module.safe_row({'title':'x','source':{'cookies':'sensitive'}})
    assert module.safe_row({'title':'Public announcement','summary':'Public statement','url':'https://example.com/news'})

def test_export_cannot_publish_local_or_authenticated_urls():
    for url in ['file:///Users/private.csv','http://127.0.0.1/x','http://10.1.2.3/x','http://localhost/x','http://server.internal/x','https://user:password@example.com/news','javascript:alert(1)']:
        assert not module.public_url(url)
    assert module.public_url('https://mp.weixin.qq.com/s/public-article')

def test_only_known_news_fields_leave_the_export():
    data=module.export()
    allowed={'id','title','originalTitle','summary','source','links','publishedAt','discoveredAt','timelineAt','category','tags','reason','score','selected','channel','x','story'}
    assert data['items']
    for row in data['items']:
        assert set(row)==allowed
        assert set(row['source'])=={'name'}
        assert set(row['links'])=={'original'}
        assert row['score'] is None

def test_public_reader_entry_references_only_existing_reader_assets():
    from bs4 import BeautifulSoup
    root=Path(__file__).parents[1]
    page=BeautifulSoup((root/'index.html').read_text(),'html.parser')
    assert page.title.get_text()=='竞争概览 · AI Perspective'
    urls=[tag.get('src') for tag in page.select('script[src]')]+[tag.get('href') for tag in page.select('link[rel="stylesheet"]')]
    assert urls
    for url in urls:
        assert url.startswith('./assets/')
        assert (root/url.split('?')[0].removeprefix('./')).is_file()


def test_curated_history_survives_latest_window_with_public_safety(monkeypatch, tmp_path):
    import json
    (tmp_path/'topics').mkdir()
    (tmp_path/'archive.json').write_text(json.dumps({'items':[
        {'id':'kept','title':'Verified product guide','url':'https://example.com/guide','published_at':'2026-11-06T03:00:00Z','curated':True},
        {'id':'noise','title':'Uncurated history','url':'https://example.com/noise','published_at':'2026-11-06T03:00:00Z'},
        {'id':'old','title':'Old guide','url':'https://example.com/old','published_at':'2026-09-01T00:00:00Z','curated':True},
        {'id':'unsafe','title':'Unsafe history','url':'https://example.com/unsafe','published_at':'2026-11-06T03:00:00Z','curated':True,'private':True},
        {'id':'local','title':'Local history','url':'http://localhost/guide','published_at':'2026-11-06T03:00:00Z','curated':True},
        {'id':'dup','title':'Duplicate guide','url':'https://example.com/guide','published_at':'2026-11-06T03:00:00Z','curated':True},
    ]}))
    payloads={'config/topics.json':{'topics':[],'groups':[]},
              'data/topics.json':{'generated_at':'2026-11-10T03:00:00Z'},
              'data/news-summary-cache.json':{},'data/title-zh-cache.json':{},
              'data/latest-24h-all.json':{'items_all':[]},
              'data/stories-merged.json':{'stories':[]},'data/daily-brief.json':{'items':[]},
              'data/archive.json':json.loads((tmp_path/'archive.json').read_text())}
    monkeypatch.setattr(module,'NEWS',tmp_path)
    monkeypatch.setattr(module,'load',lambda key:payloads[key])
    data=module.export()
    assert [row['id'] for row in data['items']]==['kept']
    assert data['items'][0]['publishedAt']=='2026-11-06T03:00:00Z'
    assert data['generatedAt']=='2026-11-10T03:00:00Z'
