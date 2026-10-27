#!/usr/bin/env python3
"""Public editorial reports. No model API, account credentials, or raw article storage.

prepare produces candidate leads, not verified facts. The local Codex task reads
original pages before authoring a report. apply validates the public contract;
publish revalidates it against the latest remote parent in an isolated clone.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

UTC = timezone.utc
SH = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[1]
IDS = ("doubao", "qwen", "hunyuan", "openai", "anthropic", "xai", "google-gemini", "meta-llama")
DOMESTIC = frozenset(IDS[:3])
LATEST = Path("trends/latest.json")
REPORT_SCHEMA = "radar_trend_report_v1"
LATEST_SCHEMA = "radar_trends_v1"
SECRET = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})|\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}|\bBearer\s+\S+|(?:access_token|refresh_token|client_secret|authorization|password|cookie)\s*[:=]\s*\S+", re.I)
BAD_QUERY = frozenset({"token", "access_token", "refresh_token", "api_key", "apikey", "key", "secret", "password", "auth", "authorization", "cookie", "code", "iga_token", "iga_time", "x-signature"})


def history_module():
    try:
        from scripts import trend_history
    except ModuleNotFoundError:
        import trend_history
    return trend_history


def require(condition, code):
    if not condition:
        raise ValueError(code)


def keys(value, expected, code):
    require(isinstance(value, dict) and set(value) == set(expected.split()), code)


def stamp(value):
    require(isinstance(value, str), "invalid_timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid_timestamp") from None
    require(result.tzinfo is not None, "timestamp_needs_timezone")
    return result.astimezone(UTC)


def iso(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def date_floor(value):
    # Preserve date-only precision publicly; never invent a publication hour.
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return datetime.fromisoformat(value).replace(tzinfo=SH).astimezone(UTC)
    return stamp(value)


def event_fits(value, start, end):
    if len(value) == 10:
        # An original calendar date does not establish the publisher's time zone.
        # Count it only when the whole possible date range lies inside the period.
        midnight = datetime.fromisoformat(value).replace(tzinfo=UTC)
        return start <= midnight - timedelta(hours=14) and midnight + timedelta(hours=36) <= end
    at = date_floor(value)
    return start <= at < end


def clean(value, limit=1200, empty=False):
    require(isinstance(value, str) and (empty or value.strip()) and len(value) <= limit, "invalid_public_text")
    require(not SECRET.search(value), "sensitive_content_rejected")
    return value.strip()


def public_url(value):
    clean(value, 1800)
    try:
        u = urlsplit(value)
        require(u.scheme == "https" and u.hostname and "." in u.hostname and not u.username and not u.password and u.port in (None, 443), "non_public_url")
        host = u.hostname.lower()
        require(not host.endswith((".local", ".internal", ".localhost", ".test", ".invalid")) and host != "localhost", "non_public_url")
        try:
            require(ipaddress.ip_address(host).is_global, "non_public_url")
        except ValueError as exc:
            if str(exc) == "non_public_url":
                raise
        require(not any(k.lower() in BAD_QUERY for k in parse_qs(u.query)), "credential_url_rejected")
    except (TypeError, ValueError) as exc:
        raise ValueError("unsafe_public_url") from None
    return value


def canonical(url):
    u = urlsplit(public_url(url))
    return urlunsplit((u.scheme, u.netloc.lower(), u.path.rstrip("/"), u.query, u.fragment))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else deepcopy(default)


def periods(kind, as_of):
    if kind == "daily":
        return as_of - timedelta(hours=24), as_of
    monday = as_of.astimezone(SH).replace(hour=0, minute=0, second=0, microsecond=0)
    monday -= timedelta(days=monday.weekday())
    return (monday - timedelta(days=7)).astimezone(UTC), monday.astimezone(UTC)


def prepare(data_dir, kind, now=None):
    now = now or datetime.now(UTC)
    hub = load(data_dir / "topics.json")
    as_of = stamp(hub["generated_at"])
    require(timedelta(0) <= now - as_of <= timedelta(hours=36), "news_snapshot_stale_or_future")
    start, end = periods(kind, as_of)
    baseline = load(ROOT / "config/trend_baseline.json")
    previous = load(data_dir / LATEST, {})
    companies = {}
    for slug in IDS:
        data = load(data_dir / "topics" / f"{slug}.json", {"items": []})
        rows, seen = [], set()
        # Read the whole company pool, not the limited daily top-20 pool.
        for row in data.get("items", []):
            try:
                url = canonical(row.get("url"))
                at = stamp(row["published_at"]) if row.get("published_at") else None
                title = clean(row.get("title_original") or row.get("title") or "", 1500)
                if url in seen or (at and not as_of - timedelta(days=30) <= at <= as_of):
                    continue
                seen.add(url)
                rows.append({"url": url, "title": title, "reported_at_unverified": iso(at) if at else None,
                             "summary_unverified": clean(row.get("summary") or "", 2200, empty=True),
                             "source": clean(row.get("source") or row.get("source_name") or "未知", 120),
                             "editorial_focus": row.get("editorial_focus", "general")})
            except (ValueError, KeyError, TypeError):
                continue
        rows.sort(key=lambda r: (r["editorial_focus"] == "product", r["reported_at_unverified"] or ""), reverse=True)
        # Reserve both recent and older context; never treat this cap as full coverage.
        fresh = [r for r in rows if r["reported_at_unverified"] and start <= stamp(r["reported_at_unverified"]) < end]
        selected = list({r["url"]: r for r in fresh[:16] + rows[:12]}.values())
        companies[slug] = {"baseline": baseline["companies"][slug], "previous": previous.get("companies", {}).get(slug),
                           "candidate_count": len(rows), "candidates_truncated": len(selected) < len(rows), "candidates": selected}
    bundle = {"schema": "radar_trend_input_v1", "kind": kind, "period_start": iso(start), "period_end": iso(end),
              "source_snapshot_at": iso(as_of), "previous_report_id": previous.get("report_id"),
              "previous_overview": previous.get("overview"), "companies": companies,
              "known_daily_events": daily_event_index(data_dir, as_of),
              "history_context": history_module().history_context(data_dir),
              "evolution_contract": {"types": history_module().TYPES, "directions": history_module().DIRECTIONS, "required": True,
                                     "strengthening_policy": history_module().STRENGTHENING_POLICY},
              "warning": "候选时间、标题、摘要未经本轮原文核验；原文失败是覆盖缺口。既有判断不是新证据；同一事件多家报道只算一次。"}
    bundle["input_id"] = digest(bundle)
    return bundle


def daily_event_index(data_dir, as_of):
    """Stable event ids and dated original refs across overlapping daily windows."""
    result = {slug: {} for slug in IDS}
    for path in sorted((data_dir / "trends" / "daily").glob("????-??-??.json")):
        archived = load(path)
        if stamp(archived["period_end"]) < as_of - timedelta(days=35):
            continue
        raw = {k: v for k, v in archived.items() if k != "report_id"}
        checked = validate_report(raw, now=stamp(raw["generated_at"]))
        require(checked["report_id"] == archived.get("report_id"), "invalid_daily_archive_hash")
        evidence = {e["id"]: e for e in archived["evidence"]}
        for slug in IDS:
            for event in archived["companies"][slug]["events"]:
                refs = [{"url": canonical(evidence[k]["url"]), "event_at": evidence[k]["event_at"]}
                        for k in event["evidence_ids"] if evidence[k]["event_at"]]
                previous = result[slug].get(event["event_id"], {})
                merged_refs = {digest(r): r for r in previous.get("dated_refs", []) + refs}
                result[slug][event["event_id"]] = {"headline": event["headline"], "first_report_end": previous.get("first_report_end", archived["period_end"]), "dated_refs": list(merged_refs.values())}
    return result


def validate_report(raw, *, now=None):
    now = now or datetime.now(UTC)
    keys(raw, "schema kind period_start period_end source_snapshot_at generated_at input_id previous_report_id companies evidence overview" + (" evolution" if "evolution" in raw else ""), "invalid_report_fields")
    require(raw["schema"] == REPORT_SCHEMA and raw["kind"] in {"daily", "weekly"}, "invalid_report_schema")
    start, end, source, generated = (stamp(raw[k]) for k in ("period_start", "period_end", "source_snapshot_at", "generated_at"))
    require(start < end <= source <= generated <= now + timedelta(minutes=5), "invalid_report_window")
    require(now - source <= timedelta(hours=36), "stale_report_snapshot")
    require((start, end) == periods(raw["kind"], source), "invalid_period_bounds")
    require(isinstance(raw["input_id"], str) and re.fullmatch(r"[a-f0-9]{64}", raw["input_id"]), "invalid_input_id")
    require(raw["previous_report_id"] is None or re.fullmatch(r"[a-f0-9]{64}", str(raw["previous_report_id"])), "invalid_parent_id")
    evidence = {}
    require(isinstance(raw["evidence"], list) and len(raw["evidence"]) <= 100, "invalid_evidence")
    for item in raw["evidence"]:
        keys(item, "id url title source published_at event_at verified_at company_ids level date_basis note", "invalid_evidence_fields")
        key = clean(item["id"], 80)
        require(re.fullmatch(r"[a-z0-9_-]+", key) and key not in evidence, "duplicate_evidence")
        public_url(item["url"])
        for k, limit in (("title", 400), ("source", 120), ("note", 600)):
            clean(item[k], limit, empty=k == "note")
        require(item["level"] in {"official", "media"} and item["date_basis"] in {"original_page", "undated_document"}, "invalid_evidence_level")
        require(isinstance(item["company_ids"], list) and item["company_ids"] and set(item["company_ids"]) <= set(IDS), "invalid_evidence_companies")
        require(start - timedelta(days=40) <= stamp(item["verified_at"]) <= generated, "invalid_verification_time")
        if item["published_at"] is not None:
            require(date_floor(item["published_at"]) <= source, "future_publication")
        require((item["published_at"] is None) == (item["date_basis"] == "undated_document"), "missing_original_date_basis")
        if item["event_at"] is not None:
            require(item["published_at"] is not None and date_floor(item["event_at"]) <= date_floor(item["published_at"]), "unverified_event_date")
        evidence[key] = item

    def card(value, company=None):
        keys(value, "headline summary evidence_ids", "invalid_card_fields")
        clean(value["headline"], 100)
        clean(value["summary"], 1400)
        refs = value["evidence_ids"]
        require(isinstance(refs, list) and 0 < len(refs) <= 15 and len(refs) == len(set(refs)) and set(refs) <= evidence.keys(), "missing_evidence_reference")
        if company:
            require(all(company in evidence[k]["company_ids"] for k in refs), "cross_company_citation")
        require(not re.search(r"^(?:要|应当|需要|如何|建议|重点看|关键在于)", value["headline"]), "method_is_not_a_judgment")

    companies = raw["companies"]
    require(isinstance(companies, dict) and set(companies) == set(IDS), "must_cover_eight_companies")
    for slug, company in companies.items():
        keys(company, "state reason judgment changes digest events", "invalid_company_fields")
        require(company["state"] in {"updated", "unchanged", "insufficient"}, "invalid_company_state")
        clean(company["reason"], 600)
        for field in ("judgment", "digest"):
            if company[field] is not None:
                card(company[field], slug)
        require(company["changes"] is None or isinstance(company["changes"], list) and len(company["changes"]) <= 5, "invalid_changes")
        for value in company["changes"] or []:
            card(value, slug)
        require(isinstance(company["events"], list) and len(company["events"]) <= 12, "invalid_events")
        event_ids = set()
        for event in company["events"]:
            keys(event, "event_id status headline summary evidence_ids", "invalid_event_fields")
            require(re.fullmatch(r"[a-z0-9_-]{3,100}", str(event["event_id"])) and event["event_id"] not in event_ids, "duplicate_event")
            event_ids.add(event["event_id"])
            require(event["status"] in {"new", "continuation", "supplement", "correction"}, "invalid_event_status")
            card({k: event[k] for k in ("headline", "summary", "evidence_ids")}, slug)
            if event["status"] == "new":
                require(any(evidence[k]["event_at"] and event_fits(evidence[k]["event_at"], start, end) for k in event["evidence_ids"]), "old_or_undated_event_marked_new")
        if company["state"] != "updated":
            require(company["judgment"] is None and company["changes"] is None, "unchanged_company_cannot_rewrite")
        if company["state"] == "insufficient":
            require(company["digest"] is None and not company["events"], "insufficient_company_cannot_assert")
    if raw["overview"] is not None:
        overview = raw["overview"]
        keys(overview, "reason lead themes", "invalid_overview_fields")
        clean(overview["reason"], 600)
        clean(overview["lead"], 350)
        require(isinstance(overview["themes"], list) and 1 <= len(overview["themes"]) <= 4, "invalid_overview_themes")
        for theme in overview["themes"]:
            keys(theme, "headline summary evidence_ids company_ids", "invalid_theme_fields")
            card({k: theme[k] for k in ("headline", "summary", "evidence_ids")})
            require(isinstance(theme["company_ids"], list) and len(set(theme["company_ids"])) >= 2 and set(theme["company_ids"]) <= set(IDS), "single_company_is_not_cross_company_trend")
            supported = set().union(*(set(evidence[k]["company_ids"]) for k in theme["evidence_ids"]))
            require(set(theme["company_ids"]) <= supported, "unsupported_overview_company")
            require(any(c in DOMESTIC for c in supported) and any(c not in DOMESTIC for c in supported), "overview_needs_domestic_and_overseas_evidence")
    if "evolution" in raw:
        history_module().validate_evolution(raw)
    result = deepcopy(raw)
    result["report_id"] = digest(raw)
    return result


def validate_latest(value):
    keys(value, "schema report_id updated_at source_snapshot_at companies overview daily weekly", "invalid_latest_fields")
    require(value["schema"] == LATEST_SCHEMA and set(value["companies"]) == set(IDS), "invalid_latest_schema")
    # Public persisted values must also pass secret checks on reload/publish.
    clean(json.dumps(value, ensure_ascii=False), 500_000)
    for slug, row in value["companies"].items():
        keys(row, "judgment changes daily weekly last_checked_at state reason", "invalid_latest_company")
        clean(row["reason"], 600)
        stamp(row["last_checked_at"])
        require(row["state"] in {"updated", "unchanged", "insufficient"}, "invalid_latest_state")
        for field in ("judgment", "changes", "daily", "weekly"):
            wrapper = row[field]
            if wrapper is None:
                continue
            keys(wrapper, "generated_at source_snapshot_at period_start period_end content evidence", "invalid_persisted_wrapper")
            check_wrapper(wrapper, company=slug, field=field)
    if value["overview"] is not None:
        keys(value["overview"], "generated_at source_snapshot_at kind period_start period_end content evidence", "invalid_persisted_overview")
        check_wrapper(value["overview"])
    for k in ("daily", "weekly"):
        if value[k]:
            raw = {a: b for a, b in value[k].items() if a != "report_id"}
            # Historic reports retain original timestamps; validate in their own time.
            checked = validate_report(raw, now=stamp(raw["generated_at"]))
            require(checked["report_id"] == value[k]["report_id"], "invalid_persisted_report_hash")
    return value


def check_wrapper(wrapper, company=None, field=None):
    """Revalidate persisted prose too; never trust arbitrary local latest fields."""
    generated = stamp(wrapper["generated_at"])
    kind = wrapper.get("kind") or ("weekly" if stamp(wrapper["period_end"]) - stamp(wrapper["period_start"]) == timedelta(days=7) else "daily")
    rows = {slug: {"state": "insufficient", "reason": "未核验", "judgment": None, "changes": None, "digest": None, "events": []} for slug in IDS}
    if company:
        rows[company]["state"] = "updated"
        rows[company][field if field in {"judgment", "changes"} else "digest"] = wrapper["content"]
    raw = {"schema": REPORT_SCHEMA, "kind": kind, "period_start": wrapper["period_start"], "period_end": wrapper["period_end"],
           "source_snapshot_at": wrapper["source_snapshot_at"], "generated_at": wrapper["generated_at"], "input_id": "0" * 64,
           "previous_report_id": None, "companies": rows, "evidence": wrapper["evidence"], "overview": None if company else wrapper["content"]}
    validate_report(raw, now=generated)


def merge_report(previous, report):
    require(report["previous_report_id"] == (previous or {}).get("report_id"), "remote_parent_changed_regenerate_report")
    if previous:
        validate_latest(previous)
        require(stamp(report["source_snapshot_at"]) >= stamp(previous["source_snapshot_at"]), "snapshot_regression")
    state = deepcopy(previous) if previous else {"schema": LATEST_SCHEMA, "companies": {}, "overview": None, "daily": None, "weekly": None}
    for slug in IDS:
        row = report["companies"][slug]
        target = state["companies"].setdefault(slug, {"judgment": None, "changes": None, "daily": None, "weekly": None})
        def dated(value):
            return {"generated_at": report["generated_at"], "source_snapshot_at": report["source_snapshot_at"],
                    "period_start": report["period_start"], "period_end": report["period_end"], "content": value,
                    "evidence": [e for e in report["evidence"] if e["id"] in set().union(*(set(c["evidence_ids"]) for c in (value if isinstance(value, list) else [value])))]}
        if row["judgment"]:
            target["judgment"] = dated(row["judgment"])
        if row["changes"] is not None:
            require(row["changes"], "empty_changes_would_erase_history")
            target["changes"] = dated(row["changes"])
        # A checked day with no evidence must not be displayed as a fresh old digest.
        target[report["kind"]] = dated(row["digest"]) if row["digest"] else None
        target.update(last_checked_at=report["generated_at"], state=row["state"], reason=row["reason"])
    if report["overview"]:
        refs = {k for t in report["overview"]["themes"] for k in t["evidence_ids"]}
        state["overview"] = {"generated_at": report["generated_at"], "source_snapshot_at": report["source_snapshot_at"], "kind": report["kind"],
                             "period_start": report["period_start"], "period_end": report["period_end"], "content": report["overview"],
                             "evidence": [e for e in report["evidence"] if e["id"] in refs]}
    state[report["kind"]] = report
    state.update(report_id=report["report_id"], updated_at=report["generated_at"], source_snapshot_at=report["source_snapshot_at"])
    return state


def archive_path(report):
    end = stamp(report["period_end"]).astimezone(SH)
    key = end.date().isoformat() if report["kind"] == "daily" else "%04d-W%02d" % (end - timedelta(days=1)).isocalendar()[:2]
    return Path("trends") / report["kind"] / f"{key}.json"


def bind_input(raw, bundle):
    require(isinstance(bundle, dict) and bundle.get("schema") == "radar_trend_input_v1", "invalid_input_bundle")
    require(bundle.get("input_id") == digest({k: v for k, v in bundle.items() if k != "input_id"}), "input_bundle_tampered")
    if bundle.get("evolution_contract", {}).get("required"):
        require("evolution" in raw, "evolution_required_for_prepared_input")
    if bundle.get("evolution_contract", {}).get("strengthening_policy", {}).get("required"):
        history_module().require_strengthening_reviews(raw)
    for key in ("input_id", "kind", "period_start", "period_end", "source_snapshot_at", "previous_report_id"):
        require(raw.get(key) == bundle.get(key), "report_input_mismatch")


def write_report(data_dir, raw, *, now=None):
    report = validate_report(raw, now=now)
    path = data_dir / archive_path(report)
    previous = load(data_dir / LATEST)
    if previous and previous.get("report_id") == report["report_id"]:
        return {"status": "unchanged", "report_id": report["report_id"]}
    existing = load(path)
    require(existing is None or existing == report, "issue_already_published")
    if report["kind"] == "daily":
        known = daily_event_index(data_dir, stamp(report["source_snapshot_at"]))
        evidence = {e["id"]: e for e in report["evidence"]}
        start, end = stamp(report["period_start"]), stamp(report["period_end"])
        for slug in IDS:
            dated_refs = {(r["url"], r["event_at"]) for e in known[slug].values() for r in e["dated_refs"]}
            for event in report["companies"][slug]["events"]:
                if event["status"] != "new":
                    continue
                current_refs = {(canonical(evidence[k]["url"]), evidence[k]["event_at"]) for k in event["evidence_ids"]
                                if evidence[k]["event_at"] and event_fits(evidence[k]["event_at"], start, end)}
                require(event["event_id"] not in known[slug] and not current_refs <= dated_refs, "already_reported_event_cannot_be_new")
    merged = merge_report(previous, report)
    validate_latest(merged)
    history = history_module().build_history(data_dir, extra_report=report)
    # Validate everything before mutation; latest is the commit point.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    temporary = (data_dir / LATEST).with_suffix(".tmp")
    temporary.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n")
    history_module().write_history(data_dir, history)
    temporary.replace(data_dir / LATEST)
    return {"status": "written", "report_id": report["report_id"], "archive": str(path)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("prepare", "apply", "check"))
    p.add_argument("--data-dir", type=Path, default=ROOT / "data")
    p.add_argument("--kind", choices=("daily", "weekly"), default="daily")
    p.add_argument("--output", type=Path)
    p.add_argument("--report", type=Path)
    p.add_argument("--input", type=Path)
    args = p.parse_args()
    if args.command == "prepare":
        require(args.output is not None, "output_required")
        result = prepare(args.data_dir, args.kind)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({k: result[k] for k in ("input_id", "kind", "source_snapshot_at", "previous_report_id")}, ensure_ascii=False))
    elif args.command == "check":
        validate_latest(load(args.data_dir / LATEST))
        print("Public trend snapshot validated")
    else:
        require(args.report is not None and args.input is not None, "report_and_input_required")
        raw = load(args.report)
        bind_input(raw, load(args.input))
        print(json.dumps(write_report(args.data_dir, raw), ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError):
        # Arbitrary source text/exception messages must not enter CI logs.
        raise SystemExit("trend_report_validation_failed; previous published report retained") from None
