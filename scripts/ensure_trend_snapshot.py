#!/usr/bin/env python3
"""Wait for a qualified public snapshot, dispatching one free refresh if idle.

Run only in a clean /tmp clone. No credentials or raw subprocess diagnostics are
read/exported. This does not generate or publish editorial trend reports.
"""
from datetime import datetime, time as daytime, timezone
import argparse
import json
from pathlib import Path
import subprocess
import time
from zoneinfo import ZoneInfo

REPO = 'LeaiFish/ai-news-radar'
WORKFLOW = 'update-news.yml'
UTC = timezone.utc


def gate_for(now):
    local = now.astimezone(ZoneInfo('Asia/Shanghai'))
    return datetime.combine(local.date(), daytime(10, 40), local.tzinfo).astimezone(UTC)


def qualified(stamp, now):
    if not isinstance(stamp, str):
        return False
    try:
        value = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        return value.tzinfo is not None and gate_for(now) <= value <= now
    except ValueError:
        return False


def ensure(root, timeout=1800, *, run=None, now=None, monotonic=None, sleep=None):
    now = now or (lambda: datetime.now(UTC))
    monotonic = monotonic or time.monotonic
    sleep = sleep or time.sleep
    end = monotonic() + timeout
    run = run or subprocess.run
    def command(*args):
        remaining = end - monotonic()
        if remaining <= 0:
            raise RuntimeError('snapshot_gate_timeout')
        result = run(list(args), cwd=root, capture_output=True, text=True,
                     timeout=min(40, remaining), check=False)
        if result.returncode:
            raise RuntimeError('snapshot_operation_failed')
        return result.stdout.strip()

    # Refuse the owner's worktree, dirty checkouts and a different repository.
    temp = Path('/tmp').resolve()
    if not root.resolve().is_relative_to(temp):
        raise RuntimeError('requires_isolated_tmp_clone')
    if command('git', 'status', '--porcelain'):
        raise RuntimeError('requires_clean_clone')
    if command('git', 'remote', 'get-url', 'origin') != f'git@github.com:{REPO}.git':
        raise RuntimeError('unexpected_repository')
    if now() < gate_for(now()):
        raise RuntimeError('before_daily_snapshot_gate')

    dispatched = False
    while monotonic() < end:
        command('git', 'fetch', '--quiet', '--depth', '1', 'origin', 'master')
        payload = json.loads(command('git', 'show', 'origin/master:data/topics.json'))
        stamp = payload.get('generated_at')
        if qualified(stamp, now()):
            command('git', 'checkout', '--quiet', '--detach', 'origin/master')
            return {'status': 'ready', 'source_snapshot_at': stamp,
                    'fallback_dispatched': dispatched}
        runs = json.loads(command('gh', 'run', 'list', '--repo', REPO,
                                 '--workflow', WORKFLOW, '--branch', 'master', '--limit', '30',
                                 '--json', 'status'))
        if not dispatched and not any(r['status'] != 'completed' for r in runs):
            # Existing workflow stays free-only; do not repeat the long WeChat
            # discovery in this deadline-bound recovery. Its coverage stays partial.
            command('gh', 'workflow', 'run', WORKFLOW, '--repo', REPO,
                    '--ref', 'master', '-f', 'refresh_wechat=false')
            dispatched = True
            print(json.dumps({'status': 'fallback_dispatched', 'wechat_refresh': False}), flush=True)
        sleep(min(50, max(0, end - monotonic())))
    raise RuntimeError('snapshot_gate_timeout')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=int, default=1800)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 1800:
        parser.error('timeout must be 1..1800 seconds')
    try:
        print(json.dumps(ensure(Path.cwd(), args.timeout)), flush=True)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        # Errors from external tools must never leak raw logs or private values.
        reason = str(exc) if type(exc) is RuntimeError else 'snapshot_operation_failed'
        raise SystemExit(reason + '; retain previous judgments') from None


if __name__ == '__main__':
    main()
