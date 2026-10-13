#!/usr/bin/env python3
"""Export an explicit public-news projection. Never walk directories or export a database."""
import argparse, hashlib, ipaddress, json, re, os, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit
ROOT = Path(__file__).resolve().parent.parent
NEWS = Path(os.environ.get('RADAR_NEWS_DATA_DIR', str(ROOT/'data')))
FORBIDDEN = {'dau','mau','wau','internal','private','credentials','password','cookies','token','secret'}

def safe_row(row):
    if not isinstance(row, dict): return False
    def check(value):
        if isinstance(value, dict):
            return all(not (set(re.split(r'[^a-z]+', str(k).lower())) & FORBIDDEN) and check(v) for k,v in value.items())
        if isinstance(value,list): return all(check(v) for v in value)
        return True
    return check(row)

def public_url(value):
    try:
        u=urlsplit(value)
        if u.scheme not in ('https','http') or not u.hostname or u.username or u.password: return False
        if u.hostname.lower() in ('localhost','localhost.localdomain') or '.' not in u.hostname: return False
        try: return ipaddress.ip_address(u.hostname).is_global
        except ValueError: return not u.hostname.endswith(('.local','.internal','.localhost'))
    except (ValueError,TypeError): return False

def text(value, limit): return value[:limit] if isinstance(value,str) else ''
def load(relative):
    path = NEWS/relative[5:] if relative.startswith('data/') else ROOT/relative
    if not path.exists() and relative in ('data/news-summary-cache.json','data/title-zh-cache.json'): return {}
    return json.loads(path.read_text())
def export():
    config=load('config/topics.json'); hub=load('data/topics.json')
    summaries=load('data/news-summary-cache.json'); translations=load('data/title-zh-cache.json')
    generated=hub['generated_at']; cutoff=datetime.fromisoformat(generated.replace('Z','+00:00'))-timedelta(days=30)
    rows={}; memberships={}; topics=[]
    for topic in config['topics']:
        slug=topic['id']
        if not re.fullmatch(r'[a-zA-Z0-9_-]+',slug): raise ValueError('Invalid topic id')
        path=NEWS/'topics'/f'{slug}.json'
        if not path.exists(): continue
        d=json.loads(path.read_text()); memberships[slug]=[]
        topics.append({k:topic.get(k) for k in ('id','name','description','group','region')})
        for row in d.get('items',[]):
            if safe_row(row): rows.setdefault(row.get('url'),row); memberships[slug].append(row.get('url'))
    recent=load('data/latest-24h-all.json')
    for row in recent.get('items_all',[]):
        if safe_row(row): rows.setdefault(row.get('url'),row)
    merged=load('data/stories-merged.json').get('stories',[])
    for story in merged:
        for row in story.get('items',[]):
            if safe_row(row): rows.setdefault(row.get('url'),row)
    items=[]; ids={}
    for url,row in rows.items():
        if not public_url(url): continue
        at=row.get('published_at') or row.get('first_seen_at')
        try:
            date=datetime.fromisoformat(at.replace('Z','+00:00'))
            if date.tzinfo is None or date<cutoff: continue
        except (ValueError,TypeError,AttributeError): continue
        original=text(row.get('title_original') or row.get('title_en') or row.get('title'),1200)
        cached=translations.get(original)
        if isinstance(cached,dict): cached=cached.get('title_zh') or cached.get('zh')
        title=text(row.get('title_zh') or cached or row.get('title'),1200)
        if not title: continue
        summary=summaries.get(url,{})
        abstract=text(summary.get('summary_zh') or row.get('summary_zh') or summary.get('summary_original') or row.get('summary'),1800)
        if abstract.startswith('来源未提供摘要'): abstract=''
        identity=row.get('id')
        if not isinstance(identity,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',identity): identity=hashlib.sha256(url.encode()).hexdigest()[:40]
        ids[url]=identity
        items.append({'id':identity,'title':title,'originalTitle':original if original!=title else None,'summary':abstract or None,
          'source':{'name':text((row.get('source') if row.get('source_name') in ('AI HOT','AIHOT') else row.get('source_name')) or row.get('source') or '未知来源',200)},'links':{'original':url},
          'publishedAt':at,'discoveredAt':at,'timelineAt':at,'category':None,'tags':[],'reason':None,'score':None,
          'selected':row.get('curated') is True,'channel':'news','x':None,'story':None})
    items.sort(key=lambda row:row['timelineAt'],reverse=True)
    for topic in topics: topic['itemIds']=[ids[u] for u in dict.fromkeys(memberships[topic['id']]) if u in ids]
    stories=[]
    for story in merged:
        members=[ids[row.get('url')] for row in story.get('items',[]) if row.get('url') in ids]
        if not members or not safe_row(story): continue
        primary=next((item for item in items if item['id']==members[0]),None)
        if primary:
            stories.append({'publicId':str(uuid.uuid5(uuid.NAMESPACE_URL,'radar:'+str(story.get('story_id')))),
             'title':primary['title'],'itemIds':list(dict.fromkeys(members)),
             'selected':story.get('tier')=='selected'})
    brief=load('data/daily-brief.json').get('items',[])
    dailyIds=[ids[row.get('primary_url') or row.get('url')] for row in brief if (row.get('primary_url') or row.get('url')) in ids]
    return {'version':1,'generatedAt':generated,'windowDays':30,'groups':config['groups'],'topics':topics,'items':items,'stories':stories,'dailyIds':list(dict.fromkeys(dailyIds))}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='.public-export/public-news.json');args=parser.parse_args()
    result=export();out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')))
    print(f'Exported {len(result["items"])} public news items, {len(result["topics"])} topics to {out}')
