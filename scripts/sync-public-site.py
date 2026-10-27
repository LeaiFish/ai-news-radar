#!/usr/bin/env python3
"""Copy ONLY the public Docker outlet to a separate checkout; optional publication."""
import argparse,json,os,re,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');args=p.parse_args()
checkout=ROOT/'.local/pages-checkout'
ASSETS=['logo.svg','styles.css','sidebar.css','topics.css','perspective.css','perspective.js','public-projection.js','aihot-skin.css','research-analysis.js','trend-reports.js','trend-history.js']
def copy_reader(stage,out):
 (out/'assets').mkdir(parents=True,exist_ok=True)
 (out/'config').mkdir(parents=True,exist_ok=True)
 for name in ASSETS:shutil.copyfile(stage/'assets'/name,out/'assets'/name)
 shutil.copyfile(stage/'config/topics.json',out/'config/topics.json')
 if (stage/'data/case-leads.json').exists():
  (out/'data').mkdir(exist_ok=True)
  shutil.copyfile(stage/'data/case-leads.json',out/'data/case-leads.json')
def run(*cmd,cwd=ROOT):return subprocess.run(cmd,cwd=cwd,check=True,text=True,capture_output=True).stdout
with tempfile.TemporaryDirectory(prefix='radar-public-') as folder:
 stage=Path(folder)/'site'
 run('docker','compose','exec','-T','worker','node','scripts/export-public-db.ts')
 run('docker','compose','cp','worker:/data/public-site',str(stage))
 data=json.loads((stage/'public-news.json').read_text())
 if data.get('version')!=1 or set(data)-{'version','generatedAt','windowDays','groups','topics','items','stories','dailyIds'}:raise SystemExit('Invalid public projection')
 if not (stage/'index.html').exists():raise SystemExit('Run the free refresh once before syncing')
 if not args.publish:
  out=ROOT/'.local/public-preview/ai-news-radar';out.mkdir(parents=True,exist_ok=True)
  for name in ['index.html','history.html','public-news.json']:shutil.copyfile(stage/name,out/name)
  copy_reader(stage,out)
  # Preview includes sanitized editorial history. Publishing keeps the newer remote editorial files.
  for folder,pattern in [('',r'(latest|history|corrections)\.json'),('daily',r'\d{4}-\d{2}-\d{2}\.json'),('weekly',r'\d{4}-W\d{2}\.json'),('history',r'[a-f0-9]{64}\.json')]:
   src=stage/'data/trends'/folder;dst=out/'data/trends'/folder
   if src.exists():
    dst.mkdir(parents=True,exist_ok=True)
    for file in src.iterdir():
     if file.is_file() and re.fullmatch(pattern,file.name):shutil.copyfile(file,dst/file.name)
  print('Public preview written to .local/public-preview; nothing uploaded.')
 else:
  checkout.parent.mkdir(parents=True,exist_ok=True)
  if not checkout.exists():run('git','clone','--branch','master','--single-branch','https://github.com/LeaiFish/ai-news-radar.git',str(checkout))
  if run('git','status','--porcelain',cwd=checkout).strip():raise SystemExit('Dedicated Pages checkout has local changes; inspect before publishing')
  run('git','pull','--rebase',cwd=checkout)
  remote_snapshot=checkout/'public-news.json'
  if remote_snapshot.exists():
   current=json.loads(remote_snapshot.read_text())
   if current.get('generatedAt','') > data.get('generatedAt',''):
    print('The public site already has a newer news snapshot; skipped stale local export.')
    raise SystemExit(0)
  for name in ['index.html','history.html','public-news.json']:shutil.copyfile(stage/name,checkout/name)
  copy_reader(stage,checkout)
  run('git','add','--','index.html','history.html','public-news.json','assets/logo.svg','assets/styles.css','assets/sidebar.css','assets/topics.css','assets/perspective.css','assets/perspective.js','assets/public-projection.js','assets/aihot-skin.css','assets/research-analysis.js','assets/trend-reports.js','assets/trend-history.js','config/topics.json',cwd=checkout)
  if (checkout/'data/case-leads.json').exists():run('git','add','--','data/case-leads.json',cwd=checkout)
  if subprocess.run(['git','diff','--cached','--quiet'],cwd=checkout).returncode==0:print('No public changes')
  else:
   run('git','-c','user.name=AI Perspective publisher','-c','user.email=publisher@localhost','commit','-m','chore: publish local public-news projection',cwd=checkout)
   run('git','push','origin','HEAD:master',cwd=checkout)
   print('Published only reader assets and public-news.json')
