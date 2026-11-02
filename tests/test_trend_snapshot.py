import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
from scripts.ensure_trend_snapshot import ensure, gate_for, qualified

NOW = datetime(2026, 11, 2, 3, 10, tzinfo=timezone.utc)

class SnapshotTests(unittest.TestCase):
    def test_gate_and_dates(self):
        self.assertEqual(gate_for(NOW).isoformat(), '2026-11-02T02:40:00+00:00')
        for stamp in (None, '', '2026-11-02', '2026-11-02T02:39:59Z',
                      '2026-11-01T03:00:00Z', '2026-11-02T04:00:00Z'):
            self.assertFalse(qualified(stamp, NOW))
        self.assertTrue(qualified('2026-11-02T02:40:00Z', NOW))

    def exercise(self, stamps, runs=(), dirty=False, timeout=200):
        calls, ticks = [], [0]
        snapshots = iter(stamps)
        last = [None]
        def run(args, **kwargs):
            calls.append(args)
            output = ''
            if args[:3] == ['git', 'status', '--porcelain']:
                output = ' M file' if dirty else ''
            elif args[:3] == ['git', 'remote', 'get-url']:
                output = 'git@github.com:LeaiFish/ai-news-radar.git'
            elif args[:2] == ['git', 'show']:
                last[0] = next(snapshots, last[0])
                output = json.dumps({'generated_at': last[0]})
            elif args[:3] == ['gh', 'run', 'list']:
                output = json.dumps(runs)
            return SimpleNamespace(returncode=0, stdout=output)
        def sleep(seconds):
            self.assertLessEqual(seconds, 60)
            ticks[0] += seconds
        return calls, lambda: ensure(Path('/tmp/test-radar'), timeout, run=run,
            now=lambda: NOW, monotonic=lambda: ticks[0], sleep=sleep)

    def test_ready_does_not_dispatch(self):
        calls, action = self.exercise(['2026-11-02T03:00:00Z'])
        self.assertFalse(action()['fallback_dispatched'])
        self.assertFalse(any(c[0] == 'gh' for c in calls))
        self.assertEqual(calls[-1][-1], 'origin/master')

    def test_stale_dispatches_once_then_refreshes(self):
        calls, action = self.exercise(['2026-11-02T02:18:00Z'] * 2 + ['2026-11-02T03:00:00Z'])
        self.assertTrue(action()['fallback_dispatched'])
        dispatch = [c for c in calls if c[:3] == ['gh', 'workflow', 'run']]
        self.assertEqual(len(dispatch), 1)
        self.assertIn('refresh_wechat=false', dispatch[0])

    def test_active_run_waits_without_duplicate_dispatch(self):
        calls, action = self.exercise(['2026-11-02T02:18:00Z', '2026-11-02T03:00:00Z'],
                                      [{'status': 'in_progress'}])
        self.assertFalse(action()['fallback_dispatched'])
        self.assertFalse(any(c[:3] == ['gh', 'workflow', 'run'] for c in calls))

    def test_timeout_does_not_checkout_old_data(self):
        calls, action = self.exercise(['2026-11-02T02:18:00Z'], timeout=60)
        with self.assertRaisesRegex(RuntimeError, 'snapshot_gate_timeout'):
            action()
        self.assertFalse(any(c[:2] == ['git', 'checkout'] for c in calls))

    def test_dirty_clone_refused(self):
        calls, action = self.exercise([], dirty=True)
        with self.assertRaisesRegex(RuntimeError, 'requires_clean_clone'):
            action()
        self.assertEqual(len(calls), 1)

if __name__ == '__main__':
    unittest.main()
