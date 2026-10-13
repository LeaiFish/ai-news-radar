#!/usr/bin/env python3
"""Backfill all domestic-topic abstracts using the existing free translation service."""
import argparse,hashlib,json,re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
try:
 from scripts.update_news import create_session,translate_to_zh_cn
 from scripts.build_topics import DOMESTIC_TOPIC_IDS,write_topics_payload
except ModuleNotFoundError:
 from update_news import create_session,translate_to_zh_cn
 from build_topics import DOMESTIC_TOPIC_IDS,write_topics_payload

def chinese(text):
 return len(re.findall(r'[\u4e00-\u9fff]',text or '')) >= max(4,len(re.findall(r'[A-Za-z]',text or ''))*.15)

def backfill(data_dir,max_new=400):
 cache_path=data_dir/'news-summary-cache.json'
 cache=json.loads(cache_path.read_text()) if cache_path.exists() else {}
 rows={}
 for slug in sorted(DOMESTIC_TOPIC_IDS):
  path=data_dir/'topics'/f'{slug}.json'
  if path.exists():
   for row in json.loads(path.read_text()).get('items',[]):rows.setdefault(row.get('url'),row)
 pending=[]
 for url,row in rows.items():
  saved=cache.get(url,{})
  original=saved.get('summary_original') or row.get('summary') or ''
  if not original or chinese(original) or chinese(saved.get('summary_zh','')):continue
  pending.append((url,original))
 def translate(entry):
  url,original=entry
  with create_session() as session:result=translate_to_zh_cn(session,original)
  return url,original,result if chinese(result) else None
 completed=0
 with ThreadPoolExecutor(max_workers=4) as pool:
  for url,original,result in pool.map(translate,pending[:max_new]):
   if result:
    cache[url]={**cache.get(url,{}),'summary_original':original,'summary_zh':result,'summary_translation_hash':hashlib.sha256(original.encode()).hexdigest()};completed+=1
 cache_path.write_text(json.dumps(cache,ensure_ascii=False,indent=2)+'\n')
 write_topics_payload(data_dir)
 print(json.dumps({'pending':len(pending),'translated':completed,'remaining':len(pending)-completed}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,default=Path('data'));p.add_argument('--max-new',type=int,default=400);a=p.parse_args();backfill(a.data_dir,max(0,a.max_new))
