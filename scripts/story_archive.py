"""Daily story archives + weekly rollups for long-horizon trend analysis.

Live snapshots (`data/stories-merged.json`, `data/daily-brief.json`) stay the
rolling window view. This module writes immutable calendar-day archives under
`data/archive/daily/` and rebuildable ISO-week rollups under
`data/archive/weekly/`.

Daily files store a **compact** story projection (not full nested items/sources)
so git history stays manageable; see docs/ARCHIVE.md.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

UTC = timezone.utc
SH_TZ = ZoneInfo("Asia/Shanghai")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOPICS_CONFIG = ROOT / "config" / "topics.json"

DAILY_SCHEMA_VERSION = 1
WEEKLY_SCHEMA_VERSION = 1
ARCHIVE_PROJECTION = "compact_v1"

# Nested item/source lists are dropped; point back to the live window file.
LIVE_STORIES_POINTER = "data/stories-merged.json"

SOURCE_COUNT_BUCKETS = ("1", "2", "3+")
TOP_STORY_LIMIT = 40


def shanghai_calendar_date(now: datetime | None = None) -> date:
    current = now or datetime.now(tz=UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(SH_TZ).date()


def iso_week_key(day: date) -> str:
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def iso_week_bounds(day: date) -> tuple[date, date]:
    """Monday–Sunday bounds for the ISO week containing ``day``."""
    iso = day.isocalendar()
    monday = date.fromisocalendar(iso.year, iso.week, 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def daily_archive_path(output_dir: Path, day: date) -> Path:
    return Path(output_dir) / "archive" / "daily" / f"{day.isoformat()}.json"


def weekly_archive_path(output_dir: Path, week_key: str) -> Path:
    return Path(output_dir) / "archive" / "weekly" / f"{week_key}.json"


def source_count_bucket(count: int) -> str:
    if count <= 1:
        return "1"
    if count == 2:
        return "2"
    return "3+"


def _load_topic_matcher():
    try:
        from scripts.build_topics import load_topic_config, record_matches_topic
    except ModuleNotFoundError:  # pragma: no cover - direct script execution
        from build_topics import load_topic_config, record_matches_topic
    return load_topic_config, record_matches_topic


def load_company_and_lens_topics(
    config_path: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    path = Path(config_path) if config_path else DEFAULT_TOPICS_CONFIG
    if not path.exists():
        return [], []
    load_topic_config, _ = _load_topic_matcher()
    try:
        config = load_topic_config(path)
    except (FileNotFoundError, ValueError, OSError):
        return [], []
    company: list[dict[str, Any]] = []
    lens: list[dict[str, Any]] = []
    for topic in config.get("topics") or []:
        if not isinstance(topic, dict):
            continue
        group = str(topic.get("group") or "").strip()
        if group == "company":
            company.append(topic)
        elif group == "lens":
            lens.append(topic)
    return company, lens


def match_story_topic_ids(
    story: dict[str, Any],
    company_topics: list[dict[str, Any]],
    lens_topics: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    _, record_matches_topic = _load_topic_matcher()
    company_ids = [
        str(topic["id"])
        for topic in company_topics
        if record_matches_topic(story, topic)
    ]
    lens_ids = [
        str(topic["id"])
        for topic in lens_topics
        if record_matches_topic(story, topic)
    ]
    return company_ids, lens_ids


def project_story_for_archive(
    story: dict[str, Any],
    *,
    company_topic_ids: list[str] | None = None,
    lens_topic_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Compact projection: keep trend fields, drop bulky nested item copies."""
    url = str(story.get("url") or story.get("primary_url") or "")
    source_names = story.get("source_names")
    if not isinstance(source_names, list):
        source_names = []
    reasons = story.get("reasons")
    if not isinstance(reasons, list):
        reasons = []
    return {
        "story_id": str(story.get("story_id") or ""),
        "title": str(story.get("title") or ""),
        "url": url,
        "primary_url": str(story.get("primary_url") or url),
        "source": str(story.get("source") or ""),
        "source_names": [str(name) for name in source_names if str(name).strip()],
        "source_count": int(story.get("source_count") or 0),
        "importance_score": float(story.get("importance_score") or story.get("importance") or 0.0),
        "importance_label": str(story.get("importance_label") or ""),
        "category": str(story.get("category") or ""),
        "reasons": [str(reason) for reason in reasons if str(reason).strip()],
        "earliest_at": story.get("earliest_at"),
        "latest_at": story.get("latest_at"),
        "company_topics": list(company_topic_ids or []),
        "lens_topics": list(lens_topic_ids or []),
    }


def build_daily_archive_payload(
    stories: list[dict[str, Any]],
    *,
    archive_date: date,
    generated_at: str,
    window_hours: int,
    company_topics: list[dict[str, Any]] | None = None,
    lens_topics: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if company_topics is None or lens_topics is None:
        loaded_company, loaded_lens = load_company_and_lens_topics()
        company_topics = company_topics if company_topics is not None else loaded_company
        lens_topics = lens_topics if lens_topics is not None else loaded_lens

    projected: list[dict[str, Any]] = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        company_ids, lens_ids = match_story_topic_ids(story, company_topics, lens_topics)
        projected.append(
            project_story_for_archive(
                story,
                company_topic_ids=company_ids,
                lens_topic_ids=lens_ids,
            )
        )

    return {
        "schema_version": DAILY_SCHEMA_VERSION,
        "projection": ARCHIVE_PROJECTION,
        "archive_date": archive_date.isoformat(),
        "timezone": "Asia/Shanghai",
        "generated_at": generated_at,
        "window_hours": int(window_hours),
        "story_count": len(projected),
        "live_snapshot": LIVE_STORIES_POINTER,
        "stories": projected,
    }


def should_write_daily_archive(
    path: Path,
    archive_date: date,
    *,
    today: date,
    force: bool = False,
) -> tuple[bool, str]:
    """Decide whether to write ``path``.

    Same Shanghai calendar day may be refreshed. Past days are immutable unless
    ``force`` is set.
    """
    if force:
        return True, "forced"
    if not path.exists():
        return True, "create"
    if archive_date == today:
        return True, "same_day_refresh"
    return False, "no_clobber_past_day"


def write_json(path: Path, payload: dict[str, Any], *, indent: int | None = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=indent)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def write_daily_archive(
    output_dir: Path,
    stories_payload: dict[str, Any],
    *,
    now: datetime | None = None,
    archive_date: date | None = None,
    force: bool = False,
    topics_config: Path | None = None,
) -> dict[str, Any]:
    """Write a Shanghai calendar-day archive from a stories-merged payload.

    Defaults to today (Asia/Shanghai). Passing ``archive_date`` is mainly for
    tests / repairs; past days refuse overwrite unless ``force`` is set.
    """
    current = now or datetime.now(tz=UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    today = shanghai_calendar_date(current)
    day = archive_date or today
    path = daily_archive_path(output_dir, day)
    allowed, reason = should_write_daily_archive(path, day, today=today, force=force)
    result: dict[str, Any] = {
        "path": str(path),
        "archive_date": day.isoformat(),
        "written": False,
        "reason": reason,
    }
    if not allowed:
        return result

    stories = stories_payload.get("stories")
    if not isinstance(stories, list):
        stories = []
    company_topics, lens_topics = load_company_and_lens_topics(topics_config)
    generated_at = str(
        stories_payload.get("generated_at")
        or current.astimezone(UTC).isoformat().replace("+00:00", "Z")
    )
    window_hours = int(stories_payload.get("window_hours") or 24)
    payload = build_daily_archive_payload(
        stories,
        archive_date=day,
        generated_at=generated_at,
        window_hours=window_hours,
        company_topics=company_topics,
        lens_topics=lens_topics,
    )
    write_json(path, payload)
    result["written"] = True
    result["story_count"] = payload["story_count"]
    return result


def _load_daily_payload(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def iter_daily_archives_for_week(daily_dir: Path, week_key: str) -> list[tuple[date, dict[str, Any]]]:
    if not daily_dir.exists():
        return []
    collected: list[tuple[date, dict[str, Any]]] = []
    for path in sorted(daily_dir.glob("????-??-??.json")):
        try:
            day = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if iso_week_key(day) != week_key:
            continue
        payload = _load_daily_payload(path)
        if payload is None:
            continue
        collected.append((day, payload))
    return collected


def build_weekly_rollup_payload(
    daily_entries: list[tuple[date, dict[str, Any]]],
    *,
    week_key: str,
    generated_at: str,
) -> dict[str, Any]:
    if not daily_entries:
        # Still emit a valid empty rollup when asked for a known week.
        year_str, week_str = week_key.split("-W", 1)
        monday = date.fromisocalendar(int(year_str), int(week_str), 1)
        sunday = monday + timedelta(days=6)
        return {
            "schema_version": WEEKLY_SCHEMA_VERSION,
            "iso_week": week_key,
            "timezone": "Asia/Shanghai",
            "week_start": monday.isoformat(),
            "week_end": sunday.isoformat(),
            "generated_at": generated_at,
            "daily_dates": [],
            "story_count": 0,
            "unique_story_count": 0,
            "counts": {
                "by_company_topic": {},
                "by_lens_topic": {},
                "by_importance_label": {},
                "by_source_count_bucket": {bucket: 0 for bucket in SOURCE_COUNT_BUCKETS},
            },
            "top_stories": [],
        }

    monday, sunday = iso_week_bounds(daily_entries[0][0])
    company_counts: Counter[str] = Counter()
    lens_counts: Counter[str] = Counter()
    importance_counts: Counter[str] = Counter()
    source_bucket_counts: Counter[str] = Counter({bucket: 0 for bucket in SOURCE_COUNT_BUCKETS})
    best_by_id: dict[str, dict[str, Any]] = {}
    daily_dates: list[str] = []
    story_count = 0

    for day, payload in daily_entries:
        daily_dates.append(day.isoformat())
        stories = payload.get("stories")
        if not isinstance(stories, list):
            continue
        for story in stories:
            if not isinstance(story, dict):
                continue
            story_count += 1
            story_id = str(story.get("story_id") or "").strip()
            importance_label = str(story.get("importance_label") or "unknown") or "unknown"
            importance_counts[importance_label] += 1
            source_count = int(story.get("source_count") or 0)
            source_bucket_counts[source_count_bucket(source_count)] += 1
            for topic_id in story.get("company_topics") or []:
                if str(topic_id).strip():
                    company_counts[str(topic_id)] += 1
            for topic_id in story.get("lens_topics") or []:
                if str(topic_id).strip():
                    lens_counts[str(topic_id)] += 1

            if not story_id:
                continue
            candidate = {
                "story_id": story_id,
                "title": str(story.get("title") or ""),
                "url": str(story.get("url") or story.get("primary_url") or ""),
                "importance_score": float(story.get("importance_score") or 0.0),
                "importance_label": importance_label,
                "source_count": source_count,
                "archive_date": day.isoformat(),
                "company_topics": list(story.get("company_topics") or []),
                "lens_topics": list(story.get("lens_topics") or []),
            }
            existing = best_by_id.get(story_id)
            if existing is None or (
                candidate["importance_score"],
                candidate["source_count"],
            ) > (
                existing["importance_score"],
                existing["source_count"],
            ):
                best_by_id[story_id] = candidate

    top_stories = sorted(
        best_by_id.values(),
        key=lambda item: (item["importance_score"], item["source_count"], item["story_id"]),
        reverse=True,
    )[:TOP_STORY_LIMIT]

    return {
        "schema_version": WEEKLY_SCHEMA_VERSION,
        "iso_week": week_key,
        "timezone": "Asia/Shanghai",
        "week_start": monday.isoformat(),
        "week_end": sunday.isoformat(),
        "generated_at": generated_at,
        "daily_dates": daily_dates,
        "story_count": story_count,
        "unique_story_count": len(best_by_id),
        "counts": {
            "by_company_topic": dict(sorted(company_counts.items())),
            "by_lens_topic": dict(sorted(lens_counts.items())),
            "by_importance_label": dict(sorted(importance_counts.items())),
            "by_source_count_bucket": {
                bucket: int(source_bucket_counts.get(bucket, 0)) for bucket in SOURCE_COUNT_BUCKETS
            },
        },
        "top_stories": top_stories,
    }


def write_weekly_rollup(
    output_dir: Path,
    *,
    week_key: str | None = None,
    now: datetime | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Rebuild one ISO-week rollup from daily archive files (idempotent)."""
    current = now or datetime.now(tz=UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    day = shanghai_calendar_date(current)
    key = week_key or iso_week_key(day)
    daily_dir = Path(output_dir) / "archive" / "daily"
    entries = iter_daily_archives_for_week(daily_dir, key)
    stamp = generated_at or current.astimezone(UTC).isoformat().replace("+00:00", "Z")
    payload = build_weekly_rollup_payload(entries, week_key=key, generated_at=stamp)
    path = weekly_archive_path(output_dir, key)
    write_json(path, payload)
    return {
        "path": str(path),
        "iso_week": key,
        "written": True,
        "daily_dates": payload["daily_dates"],
        "story_count": payload["story_count"],
    }


def update_story_archives(
    output_dir: Path,
    stories_payload: dict[str, Any],
    *,
    now: datetime | None = None,
    force: bool = False,
    topics_config: Path | None = None,
) -> dict[str, Any]:
    """Write/refresh today's daily archive and rebuild its ISO-week rollup."""
    daily = write_daily_archive(
        output_dir,
        stories_payload,
        now=now,
        force=force,
        topics_config=topics_config,
    )
    archive_date = date.fromisoformat(str(daily["archive_date"]))
    week_key = iso_week_key(archive_date)
    generated_at = str(stories_payload.get("generated_at") or "")
    weekly = write_weekly_rollup(
        output_dir,
        week_key=week_key,
        now=now,
        generated_at=generated_at or None,
    )
    return {"daily": daily, "weekly": weekly}
