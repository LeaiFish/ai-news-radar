#!/usr/bin/env python3
"""Run the private scheduled collector with a shared lock and public-only output."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.publish_wechat_snapshot import public_snapshot
from scripts.wechat_schedule import SCHEMA


def run(source):
    source = source.resolve()
    # This entrypoint is installed only into the private, pinned collector.
    if ROOT != source.parent / 'scheduled-collector':
        raise ValueError('private_schedule_install_required')
    state = source.parent / 'scheduled-state'
    state.mkdir(mode=0o700, exist_ok=True)
    with (state / 'collector.lock').open('a') as lock:
        os.fchmod(lock.fileno(), 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({'status': 'already_running', 'private_collection_started': False}))
            return 0
        marker = source / 'data/radar-schedule.json'
        temporary = None
        try:
            with tempfile.NamedTemporaryFile('w', dir=marker.parent, delete=False) as handle:
                temporary = Path(handle.name)
                os.fchmod(handle.fileno(), 0o600)
                json.dump({'schema': SCHEMA, 'enabled': True}, handle)
                handle.flush(); os.fsync(handle.fileno())
            temporary.replace(marker)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        started = datetime.now(timezone.utc)
        output = state / 'public-snapshot.json'
        result = subprocess.run([str(source / '.venv/bin/python'), '-B',
            str(ROOT / 'scripts/wechat_wemprss.py'), '--source-dir', str(source),
            '--output', str(output)], cwd=source, capture_output=True, timeout=390)
        if result.returncode not in (0, 2):
            raise ValueError('scheduled_collection_failed')
        snapshot = public_snapshot(json.loads(output.read_text()), datetime.now(timezone.utc))
        if datetime.fromisoformat(snapshot['last_run']['at'].replace('Z', '+00:00')) < started:
            raise ValueError('scheduled_output_not_updated')
        print(json.dumps(snapshot['last_run'], ensure_ascii=False))
        return result.returncode


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        raise SystemExit(run(args.source_dir))
    except Exception:
        # Never expose upstream diagnostics, credentials or response bodies.
        print(json.dumps({'error': 'wemprss_scheduled_collection_failed'}))
        raise SystemExit(1)
