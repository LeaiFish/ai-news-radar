#!/usr/bin/env python3
"""Verify agent-discovered public WeChat URLs; keep credentials and search off-repo."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import html
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import parse_qs, urlencode, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/wechat_sources.json"
DEFAULT_OUTPUT = ROOT / "data/bridge/wechat-accounts.json"
SCHEMA = "wechat_accounts_v1"
UTC = timezone.utc
SHANGHAI = ZoneInfo("Asia/Shanghai")
MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"


def targets():
    return json.loads(CONFIG.read_text(encoding="utf-8"))["companies"]


def normalized_name(value):
    # Spacing/case are cosmetic. Do not fuzzy-match other accounts or media reprints.
    return re.sub(r"\s+", "", str(value or "")).casefold()


def canonical_url(value):
    parsed = urlparse(str(value or ""))
    if parsed.scheme not in {"http", "https"} or parsed.netloc != "mp.weixin.qq.com":
        raise ValueError("not_a_public_wechat_article")
    if re.fullmatch(r"/s/[A-Za-z0-9_-]+", parsed.path):
        return "https://mp.weixin.qq.com" + parsed.path
    if parsed.path == "/s":
        query = parse_qs(parsed.query)
        keys = ("__biz", "mid", "idx", "sn")
        if all(query.get(key) for key in keys):
            return "https://mp.weixin.qq.com/s?" + urlencode({key: query[key][0] for key in keys})
    raise ValueError("not_a_public_wechat_article")


def iso(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def published_datetime(value):
    """Require an absolute, complete date; date-only means Shanghai midnight."""
    if not value:
        return None
    text = str(value).strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?", text):
        return None
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return (result if result.tzinfo else result.replace(tzinfo=SHANGHAI)).astimezone(UTC)
    except ValueError:
        return None


def js_value(source, name):
    pattern = rf"\b{re.escape(name)}\s*[:=]\s*(['\"])((?:\\.|(?!\1).)*?)\1"
    match = re.search(pattern, source, re.S)
    if not match:
        return None
    value = match[2]
    value = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m[1], 16)), value)
    value = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m[1], 16)), value)
    return html.unescape(value.replace("\\'", "'").replace('\\"', '"').replace("\\/", "/"))


def parse_article(source, requested_account, url, now):
    soup = BeautifulSoup(source, "html.parser")
    nickname = soup.select_one("#js_name, .rich_media_meta_nickname")
    account = nickname.get_text(" ", strip=True) if nickname else js_value(source, "nick_name")
    title_node = soup.select_one("#activity-name, .rich_media_title")
    title = title_node.get_text(" ", strip=True) if title_node else None
    og = soup.select_one('meta[property="og:title"]')
    title = title or (og.get("content") if og else None) or js_value(source, "msg_title")
    if not account or not title:
        raise ValueError("blocked_or_missing_article_metadata")
    if normalized_name(account) != normalized_name(requested_account):
        raise ValueError("account_mismatch")
    date_node = soup.select_one("#publish_time, #post-date")
    published = published_datetime(date_node.get_text(strip=True) if date_node else None)
    if not published:
        published = published_datetime(js_value(source, "publish_time") or js_value(source, "create_time"))
    if not published:
        # ct is the original publication time, never an archive capture timestamp.
        ct = js_value(source, "ct")
        if not ct:
            match = re.search(r"\bct\s*[:=]\s*(\d{10})(?!\d)", source)
            ct = match[1] if match else None
        if ct and re.fullmatch(r"\d{10}", ct):
            published = datetime.fromtimestamp(int(ct), UTC)
    if published and published > now:
        raise ValueError("future_publication_date")
    return {"url": canonical_url(url), "title": title, "account_name": account,
            "published": iso(published) if published else None,
            "verified_at": iso(now), "account_verified": True}


def read_page(url):
    # Only follow redirects within the requested public host. Never use a login session.
    host = urlparse(url).netloc
    for _ in range(5):
        response = requests.get(url, headers={"User-Agent": MOBILE_UA}, timeout=20, allow_redirects=False)
        if response.is_redirect:
            from urllib.parse import urljoin
            redirected = urljoin(url, response.headers["Location"])
            if urlparse(redirected).netloc != host or urlparse(redirected).scheme != "https":
                raise ValueError("redirect_outside_public_source")
            url = redirected
            continue
        response.raise_for_status()
        response.encoding = "utf-8"
        return response.text
    raise ValueError("too_many_redirects")


def verify_candidate(candidate, now):
    company = candidate.get("company_id")
    account = candidate.get("account_name")
    if company not in targets() or account not in targets()[company]:
        raise ValueError("unknown_target_account")
    url = canonical_url(candidate.get("url"))
    try:
        row = parse_article(read_page(url), account, url, now)
        evidence = url
    except ValueError as exc:
        if str(exc) in {"account_mismatch", "future_publication_date"}:
            raise
        evidence = f"https://web.archive.org/web/{now.year}id_/{url}"
        row = parse_article(read_page(evidence), account, url, now)
    except requests.RequestException:
        evidence = f"https://web.archive.org/web/{now.year}id_/{url}"
        row = parse_article(read_page(evidence), account, url, now)
    row.update(company_id=company, evidence_url=evidence)
    return row


def eligible_rows(payload, now):
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA or not isinstance(payload.get("accounts"), dict):
        raise ValueError("invalid_wechat_accounts_schema")
    allowed = targets()
    for company, rows in payload["accounts"].items():
        if company not in allowed or not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict) or row.get("account_verified") is not True:
                continue
            if normalized_name(row.get("account_name")) not in {normalized_name(n) for n in allowed[company]}:
                continue
            try:
                url = canonical_url(row.get("url"))
            except ValueError:
                continue
            verified_at = published_datetime(row.get("verified_at"))
            evidence = row.get("evidence_url")
            archived = re.fullmatch(r"https://web\.archive\.org/web/\d+(?:id_)?/(https://mp\.weixin\.qq\.com/.*)", str(evidence or ""))
            try:
                evidence_target = canonical_url(archived[1] if archived else evidence)
            except ValueError:
                continue
            if not isinstance(row.get("title"), str) or not row["title"].strip() or not verified_at or verified_at > now or evidence_target != url:
                continue
            # Allowlist fields; no arbitrary candidate/page metadata enters Radar.
            yield company, {k: row.get(k) for k in (
                "title", "account_name", "published", "verified_at", "account_verified", "evidence_url"
            )} | {"url": url}


def sync(payload, existing, now, verifier=verify_candidate):
    allowed = targets()
    if not isinstance(payload, dict) or not isinstance(payload.get("searches"), list) or not isinstance(payload.get("candidates"), list):
        raise ValueError("invalid_wechat_candidates_schema")
    searches = payload.get("searches", [])
    errors = []
    target_names = {name for names in allowed.values() for name in names}
    successful_searches = {s.get("account_name") for s in searches if isinstance(s, dict) and s.get("ok") is True and isinstance(s.get("account_name"), str)} & target_names
    for name in sorted(target_names):
        if name not in successful_searches:
            errors.append({"account_name": name, "error": "search_failed_or_not_run"})
    rows_by_company = {company: {} for company in allowed}
    if existing:
        for company, row in eligible_rows(existing, now):
            rows_by_company[company][row["url"]] = row
    candidates, counts, seen = [], {}, set()
    for candidate in payload.get("candidates", []):
        if not isinstance(candidate, dict):
            errors.append({"error": "invalid_candidate"})
            continue
        name = candidate.get("account_name")
        if not isinstance(name, str) or candidate.get("company_id") not in allowed or name not in allowed[candidate["company_id"]]:
            errors.append({"error": "unknown_target_account"})
            continue
        try:
            url = canonical_url(candidate.get("url"))
        except ValueError:
            errors.append({"account_name": name, "error": "not_a_public_wechat_article"})
            continue
        key = (candidate.get("company_id"), name, url)
        if key in seen or counts.get(name, 0) >= 10:
            continue
        seen.add(key)
        counts[name] = counts.get(name, 0) + 1
        candidates.append(candidate | {"url": url})
    def checked(candidate):
        try:
            return candidate, verifier(candidate, now), None
        except (ValueError, requests.RequestException) as exc:
            # Only public URL and exception type; never echo response bodies or headers.
            reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                reason = f"http_{exc.response.status_code}"
            return candidate, None, reason
    added = verified = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for candidate, row, error in pool.map(checked, candidates):
            if error:
                errors.append({"account_name": candidate.get("account_name"), "url": candidate["url"], "error": error})
                continue
            company = row.pop("company_id")
            previous = rows_by_company[company].get(row["url"])
            added += int(previous is None)
            verified += 1
            if previous and not row["published"]:
                row["published"] = previous.get("published")
            rows_by_company[company][row["url"]] = row
    accounts = {}
    for company, rows in rows_by_company.items():
        # Cap each real account, not each company with several distinct accounts.
        by_name = {}
        for row in rows.values():
            by_name.setdefault(normalized_name(row["account_name"]), []).append(row)
        accounts[company] = []
        for rows in by_name.values():
            rows.sort(key=lambda r: (r.get("published") or "", r["verified_at"]), reverse=True)
            accounts[company].extend(rows[:20])
    covered_accounts = {normalized_name(row["account_name"]) for rows in accounts.values() for row in rows}
    return {"schema": SCHEMA, "updated": now.astimezone(SHANGHAI).date().isoformat(),
            "accounts": accounts, "last_run": {"at": iso(now), "ok": not errors,
                "searched_accounts": len(successful_searches), "candidates": len(candidates),
                "covered_companies": sum(bool(rows) for rows in accounts.values()),
                "covered_accounts": len(covered_accounts),
                "verified": verified, "added": added, "errors": errors}}


def load_radar_rows(path, now, window_hours=24):
    status = {"site_id": "wechat_bridge", "site_name": "官方公众号（补充）", "ok": True,
              "item_count": 0, "duration_ms": 0, "error": None, "skipped": False}
    path = Path(path)
    if not path.exists():
        return [], status | {"skipped": True, "skip_reason": "no_wechat_accounts_file"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows, seen = [], set()
        missing_date = 0
        for company, row in eligible_rows(payload, now):
            published = published_datetime(row["published"])
            missing_date += int(published is None)
            if not published or not now - timedelta(hours=window_hours) <= published <= now or row["url"] in seen:
                continue
            seen.add(row["url"])
            rows.append(row | {"company_id": company, "published_at": published})
        last_run = payload.get("last_run", {})
        if not isinstance(last_run, dict) or not isinstance(last_run.get("errors", []), list):
            raise ValueError("invalid_wechat_discovery_status")
        refreshed = published_datetime(last_run.get("at"))
        stale = not refreshed or refreshed > now or now - refreshed > timedelta(hours=30)
        status.update(item_count=len(rows), undated_count=missing_date, stale=stale,
                      discovery={key: last_run.get(key) for key in ("at", "ok", "searched_accounts", "candidates", "verified", "added", "covered_companies", "covered_accounts")},
                      failed_candidates=len(last_run.get("errors", [])), ok=last_run.get("ok") is True and not stale,
                      error="wechat_snapshot_stale" if stale else (None if last_run.get("ok") is True else "wechat_discovery_incomplete"))
        return rows, status
    except (ValueError, OSError, TypeError) as exc:
        return [], status | {"ok": False, "error": type(exc).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, help="Agent search results JSON; no search snippets trusted as metadata")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--list-targets", action="store_true")
    args = parser.parse_args()
    if args.list_targets:
        print(json.dumps(targets(), ensure_ascii=False, indent=2))
        return 0
    if not args.candidates:
        parser.error("--candidates is required")
    now = datetime.now(UTC)
    existing = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else None
    result = sync(json.loads(args.candidates.read_text(encoding="utf-8")), existing, now)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.output.parent, delete=False) as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(args.output)
    run = result["last_run"]
    print(json.dumps({"output": str(args.output), "covered_companies": sum(bool(rows) for rows in result["accounts"].values()), **run}, ensure_ascii=False))
    return 0 if run["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
