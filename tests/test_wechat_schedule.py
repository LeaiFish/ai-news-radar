from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from scripts.wechat_schedule import SCHEMA, ScheduleError, reuse_scheduled_snapshot

NOW = datetime(2026, 10, 28, 7, tzinfo=timezone.utc)


def setup_schedule(tmp_path, age=timedelta(), enabled=True, now=NOW):
    source = tmp_path / 'runtime'
    (source / 'data').mkdir(parents=True)
    (source / 'data/radar-schedule.json').write_text(json.dumps({'schema': SCHEMA, 'enabled': enabled}))
    state = tmp_path / 'scheduled-state'
    state.mkdir()
    at = (now - age).isoformat()
    payload = {'schema': 'wechat_accounts_v1', 'updated': at, 'accounts': {},
               'private_cookie': 'must_not_leave_input',
               'last_run': {'at': at, 'ok': False, 'searched_accounts': 0, 'candidates': 0,
                            'verified': 0, 'added': 0, 'covered_companies': 0, 'covered_accounts': 0,
                            'collector': 'wemprss', 'errors': [], 'collection_state': 'partial'}}
    (state / 'public-snapshot.json').write_text(json.dumps(payload))
    return source, tmp_path / 'scheduled-collector/scripts/wechat_wemprss.py'


def test_unmanaged_and_owner_do_not_reuse(tmp_path):
    assert reuse_scheduled_snapshot(tmp_path, tmp_path / 'out', Path(__file__), NOW) is None
    source, owner = setup_schedule(tmp_path)
    assert reuse_scheduled_snapshot(source, tmp_path / 'out', owner, NOW) is None
    assert not (tmp_path / 'out').exists()


def test_other_entrypoint_reuses_only_public_fields_and_original_status(tmp_path):
    source, _ = setup_schedule(tmp_path, timedelta(minutes=10))
    output = tmp_path / 'out.json'
    snapshot = reuse_scheduled_snapshot(source, output, Path(__file__), NOW)
    assert snapshot == json.loads(output.read_text())
    assert snapshot['last_run']['at'] == (NOW - timedelta(minutes=10)).isoformat()
    assert snapshot['last_run']['ok'] is False
    assert 'private_cookie' not in snapshot
    assert output.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('failure', ['stale', 'missing', 'invalid_marker'])
def test_bad_output_never_enables_private_fallback_or_overwrites_history(tmp_path, failure):
    source, _ = setup_schedule(tmp_path, timedelta(hours=31) if failure == 'stale' else timedelta())
    if failure == 'missing':
        (tmp_path / 'scheduled-state/public-snapshot.json').unlink()
    if failure == 'invalid_marker':
        (source / 'data/radar-schedule.json').write_text('{}')
    output = tmp_path / 'out.json'
    output.write_text('previous')
    with pytest.raises(ScheduleError):
        reuse_scheduled_snapshot(source, output, Path(__file__), NOW)
    assert output.read_text() == 'previous'


def test_existing_collector_cli_reuses_without_starting_worker(tmp_path, monkeypatch, capsys):
    from scripts import wechat_wemprss
    source, _ = setup_schedule(tmp_path, timedelta(minutes=10), now=datetime.now(timezone.utc))
    monkeypatch.setattr('sys.argv', ['collector', '--source-dir', str(source), '--output', str(tmp_path / 'out')])
    def forbidden(*args, **kwargs):
        raise AssertionError('authenticated worker must not start')
    monkeypatch.setattr(wechat_wemprss.subprocess, 'run', forbidden)
    assert wechat_wemprss.main() == 2
    assert json.loads(capsys.readouterr().out)['scheduled_snapshot_reused'] is True


def test_schedule_lock_prevents_concurrent_collection(tmp_path, monkeypatch, capsys):
    import fcntl
    from scripts import run_wechat_schedule
    source, owner = setup_schedule(tmp_path)
    monkeypatch.setattr(run_wechat_schedule, 'ROOT', owner.parents[1])
    with (tmp_path / 'scheduled-state/collector.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert run_wechat_schedule.run(source) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'already_running'
