#!/usr/bin/env python3
"""Hourly free pipeline, isolated from internal business files and provider credentials."""
import os, shutil, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
news=Path(os.environ.get('RADAR_NEWS_DATA_DIR','/data/radar-news'));news.mkdir(parents=True,exist_ok=True)
public=Path(os.environ.get('RADAR_PUBLIC_SITE_DIR','/data/public-site'));public.mkdir(parents=True,exist_ok=True)
env={**os.environ,'RADAR_FREE_ONLY':'1','MODEL_CALLS_ENABLED':'false','COLLECT_ENABLED':'false',
 'SOCIALDATA_API_ENABLED':'0','TIKHUB_ENABLED':'0','X_API_ENABLED':'0','EMAIL_DIGEST_ENABLED':'0','EMAIL_DIGEST_PUBLISH':'0',
 'TITLE_ENHANCE_MAX_PER_RUN':'0','REASON_ENHANCE_MAX_PER_RUN':'0','RADAR_NEWS_DATA_DIR':str(news),
 'RADAR_PUBLIC_INPUT':str(public/'public-news.json')}
def run(*args): subprocess.run(args,cwd=ROOT,env=env,check=True,timeout=1500)
run('python3','scripts/update_news.py','--output-dir',str(news),'--window-hours','24','--archive-days','35','--translate-max-new','20')
run('python3','scripts/free_news_content.py','--data-dir',str(news),'--max-fetch','40','--max-translate','20')
run('python3','scripts/build_topics.py','--data-dir',str(news),'--translate-max-new','20')
run('python3','scripts/translate-domestic-summaries.py','--data-dir',str(news),'--max-new','400')
run('python3','scripts/export-public-news.py','--output',str(public/'public-news.json'))
run('node','scripts/import-public-news.ts')
# The exporter reads only marked public imports and respects withdrawals.
env['RADAR_PUBLIC_OUTPUT']=str(public/'public-news.json')
run('node','scripts/export-public-db.ts')
built=ROOT/'.public-export/site'
if built.exists():
 shutil.copyfile(built/'index.html',public/'index.html')
 shutil.copytree(built/'assets',public/'assets',dirs_exist_ok=True)
 shutil.copytree(built/'config',public/'config',dirs_exist_ok=True)
 (public/'.nojekyll').write_text('')
print('Free public-news cycle complete')
