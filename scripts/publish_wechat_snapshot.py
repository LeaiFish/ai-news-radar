#!/usr/bin/env python3
"""Publish only verified public WeChat metadata from an isolated checkout."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import tempfile

try:
    from scripts.wechat_sources import SCHEMA, eligible_rows, normalized_name, published_datetime, targets, canonical_url, canonical_evidence_url
except ModuleNotFoundError:
    from wechat_sources import SCHEMA, eligible_rows, normalized_name, published_datetime, targets, canonical_url, canonical_evidence_url

REPOSITORY = "git@github.com:LeaiFish/ai-news-radar.git"
SNAPSHOT = Path("data/bridge/wechat-accounts.json")
ROOT = Path(__file__).resolve().parents[1]
STATS = ("at", "ok", "searched_accounts", "candidates", "verified", "added", "covered_companies", "covered_accounts")
# Exact codes only: never copy upstream messages, account identifiers or headers.
PUBLIC_DISCOVERY_ERRORS = frozenset({
    "discovery_failed", "wemprss_stopped_after_auth_or_quota_error", "wemprss_worker_failed",
    *(f"wemprss_api_{code}" for code in (-2010, -2012, -2014, -2041, 401, 403, 429, 499)),
    *(f"search_http_{code}" for code in (401, 403, 429, 500, 502, 503, 504)),
    "search_backend_unavailable", "search_rate_limited", "search_provider_error", "search_rpc_error",
    "supplemental_discovery_failed", "pilot_discovery_failed",
})


def public_snapshot(payload, now):
    """Rebuild an allowlisted payload; never publish arbitrary local JSON fields."""
    rows = list(eligible_rows(payload, now))
    raw = payload["accounts"]
    if any(company not in targets() or not isinstance(items, list) for company, items in raw.items()):
        raise ValueError("invalid_snapshot_accounts")
    if len(rows) != sum(len(items) for items in raw.values()):
        raise ValueError("snapshot_contains_unverified_or_invalid_articles")
    accounts = {company: [] for company in targets()}
    for company, row in rows:
        if row["published"] is not None and not published_datetime(row["published"]):
            raise ValueError("invalid_publication_date")
        row["evidence_url"] = canonical_evidence_url(row["evidence_url"], row["url"])
        accounts[company].append(row)
    run = payload.get("last_run")
    if not isinstance(run, dict) or not published_datetime(run.get("at")):
        raise ValueError("missing_discovery_timestamp")
    stats = {}
    for key in STATS:
        value = run.get(key)
        if key == "at":
            if published_datetime(value) > now:
                raise ValueError("future_discovery_timestamp")
        elif key == "ok":
            if type(value) is not bool:
                raise ValueError("invalid_discovery_status")
        elif type(value) is not int or value < 0:
            raise ValueError("invalid_discovery_count")
        stats[key] = value
    errors = run.get("errors", [])
    if not isinstance(errors, list):
        raise ValueError("invalid_discovery_errors")
    # Known codes aid diagnosis; arbitrary provider text stays local.
    stats["errors"] = [{"error": error.get("error") if isinstance(error, dict)
                        and isinstance(error.get("error"), str)
                        and error["error"] in PUBLIC_DISCOVERY_ERRORS else "discovery_failed"}
                       for error in errors]
    if isinstance(run.get("collector"), str) and run["collector"] in {"wemprss", "public_search"}:
        stats["collector"] = run["collector"]
    for key in ('recent_24h', 'rejected'):
        if type(run.get(key)) is int and run[key] >= 0:
            stats[key] = run[key]
    if run.get('collection_state') in {'complete', 'partial', 'failed'}:
        stats['collection_state'] = run['collection_state']
    if isinstance(run.get('pilot_recent_7d'), dict):
        stats['pilot_recent_7d'] = {k: v for k, v in run['pilot_recent_7d'].items()
                                    if k in {'千问APP', '通义实验室'} and type(v) is int and v >= 0}
    updated = payload.get("updated")
    if not isinstance(updated, str) or not published_datetime(updated):
        raise ValueError("invalid_snapshot_date")
    return {"schema": SCHEMA, "updated": updated, "accounts": accounts, "last_run": stats}


def merged_snapshot(incoming, remote, now):
    incoming = public_snapshot(incoming, now)
    if remote is None:
        return incoming
    remote = public_snapshot(remote, now)
    if published_datetime(incoming["last_run"]["at"]) < published_datetime(remote["last_run"]["at"]):
        raise ValueError("remote_snapshot_is_newer_rerun_collection")
    accounts = {company: {} for company in targets()}
    for snapshot in (remote, incoming):
        for company, rows in snapshot["accounts"].items():
            for row in rows:
                previous = accounts[company].get(row["url"])
                if previous and published_datetime(previous["verified_at"]) > published_datetime(row["verified_at"]):
                    continue
                if previous and row["published"] is None:
                    row = row | {"published": previous["published"]}
                accounts[company][row["url"]] = row
    for company, indexed in accounts.items():
        grouped = {}
        for row in indexed.values():
            grouped.setdefault(normalized_name(row["account_name"]), []).append(row)
        incoming["accounts"][company] = [row for name in sorted(grouped)
            for row in sorted(grouped[name], key=lambda r: (r["published"] or "", r["verified_at"]), reverse=True)[:20]]
    # Counts must describe the merged archive, including remote-only history.
    retained = [(company, row) for company, rows in incoming["accounts"].items() for row in rows]
    remote_keys = {(company, row["url"]) for company, rows in remote["accounts"].items() for row in rows}
    run = incoming["last_run"]
    run["covered_companies"] = sum(bool(rows) for rows in incoming["accounts"].values())
    run["covered_accounts"] = len({normalized_name(row["account_name"]) for _, row in retained})
    run["added"] = (remote["last_run"]["added"] if run["at"] == remote["last_run"]["at"] else
        sum((company, row["url"]) not in remote_keys for company, row in retained))
    if "recent_24h" in run:
        collected_at = published_datetime(run["at"])
        run["recent_24h"] = sum(bool(published_datetime(row["published"])) and
            collected_at - timedelta(hours=24) <= published_datetime(row["published"]) <= collected_at for _, row in retained)
    return incoming


def git(*args, cwd=None, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)


def publish(payload, *, repository=REPOSITORY):
    now = datetime.now(timezone.utc)
    incoming = public_snapshot(payload, now)  # Validate before any Git/network operations.
    with tempfile.TemporaryDirectory(prefix="radar-wechat-publish-") as directory:
        checkout = Path(directory) / "repo"
        git("clone", "--quiet", "--depth", "1", "--branch", "master", repository, str(checkout))
        git("config", "user.name", "Radar WeChat Sync", cwd=checkout)
        git("config", "user.email", "radar-sync@users.noreply.github.com", cwd=checkout)
        for attempt in range(3):
            if attempt:
                git("fetch", "origin", "master", cwd=checkout)
                git("reset", "--hard", "origin/master", cwd=checkout)
            destination = checkout / SNAPSHOT
            remote = json.loads(destination.read_text()) if destination.exists() else None
            merged = merged_snapshot(incoming, remote, now)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            git("add", "--", str(SNAPSHOT), cwd=checkout)
            paths = git("diff", "--cached", "--name-only", cwd=checkout).stdout.splitlines()
            if not paths:
                return {"status": "unchanged", "commit": git("rev-parse", "HEAD", cwd=checkout).stdout.strip()}
            if paths != [str(SNAPSHOT)]:
                raise ValueError("unexpected_staged_paths")
            git("commit", "-m", "chore: sync verified WeChat metadata", cwd=checkout)
            result = git("push", "origin", "HEAD:master", cwd=checkout, check=False)
            if result.returncode == 0:
                return {"status": "pushed", "commit": git("rev-parse", "HEAD", cwd=checkout).stdout.strip()}
        raise RuntimeError("snapshot_push_failed_after_3_attempts")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=ROOT / SNAPSHOT)
    args = parser.parse_args()
    try:
        print(json.dumps(publish(json.loads(args.snapshot.read_text(encoding="utf-8")))) )
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        # Git output may include local credential helper details; do not echo it.
        print(json.dumps({"status": "failed", "error": str(exc) if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
