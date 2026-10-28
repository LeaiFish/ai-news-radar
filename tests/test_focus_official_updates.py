import json
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from bs4 import BeautifulSoup

from scripts.focus_official_updates import SOURCES, card_rows, structured_rows, fetch_source
from scripts.official_app_updates import update_fragment
from scripts.update_news import fetch_aihot_focus, normalize_url
from urllib.parse import urlparse

NOW = datetime(2026, 10, 28, 8, tzinfo=timezone.utc)
SPEC = next(s for s in SOURCES if s['id'] == 'official_focus_xai')


def test_cards_never_borrow_neighbour_date_or_follow_offsite_links():
    html = '''<div><a href="/news/undated"><h2>Grok undated</h2></a>
    <a href="/news/sales"><h2>Grok Shared Bots</h2><time datetime="2026-10-27">Oct 27, 2026</time></a>
    <a href="https://x.ai.attacker.test/news/fake"><h2>Grok fake</h2><time datetime="2026-10-27"></time></a></div>'''
    rows = card_rows(BeautifulSoup(html, 'html.parser'), SPEC)
    assert [(r['title'], r['url']) for r in rows] == [('Grok Shared Bots', 'https://x.ai/news/sales')]


def test_structured_publication_date_is_preserved_and_modified_date_is_not_publication():
    spec = next(s for s in SOURCES if s['id'] == 'official_focus_luma')
    data = {'itemListElement':[
        {'item':{'headline':'A video workflow', 'url':'https://lumalabs.ai/news/workflow', 'datePublished':'2026-10-27T07:31:19.662Z'}},
        {'item':{'headline':'Old page changed', 'url':'https://lumalabs.ai/news/modified', 'dateModified':'2026-10-28T00:00:00Z'}},
    ]}
    html = '<script type="application/ld+json">' + json.dumps(data) + '</script>'
    rows = structured_rows(BeautifulSoup(html, 'html.parser'), spec)
    assert len(rows) == 1
    assert rows[0]['published_at'].isoformat() == '2026-10-27T07:31:19.662000+00:00'


def test_next_data_is_parsed_without_executing_javascript():
    spec = next(s for s in SOURCES if s['id'] == 'official_focus_suno')
    data = ['$', {'posts':[{'title':'New music workflow','slug':{'current':'workflow'},'publishedAt':'2026-10-27T12:00:00Z'}]}]
    script = 'self.__next_f.push(' + json.dumps([1, '5:' + json.dumps(data) + '\n']) + ')'
    rows = structured_rows(BeautifulSoup('<script>'+script+'</script>', 'html.parser'), spec)
    assert rows[0]['url'] == 'https://suno.com/blog/workflow'


def test_bad_structure_reports_failure_not_green_empty_source():
    session = Mock()
    session.get.return_value.url = SPEC['url']
    session.get.return_value.content = b'<html>Challenge</html>'
    session.get.return_value.text = '<html>Challenge</html>'
    with pytest.raises(ValueError, match='No dated'):
        fetch_source(session, SPEC, NOW)


def test_dated_changelog_fragments_survive_url_normalization():
    url = 'https://x.ai/changelog/bot#v0.77.0'
    assert update_fragment(urlparse(url)) == 'v0.77.0'
    assert normalize_url(url) == url
    assert normalize_url('https://x.ai/changelog/bot#untrusted') == 'https://x.ai/changelog/bot'


def test_all_mode_recovers_focused_unselected_items_but_not_same_named_impostors_or_wechat():
    entries = [
        {'id':'real', 'title':'Cursor design mode adds visual annotations', 'score':20, 'selected':False,
         'source':{'name':'X: Cursor'},'publishedAt':'2026-10-27T19:11:57Z','links':{'original':'https://x.com/cursor_ai/status/123'}},
        {'id':'personal', 'title':'Grok Bot workflow: manage your mentions with daily digests', 'score':20, 'selected':False,
         'source':{'name':'X: Lauren Tan'},'publishedAt':'2026-10-27T22:16:12Z','links':{'original':'https://x.com/poteto/status/124'}},
        {'id':'fake', 'title':'Cursor adds a feature', 'score':90, 'source':{'name':'Cursor'},
         'publishedAt':'2026-10-27T12:00:00Z','links':{'original':'https://x.com/cursor_ai_fake/status/1'}},
        {'id':'wechat', 'title':'千问新增功能', 'score':90, 'source':{'name':'千问APP'},
         'publishedAt':'2026-10-27T12:00:00Z','links':{'original':'https://mp.weixin.qq.com/s/not-verified'}},
        {'id':'noise', 'title':'xAI Lauren bought a new domain', 'score':90, 'source':{'name':'X: Lauren Tan'},
         'publishedAt':'2026-10-27T12:00:00Z','links':{'original':'https://x.com/poteto/status/125'}},
    ]
    session = Mock()
    session.get.return_value.json.return_value = {'schemaVersion':1,'items':entries,'page':{'hasMore':False}}
    rows = fetch_aihot_focus(session, NOW)
    assert {r.url for r in rows} == {'https://x.com/cursor_ai/status/123','https://x.com/poteto/status/124'}
    assert all(r.site_id == 'aihot' for r in rows)
    assert all(not r.meta.get('select_tier') for r in rows)


def test_personal_supplement_is_not_mislabeled_official():
    from scripts.focus_sources import load_sources, load_supplemental_sources
    assert len(load_sources()) == 48
    lauren = next(r for r in load_supplemental_sources() if r['source_url'].endswith('/poteto'))
    assert lauren['identity_kind'] == 'team_member_personal_account'
    from scripts.source_tiers import resolve_select_tier
    assert resolve_select_tier(site_id='aihot', source='X: Lauren Tan') == 'T2'
