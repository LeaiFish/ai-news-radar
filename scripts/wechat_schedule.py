"""Reuse a locally managed collector's public output without renewing again."""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import tempfile

from scripts.publish_wechat_snapshot import public_snapshot
from scripts.wechat_sources import published_datetime

SCHEMA = 'radar_wemprss_schedule_v1'


class ScheduleError(ValueError):
    """Only fixed, non-sensitive codes leave the schedule boundary."""


def reuse_scheduled_snapshot(source: Path, output: Path, entrypoint: Path, now: datetime):
    """Return None for the owner or unmanaged runs; otherwise reuse public metadata.

    An explicit marker lives in the private runtime. Missing, stale or invalid
    scheduled output never falls back to a second authenticated collection.
    """
    marker = source / 'data/radar-schedule.json'
    if not marker.exists():
        return None
    try:
        settings = json.loads(marker.read_text())
        if settings.get('schema') != SCHEMA or settings.get('enabled') is not True:
            raise ValueError()
        owner = (source.parent / 'scheduled-collector/scripts/wechat_wemprss.py').resolve()
        if entrypoint.resolve() == owner:
            return None
        path = source.parent / 'scheduled-state/public-snapshot.json'
        snapshot = public_snapshot(json.loads(path.read_text()), now)
        at = published_datetime(snapshot['last_run']['at'])
        if at is None or now - at > timedelta(hours=30):
            raise ScheduleError('wemprss_scheduled_snapshot_stale')
    except ScheduleError:
        raise
    except Exception:
        raise ScheduleError('wemprss_scheduled_snapshot_unavailable') from None
    # Preserve the real collection time and status; reuse is not a new scan.
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=output.parent, delete=False) as handle:
            temporary = Path(handle.name)
            os.fchmod(handle.fileno(), 0o600)
            json.dump(snapshot, handle, ensure_ascii=False, indent=2)
            handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return snapshot
