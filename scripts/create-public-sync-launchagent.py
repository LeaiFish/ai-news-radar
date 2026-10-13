#!/usr/bin/env python3
"""Generate a reviewable macOS timer; do not install it or change this machine."""
import plistlib
from pathlib import Path
root=Path(__file__).resolve().parent.parent
out=root/'.local/com.ai-perspective.public-sync.plist';out.parent.mkdir(parents=True,exist_ok=True)
config={'Label':'com.ai-perspective.public-sync','ProgramArguments':['/usr/bin/python3',str(root/'scripts/sync-public-site.py'),'--publish'],
 'WorkingDirectory':str(root),'StartInterval':3600,'RunAtLoad':False,
 'EnvironmentVariables':{'PATH':'/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin'},
 'StandardOutPath':str(root/'.local/public-sync.log'),'StandardErrorPath':str(root/'.local/public-sync-error.log')}
out.write_bytes(plistlib.dumps(config));print(f'Generated {out}; no timer has been installed.')
