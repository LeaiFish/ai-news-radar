"""Nov 9 recovery: actionable failures, original dates and bounded product intake."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import json
import pytest
from scripts.ai_relevance import score_ai_relevance
from scripts.editorial_focus import editorial_focus
from scripts.ensure_trend_snapshot import ensure
from scripts.focus_sources import matched_sources, load_sources
from scripts.update_news import fetch_aihot_focus, parse_aihot_api_items, CURATED_AI_MEDIA_FEEDS, parse_curated_ai_media_feed_items

NOW=datetime(2026,11,9,5,tzinfo=timezone.utc)
DUET='https://x.com/davidsuttonca/status/2118785613436698719'
QUOTE='https://x.com/adocomplete/status/2118806752611434984'
DOUBAO='https://www.ithome.com/1/023/414.htm'

def entry(url,title,date,score=45):
 return dict(id=url,title=title,links={'original':url},source={'name':'Copied official label'},
             publishedAt=date,score=score,selected=False,summary='Today unlimited new launch')

def test_dispatch_denial_has_actionable_safe_code_without_upstream_output():
 calls=[]
 def run(args,**kwargs):
  calls.append(args);stdout=''
  if args[:3]==['git','remote','get-url']:stdout='git@github.com:LeaiFish/ai-news-radar.git'
  elif args[:2]==['git','show']:stdout=json.dumps({'generated_at':'2026-11-06T22:07:14Z'})
  elif args[:3]==['gh','run','list']:stdout='[]'
  if args[:3]==['gh','workflow','run']:
   return SimpleNamespace(returncode=1,stdout='',stderr='HTTP 422: Actions has been disabled for this repository. private-local-detail')
  return SimpleNamespace(returncode=0,stdout=stdout,stderr='')
 with pytest.raises(RuntimeError,match='^snapshot_actions_disabled_contact_github_support$'):
  ensure(Path('/tmp/repair-test'),run=run,now=lambda:NOW,sleep=lambda _:pytest.fail('must stop on denied dispatch'))
 assert len([a for a in calls if a[:3]==['gh','workflow','run']])==1


def test_other_failure_names_stage_without_raw_diagnostics():
 def run(args,**kwargs):
  if args[:2]==['git','fetch']:
   return SimpleNamespace(returncode=1,stdout='',stderr='sensitive upstream detail')
  return SimpleNamespace(returncode=0,stdout='git@github.com:LeaiFish/ai-news-radar.git' if args[:3]==['git','remote','get-url'] else '',stderr='')
 with pytest.raises(RuntimeError,match='^snapshot_operation_failed:fetch$'):
  ensure(Path('/tmp/repair-test'),run=run,now=lambda:NOW)

@pytest.mark.parametrize('title',[
 '豆包工作个人版取消 5 小时额度限制',
 'Claude Duet 新增 Claude Code 会话支持，可用手机远程管理',
 'Claude 新增会话管理功能',
])
def test_product_usage_and_limits_are_kept(title):
 row={'title':title,'url':DOUBAO,'site_id':'curated_media','source':'IT之家'}
 assert score_ai_relevance(row)['is_ai_related']
 assert editorial_focus(row)=='product'

@pytest.mark.parametrize('title',[
 '豆包充值会员送优惠券，关注领红包',
 '个人银行取消五小时转账限制',
 'Claude 云端会话推理性能评测',
])
def test_limits_do_not_whitelist_promotions_or_technical_posts(title):
 assert editorial_focus({'title':title,'url':'https://example.org/post'})!='product'


def test_duet_quote_and_primary_are_one_personal_original_with_original_date():
 a=entry(QUOTE,'Claude Code in your Claude Duet!','2026-11-06T20:44:30Z')
 b=entry(DUET,'Claude Duet: now with Claude Code sessions','2026-11-06T19:20:30Z')
 session=Mock();session.get.return_value.json.return_value={'schemaVersion':1,'items':[a,b], 'page':{'hasMore':False,'nextCursor':None}}
 [raw]=fetch_aihot_focus(session,NOW)
 assert raw.url==DUET and raw.published_at.isoformat()=='2026-11-06T19:20:30+00:00'
 assert '个人账号' in raw.source and '官方' not in raw.source
 assert '手机' in raw.meta['summary'] and '首次上线' not in raw.title
 assert 'Today unlimited' not in raw.meta['summary']
 assert len(load_sources())==48
 assert matched_sources({'url':QUOTE}) and matched_sources({'url':DUET})
 assert not matched_sources({'url':'https://x.com/davidsuttonca/status/99'})
 assert parse_aihot_api_items({'items':[a]},NOW)==[] # selected gate unchanged


def test_doubao_rss_and_aihot_keep_same_original_day_and_weekly_limit():
 rss=('<rss><channel><item><title>豆包工作个人版取消 5 小时额度限制</title>'
      '<link>'+DOUBAO+'</link><pubDate>Fri, 06 Nov 2026 08:57:38 GMT</pubDate>'
      '<description>周额度及其他使用规则仍以对应套餐为准。</description></item></channel></rss>').encode()
 feed=next(x for x in CURATED_AI_MEDIA_FEEDS if 'ithome.com' in x['xml_url'])
 [raw]=parse_curated_ai_media_feed_items(rss,feed,NOW)
 assert raw.url==DOUBAO and raw.published_at.isoformat()=='2026-11-06T08:57:38+00:00'
 [indirect]=parse_aihot_api_items({'items':[entry(DOUBAO,'豆包工作取消5小时限制','2026-11-09T00:00:00Z',55)]},NOW,min_score=0)
 assert indirect.published_at==raw.published_at
 assert '周额度及其他规则仍以对应套餐为准' in indirect.meta['summary'] and '不代表无限额度' in indirect.meta['summary']
 assert indirect.url==raw.url
