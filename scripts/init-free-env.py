#!/usr/bin/env python3
"""Create local credentials without printing them or enabling paid services."""
import os, secrets
from pathlib import Path
root=Path(__file__).resolve().parent.parent
path=root/'.env'
content='\n'.join(['RADAR_FREE_ONLY=1','MODEL_CALLS_ENABLED=false','COLLECT_ENABLED=false','SITE_URL=http://localhost:3000','PORT=3000',
 'ADMIN_PASSWORD='+secrets.token_urlsafe(24),'SESSION_SECRET='+secrets.token_hex(32),'IMG_PROXY_SIGN_SECRET='+secrets.token_hex(32),
 'POSTGRES_PASSWORD='+secrets.token_hex(24),'LLM_API_KEY=','SOCIALDATA_API_KEY=','DAJIALA_KEY=','JINA_API_KEY=','EMBEDDING_API_KEY=','DASHSCOPE_API_KEY=',''])
try:
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
except FileExistsError:
 raise SystemExit('.env already exists; retained unchanged. Review free-only settings before startup.')
with os.fdopen(fd,'w') as stream: stream.write(content)
print('Created private .env (0600). Admin password is stored there; paid services are disabled.')
