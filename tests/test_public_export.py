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
    assert page.title.get_text()=='AI Perspective'
    urls=[tag.get('src') for tag in page.select('script[src]')]+[tag.get('href') for tag in page.select('link[rel="stylesheet"]')]
    assert urls
    for url in urls:
        assert url.startswith('/ai-news-radar/assets/public-reader/')
        assert (root/url.removeprefix('/ai-news-radar/')).is_file()
