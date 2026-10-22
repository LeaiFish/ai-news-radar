#!/usr/bin/env python3
"""Opt-in private we-mp-rss reader; emit verified public metadata only."""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.wechat_sources import (DEFAULT_OUTPUT, canonical_evidence_url,
    normalized_name, parse_article, sync, targets)

CONFIG = ROOT / "config/wemprss_sources.json"
STOP_CODES = {-2010, -2012, -2014, -2041, 401, 403, 429, 499}


def subscriptions(path):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))["subscriptions"]
    allowed = targets()
    seen = set()
    for row in rows:
        company, name, book = (row.get(k) for k in ("company_id", "account_name", "book_id"))
        if (company not in allowed or name not in allowed[company]
                or not re.fullmatch(r"MP_WXS_\d+", str(book or "")) or book in seen):
            raise ValueError("invalid_wemprss_subscription")
        seen.add(book)
    return rows


def collect(reader, jobs, now, delay=time.sleep):
    """Cover is a discovery hint, never a publication timestamp or full list."""
    searches, candidates, rows = [], [], []
    stopped = False
    for index, job in enumerate(jobs):
        name, company, book = (job[k] for k in ("account_name", "company_id", "book_id"))
        search = {"account_name": name, "ok": False}
        searches.append(search)
        if stopped:
            search["error"] = "wemprss_stopped_after_auth_or_quota_error"
            continue
        if index:
            delay(2)
        try:
            cover = reader._get_mp_cover(book)
            actual = cover["name"]
            if normalized_name(actual) not in {normalized_name(n) for n in targets()[company]}:
                raise ValueError("account_mismatch")
            review = cover["reviewId"]
            prefix = book + "_"
            if not review.startswith(prefix):
                raise ValueError("publisher_id_mismatch")
            url = "https://mp.weixin.qq.com/s/" + review[len(prefix):].replace("~", "_")
            evidence = canonical_evidence_url("https://weread.qq.com/web/mp/content?" + urlencode({"reviewId": review}), url)
            response = reader._weread_http_get("https://weread.qq.com/web/mp/content",
                params={"reviewId": review}, timeout=(5, 20))
            response.raise_for_status()
            response.encoding = "utf-8"
            try:
                api = response.json()
            except ValueError:
                api = None
            if isinstance(api, dict) and (api.get("errCode") or api.get("errcode")):
                code = int(api.get("errCode") or api["errcode"])
                stopped = code in STOP_CODES
                search["error"] = f"wemprss_api_{code}"
                continue
            row = parse_article(response.text, actual, url, now)
            row.update(company_id=company, evidence_url=evidence)
            rows.append(row)
            candidates.append({"company_id": company, "account_name": name, "url": url})
            search["ok"] = True
        except Exception as exc:
            code = getattr(exc, "code", None)
            status = getattr(getattr(exc, "response", None), "status_code", None)
            stopped = code in STOP_CODES or status in STOP_CODES
            # Never serialize upstream exception messages, cookies or response bodies.
            search["error"] = f"wemprss_api_{code}" if isinstance(code, int) else (
                f"wemprss_http_{status}" if isinstance(status, int) else "wemprss_" + type(exc).__name__)
    return {"searches": searches, "candidates": candidates, "rows": rows}


def merge_result(result, existing, jobs, now):
    indexed = {(r["company_id"], r["url"]): r for r in result["rows"]}
    def verified(candidate, _now):
        return dict(indexed[(candidate["company_id"], candidate["url"])])
    snapshot = sync(result, existing, now, verifier=verified,
                    expected_accounts=[r["account_name"] for r in jobs])
    run = snapshot["last_run"]
    run["collector"] = "wemprss"
    run["collection_state"] = "complete" if run["ok"] else ("partial" if run["verified"] else "failed")
    return snapshot


def worker(jobs):
    # Upstream resolves private credentials relative to its cwd. Its diagnostics
    # may contain authentication data, so discard them rather than retaining logs.
    logging.disable(logging.CRITICAL)
    with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        sys.path.insert(0, str(Path.cwd()))
        from core.wx.model.weread_mp import MpsWereadMP
        reader = MpsWereadMP()
        reader._load_weread_auth()
        result = collect(reader, jobs, datetime.now(timezone.utc))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=os.environ.get("WEMPRSS_SOURCE_DIR"))
    parser.add_argument("--subscriptions", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    jobs = subscriptions(args.subscriptions)
    if args.worker:
        print(json.dumps(worker(jobs), ensure_ascii=False))
        return 0
    if not args.source_dir:
        parser.error("--source-dir or WEMPRSS_SOURCE_DIR is required")
    source = args.source_dir.resolve()
    if source == ROOT or ROOT in source.parents:
        parser.error("private we-mp-rss runtime must be outside this repository")
    python = source / ".venv/bin/python"
    try:
        process = subprocess.run([str(python), str(Path(__file__).resolve()), "--worker",
            "--subscriptions", str(args.subscriptions.resolve())], cwd=source,
            capture_output=True, text=True, timeout=360, check=True)
        result = json.loads(process.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        result = {"searches": [{"account_name": r["account_name"], "ok": False,
            "error": "wemprss_worker_failed"} for r in jobs], "candidates": [], "rows": []}
    now = datetime.now(timezone.utc)
    existing = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else None
    snapshot = merge_result(result, existing, jobs, now)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.output.parent, delete=False) as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(args.output)
    print(json.dumps(snapshot["last_run"], ensure_ascii=False))
    return 0 if snapshot["last_run"]["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
