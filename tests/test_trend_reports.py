from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess

import pytest

from scripts.trend_reports import (IDS, LATEST, REPORT_SCHEMA, archive_path, bind_input,
                                  digest, iso, load, periods, prepare, public_url,
                                  validate_latest, validate_report, write_report)
from scripts.publish_trend_report import publish


@pytest.fixture
def report():
    now = datetime.now(timezone.utc)
    source = now - timedelta(minutes=5)
    start, end = periods("daily", source)
    return {"schema": REPORT_SCHEMA, "kind": "daily", "period_start": iso(start), "period_end": iso(end),
            "source_snapshot_at": iso(source), "generated_at": iso(now), "input_id": "a" * 64,
            "previous_report_id": None, "companies": {slug: {"state": "insufficient", "reason": "原文证据不足，保留已有判断", "judgment": None, "changes": None, "digest": None, "events": []} for slug in IDS},
            "evidence": [], "overview": None}


def evidence(report, key="doubao-1", company="doubao"):
    return {"id": key, "url": "https://www.doubao.com/work", "title": "豆包工作", "source": "豆包", "published_at": report["period_start"],
            "event_at": report["period_start"], "verified_at": report["generated_at"], "company_ids": [company], "level": "official", "date_basis": "original_page", "note": "原文核验"}


def card(key="doubao-1"):
    return {"headline": "豆包工作补充网页分享", "summary": "用户可将生成的网页发布为分享链接。", "evidence_ids": [key]}


def updated(report):
    report["evidence"] = [evidence(report)]
    report["companies"]["doubao"].update(state="updated", judgment=card(), changes=[card()], digest=card(), events=[{"event_id": "doubao-pages", "status": "new", **card()}])
    return report


def test_unknown_or_old_event_cannot_be_today_new(report):
    updated(report)
    report["evidence"][0].update(published_at=None, event_at=None, date_basis="undated_document")
    with pytest.raises(ValueError, match="old_or_undated"):
        validate_report(report)
    report["companies"]["doubao"]["events"][0]["status"] = "supplement"
    assert validate_report(report)["report_id"]


def test_source_publication_is_not_inferred_from_discovery(report):
    updated(report)
    report["evidence"][0]["event_at"] = iso(datetime.fromisoformat(report["period_start"].replace("Z", "+00:00")) - timedelta(days=3))
    with pytest.raises(ValueError, match="old_or_undated"):
        validate_report(report)


def test_day_precision_does_not_invent_an_hour_inside_rolling_window(report):
    updated(report)
    report["evidence"][0].update(published_at="2026-10-21", event_at="2026-10-21")
    report.update(period_start="2026-10-21T07:00:00Z", period_end="2026-10-22T07:00:00Z", source_snapshot_at="2026-10-22T07:00:00Z", generated_at="2026-10-22T08:00:00Z")
    report["evidence"][0]["verified_at"] = report["generated_at"]
    with pytest.raises(ValueError, match="old_or_undated"):
        validate_report(report, now=datetime(2026, 10, 22, 8, tzinfo=timezone.utc))
    report["companies"]["doubao"]["events"][0]["status"] = "supplement"
    assert validate_report(report, now=datetime(2026, 10, 22, 8, tzinfo=timezone.utc))["evidence"][0]["published_at"] == "2026-10-21"


@pytest.mark.parametrize("url", ["https://127.0.0.1/a", "https://10.0.0.1/a", "https://host.local/a", "https://user:pass@example.com/a", "https://example.com/a?access_token=private", "http://example.com/a"])
def test_private_and_credential_urls_rejected(url):
    with pytest.raises(ValueError):
        public_url(url)


@pytest.mark.parametrize("where", ["top", "evidence", "card"])
def test_arbitrary_fields_cannot_be_published(report, where):
    updated(report)
    target = report if where == "top" else report["evidence"][0] if where == "evidence" else report["companies"]["doubao"]["judgment"]
    target["access_token"] = "private-value"
    with pytest.raises(ValueError):
        validate_report(report)


def test_credentials_in_allowed_text_rejected(report):
    updated(report)
    report["evidence"][0]["note"] = "Bearer very-private-value"
    with pytest.raises(ValueError, match="sensitive"):
        validate_report(report)


def test_refs_cannot_cross_company_or_disappear(report):
    updated(report)
    report["evidence"][0]["company_ids"] = ["openai"]
    with pytest.raises(ValueError, match="cross_company"):
        validate_report(report)
    report["evidence"] = []
    with pytest.raises(ValueError, match="missing_evidence"):
        validate_report(report)


def test_all_eight_companies_and_unique_events_required(report):
    updated(report)
    report["companies"]["doubao"]["events"] *= 2
    with pytest.raises(ValueError, match="duplicate_event"):
        validate_report(report)
    del report["companies"]["xai"]
    with pytest.raises(ValueError, match="eight"):
        validate_report(report)


def test_overview_needs_domestic_and_overseas_support(report):
    updated(report)
    report["evidence"].append(evidence(report, "qwen-1", "qwen"))
    report["overview"] = {"reason": "方向变化", "lead": "办公助手补充协作", "themes": [{**card(), "evidence_ids": ["doubao-1", "qwen-1"], "company_ids": ["doubao", "qwen"]}]}
    with pytest.raises(ValueError, match="domestic_and_overseas"):
        validate_report(report)
    report["evidence"][1]["company_ids"] = ["openai"]
    report["overview"]["themes"][0]["company_ids"] = ["doubao", "openai"]
    assert validate_report(report)["overview"]


def test_week_is_previous_completed_shanghai_week():
    start, end = periods("weekly", datetime(2026, 10, 26, 3, tzinfo=timezone.utc))
    assert iso(start) == "2026-10-18T16:00:00Z"
    assert iso(end) == "2026-10-25T16:00:00Z"


def test_unchanged_preserves_prior_judgment_and_date(tmp_path, report):
    updated(report)
    write_report(tmp_path, report)
    first = load(tmp_path / LATEST)
    next_report = deepcopy(report)
    next_report["kind"] = "weekly"
    start, end = periods("weekly", datetime.fromisoformat(report["source_snapshot_at"].replace("Z", "+00:00")))
    next_report.update(period_start=iso(start), period_end=iso(end), previous_report_id=first["report_id"], overview=None)
    for row in next_report["companies"].values():
        row.update(state="insufficient", judgment=None, changes=None, digest=None, events=[])
    write_report(tmp_path, next_report)
    latest = load(tmp_path / LATEST)
    assert latest["companies"]["doubao"]["judgment"] == first["companies"]["doubao"]["judgment"]
    assert latest["companies"]["doubao"]["weekly"] is None
    validate_latest(latest)


def test_issue_immutable_and_failed_update_leaves_latest_untouched(tmp_path, report):
    write_report(tmp_path, report)
    before = (tmp_path / LATEST).read_bytes()
    assert write_report(tmp_path, report)["status"] == "unchanged"
    report["companies"]["qwen"]["reason"] = "其他理由"
    with pytest.raises(ValueError, match="issue_already"):
        write_report(tmp_path, report)
    assert (tmp_path / LATEST).read_bytes() == before


def test_stale_parent_cannot_replace_newer_editorial(tmp_path, report):
    write_report(tmp_path, report)
    report["kind"] = "weekly"
    start, end = periods("weekly", datetime.fromisoformat(report["source_snapshot_at"].replace("Z", "+00:00")))
    report.update(period_start=iso(start), period_end=iso(end))
    with pytest.raises(ValueError, match="parent_changed"):
        write_report(tmp_path, report)


def test_input_hash_binds_report_to_snapshot(report):
    bundle = {k: report[k] for k in ("kind", "period_start", "period_end", "source_snapshot_at", "previous_report_id")}
    bundle["schema"] = "radar_trend_input_v1"
    bundle["input_id"] = digest(bundle)
    report["input_id"] = bundle["input_id"]
    bind_input(report, bundle)
    bundle["source_snapshot_at"] = "2026-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="tampered"):
        bind_input(report, bundle)


def test_persisted_payload_cannot_smuggle_extra_fields(tmp_path, report):
    updated(report)
    write_report(tmp_path, report)
    latest = load(tmp_path / LATEST)
    latest["companies"]["doubao"]["judgment"]["content"]["private"] = "value"
    with pytest.raises(ValueError):
        validate_latest(latest)


def test_rolling_windows_cannot_count_same_event_new_twice(tmp_path, report):
    updated(report)
    first_source = datetime(2026, 10, 21, 3, 20, tzinfo=timezone.utc)
    event = datetime(2026, 10, 21, 3, 15, tzinfo=timezone.utc)
    report.update(source_snapshot_at=iso(first_source), period_start=iso(first_source - timedelta(hours=24)), period_end=iso(first_source), generated_at=iso(first_source))
    report["evidence"][0].update(published_at=iso(event), event_at=iso(event), verified_at=iso(first_source))
    write_report(tmp_path, report, now=first_source)
    parent = load(tmp_path / LATEST)["report_id"]
    second_source = datetime(2026, 10, 22, 3, 10, tzinfo=timezone.utc)
    report.update(source_snapshot_at=iso(second_source), period_start=iso(second_source - timedelta(hours=24)), period_end=iso(second_source), generated_at=iso(second_source), previous_report_id=parent)
    report["evidence"][0]["verified_at"] = iso(second_source)
    with pytest.raises(ValueError, match="already_reported_event"):
        write_report(tmp_path, report, now=second_source)
    report["companies"]["doubao"]["events"][0]["status"] = "continuation"
    write_report(tmp_path, report, now=second_source)


def test_oversized_merge_is_rejected_before_touching_old_snapshot(tmp_path, report):
    write_report(tmp_path, report)
    old = (tmp_path / LATEST).read_bytes()
    previous = load(tmp_path / LATEST)
    report.update(kind="weekly", previous_report_id=previous["report_id"])
    start, end = periods("weekly", datetime.fromisoformat(report["source_snapshot_at"].replace("Z", "+00:00")))
    report.update(period_start=iso(start), period_end=iso(end))
    report["evidence"] = [{**evidence(report, key=f"e{i}"), "company_ids": list(IDS), "title": "t" * 400, "source": "s" * 120, "note": "n" * 600} for i in range(15)]
    large = {**card(), "summary": "a" * 1400, "evidence_ids": [e["id"] for e in report["evidence"]]}
    for row in report["companies"].values():
        row.update(state="updated", judgment=deepcopy(large), changes=[deepcopy(large) for _ in range(5)], digest=deepcopy(large), events=[])
    validate_report(report)
    with pytest.raises(ValueError):
        write_report(tmp_path, report)
    assert (tmp_path / LATEST).read_bytes() == old
    assert not (tmp_path / archive_path(validate_report(report))).exists()


def test_publisher_only_commits_two_public_paths(tmp_path, report):
    def run(*args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()
    remote = tmp_path / "remote.git"
    run("init", "--bare", "--initial-branch=master", str(remote))
    caller = tmp_path / "caller"
    run("clone", str(remote), str(caller))
    run("config", "user.name", "Test", cwd=caller)
    run("config", "user.email", "test@example.com", cwd=caller)
    (caller / "README.md").write_text("Existing public code")
    run("add", "README.md", cwd=caller)
    run("commit", "-m", "initial", cwd=caller)
    run("push", "origin", "master", cwd=caller)
    (caller / ".env").write_text("PRIVATE_VALUE=do-not-publish")
    (caller / "README.md").write_text("unrelated local edits")
    bundle = {k: report[k] for k in ("kind", "period_start", "period_end", "source_snapshot_at", "previous_report_id")}
    bundle["schema"] = "radar_trend_input_v1"
    bundle["input_id"] = digest(bundle)
    report["input_id"] = bundle["input_id"]
    result = publish(report, bundle, repository=str(remote))
    paths = set(run("show", "--format=", "--name-only", result["commit"], cwd=remote).splitlines())
    assert paths == {str(Path("data") / LATEST), str(Path("data") / archive_path(validate_report(report)))}
    assert run("show", "master:README.md", cwd=remote) == "Existing public code"
    assert (caller / ".env").read_text() == "PRIVATE_VALUE=do-not-publish"
