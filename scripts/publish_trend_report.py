#!/usr/bin/env python3
"""Publish a validated public report; never stage the caller's working tree."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request

try:
    from scripts.trend_reports import LATEST, archive_path, bind_input, load, require, validate_report, write_report
except ModuleNotFoundError:
    from trend_reports import LATEST, archive_path, bind_input, load, require, validate_report, write_report

REPOSITORY = "git@github.com:LeaiFish/ai-news-radar.git"
PUBLIC = "https://leaifish.github.io/ai-news-radar/data/trends/latest.json"


def git(*args, cwd=None, check=True):
    result = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, timeout=180)
    if check and result.returncode:
        raise RuntimeError("trend_git_operation_failed")
    return result


def publish(raw, bundle, *, repository=REPOSITORY):
    bind_input(raw, bundle)
    report = validate_report(raw)
    allowed = {str(Path("data") / LATEST), str(Path("data") / archive_path(report))}
    with tempfile.TemporaryDirectory(prefix="radar-trend-publish-") as folder:
        checkout = Path(folder) / "repo"
        git("clone", "--quiet", "--depth", "1", "--branch", "master", repository, str(checkout))
        git("config", "user.name", "Radar Editorial Sync", cwd=checkout)
        git("config", "user.email", "radar-editorial@users.noreply.github.com", cwd=checkout)
        for attempt in range(3):
            if attempt:
                git("fetch", "origin", "master", cwd=checkout)
                git("reset", "--hard", "origin/master", cwd=checkout)
            result = write_report(checkout / "data", raw)
            if result["status"] == "unchanged":
                return {**result, "commit": git("rev-parse", "HEAD", cwd=checkout).stdout.strip()}
            git("add", "--", *sorted(allowed), cwd=checkout)
            staged = set(git("diff", "--cached", "--name-only", cwd=checkout).stdout.splitlines())
            require(staged <= allowed and staged, "unexpected_staged_paths")
            git("commit", "-m", f"chore: publish {raw['kind']} application trends", cwd=checkout)
            if git("push", "origin", "HEAD:master", cwd=checkout, check=False).returncode == 0:
                return {**result, "status": "pushed", "commit": git("rev-parse", "HEAD", cwd=checkout).stdout.strip()}
        raise RuntimeError("trend_push_failed")


def verify(report_id, timeout=1800):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        try:
            request = urllib.request.Request(PUBLIC + "?report=" + report_id, headers={"Cache-Control": "no-cache"})
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read(600_000))
            if payload.get("report_id") == report_id:
                return True
        except (OSError, ValueError):
            pass
        time.sleep(min(20, max(0, until - time.monotonic())))
    return False


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--verify", action="store_true")
    args = p.parse_args()
    result = publish(load(args.report), load(args.input))
    # Output only safe ids/status. Never expose Git/HTTP raw diagnostics.
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if args.verify:
        rebuild = subprocess.run(["gh", "api", "--method", "POST", "repos/LeaiFish/ai-news-radar/pages/builds"], capture_output=True, timeout=40)
        if rebuild.returncode:
            active = subprocess.run(["gh", "api", "repos/LeaiFish/ai-news-radar/pages/builds/latest", "--jq", ".status"], capture_output=True, text=True, timeout=40)
            require(active.returncode == 0 and active.stdout.strip() in {"queued", "building", "built"}, "pages_build_request_failed")
        require(verify(result["report_id"]), "pages_report_verification_timeout")
        print(json.dumps({"status": "deployed", "report_id": result["report_id"]}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        raise SystemExit("trend_publish_failed; publication not confirmed") from None
