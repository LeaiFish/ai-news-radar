from datetime import datetime, timedelta, timezone
import json

from scripts.wechat_sources import load_radar_rows, retained_account_rows, SCHEMA
from scripts.update_news import (
    load_wechat_bridge_items, apply_public_raw_meta, attach_select_tier,
    add_source_tier_fields, event_time, processing_window, parse_iso,
)
from scripts.ai_relevance import add_ai_relevance_fields

MONDAY = datetime(2026, 10, 26, 3, tzinfo=timezone.utc)
TITLE = '把生活需求搓成专属应用，来试试「我的应用」'
URL = 'https://mp.weixin.qq.com/s/K4UhZZiMGk5J6aHam3ORzA'


def row(url=URL, published='2026-10-23T02:43:00Z'):
    return {'url':url,'title':TITLE,'account_name':'千问APP','published':published,
            'verified_at':'2026-10-26T02:31:26Z','account_verified':True,'evidence_url':url}


def bridge(tmp_path, rows):
    p=tmp_path/'wechat.json'
    p.write_text(json.dumps({'schema':SCHEMA,'updated':'2026-10-26','accounts':{'qwen':rows},
                            'last_run':{'at':'2026-10-26T02:32:07Z','ok':False,
                                        'collection_state':'partial','errors':[{'error':'wemprss_list_api_-2041'}]}}))
    return p


def test_real_qwen_original_is_archived_as_first_party_with_its_friday_date(tmp_path):
    items,status=load_wechat_bridge_items(bridge(tmp_path,[row(),row()]),MONDAY)
    assert len(items)==1
    raw=items[0]
    record={'title':raw.title,'url':raw.url,'source':raw.source,'site_id':raw.site_id,
            'published_at':raw.published_at.isoformat(),'first_seen_at':MONDAY.isoformat()}
    apply_public_raw_meta(record,raw)
    attach_select_tier(record,site_id=raw.site_id,source=raw.source,meta=raw.meta)
    record=add_ai_relevance_fields(add_source_tier_fields(record))
    assert record['source_tier']=='official' and record['select_tier']=='T1'
    assert record['ai_is_related'] and record['editorial_focus']=='product'
    assert event_time(record)==datetime(2026,10,23,2,43,tzinfo=timezone.utc)
    assert event_time(record)<MONDAY-timedelta(hours=24)
    assert status['historical_item_count']==1 and status['recent_window_item_count']==0
    assert not status['ok']  # Valid history never erases partial collection health.


def test_monday_catches_friday_morning_saturday_and_sunday_despite_recent_job():
    p=processing_window(MONDAY,24,'2026-10-26T02:42:10Z',catch_up=True)
    assert p['start']=='2026-10-22T16:00:00Z'  # Friday00:00 in Shanghai.
    assert p['window_hours']>72
    for stamp in ['2026-10-23T00:05:00Z','2026-10-24T08:00:00Z','2026-10-25T08:00:00Z']:
        assert parse_iso(p['start'])<=parse_iso(stamp)<=MONDAY
    assert p['reasons']==['monday_friday_through_weekend']


def test_weekday_gap_recovery_is_bounded_and_not_a_read_acknowledgement():
    wednesday=datetime(2026,10,28,3,tzinfo=timezone.utc)
    p=processing_window(wednesday,24,'2026-10-22T03:00:00Z',catch_up=True)
    assert p['start']=='2026-10-22T03:00:00Z' and p['reasons']==['generation_gap']
    p=processing_window(wednesday,24,'2025-10-22T03:00:00Z',catch_up=True,archive_days=35)
    assert p['window_hours']==35*24 and p['truncated_to_archive_retention']
    assert processing_window(MONDAY,24,catch_up=False)['window_hours']==24
    assert processing_window(wednesday,24,'2099-01-01T00:00:00Z',catch_up=True)['window_hours']==24


def test_ingress_accepts_all_past_verified_dates_but_never_undated_or_future(tmp_path):
    rows,status=load_radar_rows(bridge(tmp_path,[row(),row(URL+'-old','2025-01-01T00:00:00Z'),
                                               row(URL+'-null',None),row(URL+'-future','2026-10-27T00:00:00Z')]),MONDAY)
    assert len(rows)==2 and status['historical_item_count']==2
    assert status['undated_count']==1 and status['future_date_count']==1
    assert {x['published'] for x in rows}=={'2026-10-23T02:43:00Z','2025-01-01T00:00:00Z'}


def test_more_than_twenty_weekend_posts_survive_bridge_retention():
    rows=[row(URL+str(i),f'2026-10-23T{(i%24):02d}:00:00Z') for i in range(30)]
    assert len(retained_account_rows(rows,MONDAY))==30


def test_same_original_prefers_official_company_over_media_copy():
    from scripts.update_news import choose_primary_story_item
    official=add_source_tier_fields({'site_id':'wechat_bridge','source':'公众号：千问APP','url':URL,
                                    'title':TITLE,'published_at':'2026-10-23T02:43:00Z',
                                    'account_name':'千问APP','company_id':'qwen','account_verified':True})
    media=add_source_tier_fields({'site_id':'curated_media','source':'IT之家','url':URL,
                                 'title':'千问Go推出我的应用功能','published_at':'2026-10-25T08:05:26Z'})
    assert choose_primary_story_item([media,official],MONDAY,83) is official
