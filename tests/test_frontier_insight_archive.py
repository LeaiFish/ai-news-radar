"""Path / manifest checks for the imported frontier-insight external corpus."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "archive" / "external" / "frontier-insight"
MANIFEST = CORPUS / "manifest.json"
SOURCE = CORPUS / "SOURCE.md"


def test_source_attribution_present():
    text = SOURCE.read_text(encoding="utf-8")
    assert "https://github.com/Amb2rZhou/ai-frontier-insight" in text
    assert "third-party" in text.lower() or "Third-party" in text
    assert "竞争概览" in text


def test_manifest_lists_daily_and_weekly_ranges():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["source_repo"] == "https://github.com/Amb2rZhou/ai-frontier-insight"
    assert manifest["ui_surface"] == "none"

    daily = manifest["daily"]
    weekly = manifest["weekly"]
    assert daily["count"] == len(daily["dates"]) >= 100
    assert weekly["count"] == len(weekly["weeks"]) >= 10
    assert daily["first"] == "2026-02-25"
    assert daily["last"] == "2026-07-17"
    assert weekly["first"] == "2026-W10"
    assert weekly["last"] == "2026-W21"
    assert daily["dates"] == sorted(daily["dates"])
    assert weekly["weeks"] == sorted(weekly["weeks"])


def test_manifest_paths_exist_on_disk():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    known_bad_weekly = set(manifest.get("parse_notes", {}).get("weekly_invalid_json", []))

    for date in manifest["daily"]["dates"]:
        brief = CORPUS / "daily" / date / "brief.json"
        assert brief.is_file(), f"missing daily brief for {date}"
        assert brief.stat().st_size > 0
        payload = json.loads(brief.read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        assert payload.get("date") in (date, None) or "insights" in payload or "trend_summary" in payload

    for week in manifest["weekly"]["weeks"]:
        weekly_json = CORPUS / "weekly" / f"{week}.json"
        assert weekly_json.is_file(), f"missing weekly json for {week}"
        assert weekly_json.stat().st_size > 0
        text = weekly_json.read_text(encoding="utf-8")
        if week in known_bad_weekly:
            # Upstream copy kept verbatim despite invalid JSON escapes.
            assert text.lstrip().startswith("{")
        else:
            payload = json.loads(text)
            assert isinstance(payload, dict)
        weekly_md = CORPUS / "weekly" / f"{week}.md"
        assert weekly_md.is_file(), f"missing weekly md for {week}"
        assert weekly_md.stat().st_size > 0


def test_entries_match_top_level_date_lists():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert [e["date"] for e in manifest["entries"]["daily"]] == manifest["daily"]["dates"]
    assert [e["week"] for e in manifest["entries"]["weekly"]] == manifest["weekly"]["weeks"]
    for entry in manifest["entries"]["daily"]:
        assert "brief.json" in entry["files"]
    for entry in manifest["entries"]["weekly"]:
        assert f"{entry['week']}.json" in entry["files"]
        assert f"{entry['week']}.md" in entry["files"]
