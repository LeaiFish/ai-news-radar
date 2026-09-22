"""Tests for daily story archives and weekly rollups."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import scripts.update_news as update_news
from scripts.story_archive import (
    build_daily_archive_payload,
    build_weekly_rollup_payload,
    daily_archive_path,
    iso_week_key,
    project_story_for_archive,
    should_write_daily_archive,
    update_story_archives,
    write_daily_archive,
    write_weekly_rollup,
)


NOW = datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc)  # Asia/Shanghai 18:00 same day
TODAY = date(2026, 9, 22)
YESTERDAY = date(2026, 9, 21)


def sample_story(
    story_id: str = "story_abc",
    *,
    title: str = "OpenAI ships GPT update",
    source_count: int = 2,
    importance_score: float = 0.9,
    importance_label: str = "官方更新",
    category: str = "official",
) -> dict:
    return {
        "story_id": story_id,
        "title": title,
        "url": f"https://example.com/{story_id}",
        "primary_url": f"https://example.com/{story_id}",
        "source": "OpenAI News",
        "source_names": ["OpenAI News", "The Verge"],
        "source_count": source_count,
        "importance_score": importance_score,
        "importance": importance_score,
        "importance_label": importance_label,
        "category": category,
        "reasons": ["official_source", "multi_source"],
        "earliest_at": "2026-09-22T01:00:00Z",
        "latest_at": "2026-09-22T08:00:00Z",
        "items": [{"id": "item-1", "title": title, "summary": "bulky nested payload"}],
        "sources": [{"id": "item-1", "title": title}],
        "primary_item": {"id": "item-1", "title": title},
    }


def test_project_story_drops_nested_bulky_fields():
    projected = project_story_for_archive(sample_story(), company_topic_ids=["openai"], lens_topic_ids=["monetization"])
    assert projected["story_id"] == "story_abc"
    assert projected["company_topics"] == ["openai"]
    assert projected["lens_topics"] == ["monetization"]
    assert "items" not in projected
    assert "sources" not in projected
    assert "primary_item" not in projected


def test_should_write_allows_same_day_refresh_and_blocks_past_day(tmp_path: Path):
    path = daily_archive_path(tmp_path, YESTERDAY)
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")

    assert should_write_daily_archive(path, YESTERDAY, today=TODAY, force=False) == (
        False,
        "no_clobber_past_day",
    )
    assert should_write_daily_archive(path, YESTERDAY, today=TODAY, force=True)[0] is True

    today_path = daily_archive_path(tmp_path, TODAY)
    today_path.write_text("{}", encoding="utf-8")
    assert should_write_daily_archive(today_path, TODAY, today=TODAY, force=False) == (
        True,
        "same_day_refresh",
    )


def test_write_daily_archive_no_clobber_previous_day(tmp_path: Path):
    payload = {
        "generated_at": "2026-09-21T12:00:00Z",
        "window_hours": 24,
        "stories": [sample_story("story_old")],
    }
    first = write_daily_archive(
        tmp_path,
        payload,
        now=NOW,
        archive_date=YESTERDAY,
        force=True,
    )
    assert first["written"] is True
    original = (tmp_path / "archive" / "daily" / "2026-09-21.json").read_text(encoding="utf-8")

    second = write_daily_archive(
        tmp_path,
        {
            "generated_at": "2026-09-22T12:00:00Z",
            "window_hours": 24,
            "stories": [sample_story("story_new", title="Should not overwrite")],
        },
        now=NOW,
        archive_date=YESTERDAY,
        force=False,
    )
    assert second["written"] is False
    assert second["reason"] == "no_clobber_past_day"
    assert (tmp_path / "archive" / "daily" / "2026-09-21.json").read_text(encoding="utf-8") == original


def test_same_day_rerun_refreshes_daily_archive(tmp_path: Path):
    write_daily_archive(
        tmp_path,
        {"generated_at": "2026-09-22T01:00:00Z", "window_hours": 24, "stories": [sample_story("story_1")]},
        now=NOW,
        force=False,
    )
    result = write_daily_archive(
        tmp_path,
        {
            "generated_at": "2026-09-22T10:00:00Z",
            "window_hours": 24,
            "stories": [sample_story("story_2"), sample_story("story_3")],
        },
        now=NOW,
        force=False,
    )
    assert result["written"] is True
    assert result["reason"] == "same_day_refresh"
    archived = json.loads((tmp_path / "archive" / "daily" / "2026-09-22.json").read_text(encoding="utf-8"))
    assert archived["story_count"] == 2
    assert archived["projection"] == "compact_v1"
    assert archived["timezone"] == "Asia/Shanghai"


def test_weekly_rollup_from_daily_fixtures(tmp_path: Path):
    daily_dir = tmp_path / "archive" / "daily"
    daily_dir.mkdir(parents=True)
    mon = date(2026, 9, 21)  # ISO 2026-W39
    tue = date(2026, 9, 22)
    assert iso_week_key(mon) == "2026-W39"
    assert iso_week_key(tue) == "2026-W39"

    for day, stories in (
        (
            mon,
            [
                project_story_for_archive(
                    sample_story("story_a", source_count=1, importance_score=0.5, importance_label="讨论"),
                    company_topic_ids=["openai"],
                    lens_topic_ids=["monetization"],
                )
            ],
        ),
        (
            tue,
            [
                project_story_for_archive(
                    sample_story("story_a", source_count=3, importance_score=0.95, importance_label="官方更新"),
                    company_topic_ids=["openai", "anthropic"],
                    lens_topic_ids=["monetization"],
                ),
                project_story_for_archive(
                    sample_story("story_b", title="Claude update", source_count=2, importance_score=0.8),
                    company_topic_ids=["anthropic"],
                    lens_topic_ids=[],
                ),
            ],
        ),
    ):
        payload = build_daily_archive_payload(
            [],
            archive_date=day,
            generated_at="2026-09-22T10:00:00Z",
            window_hours=24,
            company_topics=[],
            lens_topics=[],
        )
        payload["stories"] = stories
        payload["story_count"] = len(stories)
        (daily_dir / f"{day.isoformat()}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    result = write_weekly_rollup(tmp_path, week_key="2026-W39", now=NOW, generated_at="2026-09-22T10:00:00Z")
    assert result["written"] is True
    weekly = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert weekly["iso_week"] == "2026-W39"
    assert weekly["daily_dates"] == ["2026-09-21", "2026-09-22"]
    assert weekly["story_count"] == 3
    assert weekly["unique_story_count"] == 2
    assert weekly["counts"]["by_company_topic"]["openai"] == 2
    assert weekly["counts"]["by_company_topic"]["anthropic"] == 2
    assert weekly["counts"]["by_lens_topic"]["monetization"] == 2
    assert weekly["counts"]["by_importance_label"]["官方更新"] == 2
    assert weekly["counts"]["by_source_count_bucket"]["1"] == 1
    assert weekly["counts"]["by_source_count_bucket"]["2"] == 1
    assert weekly["counts"]["by_source_count_bucket"]["3+"] == 1
    assert weekly["top_stories"][0]["story_id"] == "story_a"
    assert weekly["top_stories"][0]["source_count"] == 3

    # Idempotent rebuild
    again = write_weekly_rollup(tmp_path, week_key="2026-W39", now=NOW, generated_at="2026-09-22T11:00:00Z")
    rebuilt = json.loads(Path(again["path"]).read_text(encoding="utf-8"))
    assert rebuilt["story_count"] == 3
    assert rebuilt["generated_at"] == "2026-09-22T11:00:00Z"


def test_build_weekly_rollup_payload_empty_week():
    payload = build_weekly_rollup_payload([], week_key="2026-W01", generated_at="2026-01-05T00:00:00Z")
    assert payload["story_count"] == 0
    assert payload["daily_dates"] == []
    assert payload["counts"]["by_source_count_bucket"] == {"1": 0, "2": 0, "3+": 0}


def test_update_news_main_calls_story_archive(monkeypatch, tmp_path: Path):
    calls: list[dict] = []

    def fake_update_story_archives(output_dir, stories_payload, *, now=None, force=False, topics_config=None):
        calls.append(
            {
                "output_dir": Path(output_dir),
                "story_count": len(stories_payload.get("stories") or []),
                "force": force,
                "now": now,
            }
        )
        return {
            "daily": {"path": str(tmp_path / "archive/daily/x.json"), "written": True, "reason": "create", "story_count": 0},
            "weekly": {"path": str(tmp_path / "archive/weekly/x.json"), "written": True, "iso_week": "2026-W39", "story_count": 0},
        }

    monkeypatch.setattr(update_news, "update_story_archives", fake_update_story_archives)
    monkeypatch.setattr(update_news, "create_session", lambda: object())
    monkeypatch.setattr(update_news, "fetch_service_status", lambda *_a, **_k: {"active_count": 0, "incidents": []})
    monkeypatch.setattr(update_news, "collect_all", lambda *_a, **_k: ([], []))
    monkeypatch.setattr(
        update_news,
        "maybe_fetch_agentmail_digest",
        lambda *_a, **_k: (None, {"enabled": False}),
    )
    monkeypatch.setattr(update_news, "maybe_fetch_x_api_updates", lambda *_a, **_k: ([], {"enabled": False}))
    monkeypatch.setattr(
        update_news,
        "maybe_fetch_socialdata_updates",
        lambda *_a, **_k: ([], {"enabled": False}),
    )
    monkeypatch.setattr(
        update_news,
        "maybe_fetch_tikhub_updates",
        lambda *_a, **_k: ([], {"enabled": False}),
    )
    monkeypatch.setattr(update_news, "load_paid_source_state", lambda *_a, **_k: {})
    monkeypatch.setattr(update_news, "update_paid_source_state", lambda *_a, **_k: None)
    monkeypatch.setattr(update_news, "sync_paid_source_status_timestamps", lambda *_a, **_k: None)
    monkeypatch.setattr(
        update_news,
        "fetch_waytoagi_recent_7d",
        lambda *_a, **_k: {
            "generated_at": "2026-09-22T10:00:00Z",
            "timezone": "Asia/Shanghai",
            "count_7d": 0,
            "updates_7d": [],
        },
    )
    monkeypatch.setattr(update_news, "waytoagi_updates_to_raw_items", lambda *_a, **_k: [])
    monkeypatch.setattr(update_news, "load_archive", lambda *_a, **_k: {})
    monkeypatch.setattr(update_news, "load_title_zh_cache", lambda *_a, **_k: {})
    monkeypatch.setattr(
        update_news,
        "add_bilingual_fields",
        lambda items_ai, items_all, *_a, **_k: (items_ai, items_all, {}),
    )
    monkeypatch.setattr(update_news, "add_title_enhancements", lambda items, *_a, **_k: (items, {}))
    monkeypatch.setattr(update_news, "add_recommend_reasons", lambda items, *_a, **_k: (items, {}))
    monkeypatch.setattr(update_news, "merge_story_items", lambda *_a, **_k: ([sample_story()], []))
    monkeypatch.setattr(
        update_news,
        "build_daily_brief_payload",
        lambda stories, **_k: {"generated_at": "x", "window_hours": 24, "total_items": 0, "items": []},
    )
    monkeypatch.setattr(
        update_news,
        "build_stories_payload",
        lambda stories, **_k: {
            "generated_at": "2026-09-22T10:00:00Z",
            "window_hours": 24,
            "total_stories": len(stories),
            "stories": stories,
        },
    )
    monkeypatch.setattr(
        update_news,
        "build_merge_log_payload",
        lambda events, **_k: {"generated_at": "x", "total_events": 0, "events": []},
    )
    monkeypatch.setattr(update_news, "build_creator_hot_items", lambda *_a, **_k: [])
    monkeypatch.setattr(
        update_news,
        "build_latest_payloads",
        lambda latest: (latest, {"items_all": [], "items_all_raw": []}),
    )
    monkeypatch.setattr(update_news, "sanitize_public_payload", lambda payload: payload)
    monkeypatch.setattr(update_news, "utc_now", lambda: NOW)

    # Avoid real topics build importing heavy deps
    import types
    import sys

    fake_build_topics = types.ModuleType("scripts.build_topics")
    fake_build_topics.write_topics_payload = lambda output_dir, generated_at=None: {"topic_count": 0}
    monkeypatch.setitem(sys.modules, "scripts.build_topics", fake_build_topics)
    monkeypatch.setitem(sys.modules, "build_topics", fake_build_topics)

    monkeypatch.setattr(
        sys,
        "argv",
        ["update_news.py", "--output-dir", str(tmp_path), "--window-hours", "24", "--archive-days", "21"],
    )
    assert update_news.main() == 0
    assert len(calls) == 1
    assert calls[0]["output_dir"] == tmp_path
    assert calls[0]["story_count"] == 1
    assert calls[0]["force"] is False
    assert (tmp_path / "stories-merged.json").exists()


def test_update_story_archives_writes_daily_and_weekly(tmp_path: Path):
    result = update_story_archives(
        tmp_path,
        {
            "generated_at": "2026-09-22T10:00:00Z",
            "window_hours": 24,
            "stories": [sample_story()],
        },
        now=NOW,
        force=False,
        topics_config=Path("/nonexistent/topics.json"),
    )
    assert result["daily"]["written"] is True
    assert result["weekly"]["written"] is True
    assert Path(result["daily"]["path"]).exists()
    assert Path(result["weekly"]["path"]).exists()
    assert "2026-W39" in result["weekly"]["iso_week"]
