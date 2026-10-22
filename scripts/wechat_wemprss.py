#!/usr/bin/env python3
"""Opt-in private we-mp-rss reader; emit verified public metadata only."""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode, urlparse, urljoin

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.wechat_sources import (DEFAULT_OUTPUT, canonical_evidence_url,
    normalized_name, parse_article, sync, targets, canonical_url, identity, published_datetime, MOBILE_UA)

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


class CollectionError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__('wemprss_request_failed')


class SingleAccountReader:
    """Use the current authorized session once; never rotate accounts on quota errors."""
    def __init__(self, sdk, get=None):
        self.sdk, self.get = sdk, get or requests.get

    def _weread_http_get(self, url, *, params, include_ticket=False, timeout=(5, 15)):
        response = self.get(url, params=params,
            headers=self.sdk._weread_headers(include_ticket=include_ticket),
            timeout=timeout, allow_redirects=False)
        response.raise_for_status()
        return response

    def _json(self, path, params):
        response = self._weread_http_get('https://weread.qq.com' + path, params=params,
                                        include_ticket=path == '/web/mp/articles')
        data = response.json()
        if not isinstance(data, dict):
            raise CollectionError('invalid_response')
        code = data.get('errCode', data.get('errcode', 0))
        if code:
            raise CollectionError(code if isinstance(code, int) else 'invalid_response')
        return data

    def _get_mp_articles_page(self, book, offset=0):
        return self._json('/web/mp/articles', {'bookId': book, 'offset': offset})

    def _get_mp_cover(self, book):
        return self._json('/api/mp/cover', {'bookId': book})


def review_url(job, review):
    prefix = job['book_id'] + '_'
    if not isinstance(review, str) or not review.startswith(prefix):
        raise CollectionError('publisher_id_mismatch')
    return canonical_url('https://mp.weixin.qq.com/s/' + review[len(prefix):].replace('~', '_'))


def verified_html(source, job, url, evidence, now):
    row = parse_article(source, job['account_name'], url, now)
    known = identity(job['company_id'], job['account_name'])
    if known and row.get('account_id') and row['account_id'] != known['account_id']:
        raise CollectionError('publisher_id_mismatch')
    return row | {'company_id': job['company_id'], 'evidence_url': canonical_evidence_url(evidence, url)}


def verify_review(reader, job, review, now):
    url = review_url(job, review)
    response = reader._weread_http_get('https://weread.qq.com/web/mp/content',
                                     params={'reviewId': review}, timeout=(5, 15))
    response.raise_for_status()
    response.encoding = 'utf-8'
    try:
        data = response.json()
    except ValueError:
        data = None
    if isinstance(data, dict):
        code = data.get('errCode', data.get('errcode', 0))
        if code:
            raise CollectionError(code if isinstance(code, int) else 'invalid_response')
    evidence = 'https://weread.qq.com/web/mp/content?' + urlencode({'reviewId': review})
    return verified_html(response.text, job, url, evidence, now)


def verify_public(candidate, job, now, reader=None, get=None):
    """Read public originals without login headers, or a scoped short-link article via WeRead."""
    url = canonical_url(candidate['url'])
    if reader is not None and urlparse(url).path.startswith('/s/'):
        review = job['book_id'] + '_' + urlparse(url).path.removeprefix('/s/').replace('_', '~')
        return verify_review(reader, job, review, now)
    get = get or requests.get
    current, seen = url, set()
    for _ in range(3):
        if current in seen:
            break
        seen.add(current)
        response = get(current, headers={'User-Agent': MOBILE_UA}, timeout=(5, 15), allow_redirects=False)
        response.raise_for_status()
        if 300 <= response.status_code < 400:
            # Only normal article redirects are followed, never verification/login pages.
            current = canonical_url(urljoin(current, response.headers.get('Location', '')))
            continue
        response.encoding = 'utf-8'
        return verified_html(response.text, job, url, url, now)
    raise CollectionError('public_original_unavailable')


def discover_public(jobs, now, *, deadline=None, clock=time.monotonic, get=None, max_pages=10, max_articles=100):
    """Existing public AIHOT all-mode leads; list dates are never published as article dates."""
    get = get or requests.get
    candidates, seen, counts, cursor, more, pages, limited = [], set(), {}, None, True, 0, False
    try:
        while more and pages < max_pages:
            if deadline is not None and clock() >= deadline:
                limited = True
                break
            params = {'mode': 'all', 'window': '24h', 'by': 'published', 'limit': 100}
            if cursor:
                params['cursor'] = cursor
            response = get('https://aihot.news/api/v1/items', params=params, timeout=(5, 15))
            response.raise_for_status()
            data = response.json()
            if data.get('schemaVersion') != 1 or not isinstance(data.get('items'), list) or not isinstance(data.get('page'), dict):
                raise ValueError('invalid_public_discovery')
            pages += 1
            for item in data['items']:
                source = item.get('source') if isinstance(item, dict) else None
                name = source.get('name', '') if isinstance(source, dict) else ''
                if not isinstance(name, str) or not name.startswith('公众号：'):
                    continue
                name = name.removeprefix('公众号：').strip()
                job = next((j for j in jobs if name == j['account_name'] or
                            name.startswith(j['account_name'] + '（') or name.startswith(j['account_name'] + ' (')), None)
                if job is None:
                    continue
                try:
                    url = canonical_url((item.get('links') or {}).get('original'))
                except (ValueError, AttributeError):
                    continue
                key = (job['account_name'], url)
                if key in seen:
                    continue
                if counts.get(job['account_name'], 0) >= max_articles:
                    limited = True
                    continue
                seen.add(key)
                counts[job['account_name']] = counts.get(job['account_name'], 0) + 1
                candidates.append({k: job[k] for k in ('company_id', 'account_name')} | {'url': url})
            more = bool(data['page'].get('hasMore'))
            next_cursor = data['page'].get('nextCursor')
            if more and (not isinstance(next_cursor, str) or not next_cursor or next_cursor == cursor):
                raise ValueError('invalid_public_cursor')
            cursor = next_cursor
        return {'ok': True, 'truncated': more or limited, 'candidates': candidates}
    except (ValueError, requests.RequestException):
        return {'ok': False, 'truncated': True, 'candidates': candidates}


def collect(reader, jobs, now, delay=time.sleep, *, public_discovery=None, public_verifier=None,
            clock=time.monotonic, max_seconds=240, max_pages=10, max_articles=100):
    """Scan list pages first, then merge bounded public/cover leads with explicit gaps."""
    deadline = clock() + max_seconds
    result = {'searches': [], 'candidates': [], 'rows': [], 'errors': [], 'account_coverage': []}
    by_name = {j['account_name']: j for j in jobs}
    coverage = {j['account_name']: {'account_name': j['account_name'], 'state': 'fallback',
        'list_pages': 0, 'list_complete': False, 'candidates': 0, 'verified': 0, 'unverified': 0} for j in jobs}
    searches = {j['account_name']: {'account_name': j['account_name'], 'ok': False} for j in jobs}
    seen, indexed, error_keys = set(), {}, set()
    private_blocked = False
    public_blocked = False
    list_available = True

    def gap(name, code):
        key = (name, code)
        if key not in error_keys:
            error_keys.add(key)
            result['errors'].append({'account_name': name, 'error': code})

    def ready(name):
        if clock() >= deadline:
            coverage[name]['state'] = 'limited'
            gap(name, 'wemprss_budget_exceeded')
            return False
        if coverage[name]['candidates'] >= max_articles:
            coverage[name]['state'] = 'limited'
            gap(name, 'wemprss_article_limit')
            return False
        return True

    def failed(name, exc, phase):
        nonlocal private_blocked, public_blocked, list_available
        code = getattr(exc, 'code', None)
        http = getattr(getattr(exc, 'response', None), 'status_code', None)
        if code == -2041 and phase == 'list':
            list_available = False
            reason = 'wemprss_list_api_-2041'
        elif isinstance(code, int) and code in STOP_CODES:
            private_blocked = True
            reason = f'wemprss_api_{code}'
        elif isinstance(http, int) and (http in STOP_CODES or http >= 500):
            if phase != 'public':
                private_blocked = True
            reason = f'wemprss_http_{http}'
        else:
            reason = 'wemprss_' + phase + '_failed'
        if phase == 'public' and (http in {401, 403, 429, 499} or
                                  isinstance(http, int) and http >= 500 or code in STOP_CODES):
            public_blocked = True
        if private_blocked:
            coverage[name]['state'] = 'blocked'
        gap(name, reason)
        searches[name]['error'] = reason

    def add(name, row):
        result['rows'].append(row)
        result['candidates'].append({'company_id': row['company_id'], 'account_name': name, 'url': row['url']})
        indexed[(name, row['url'])] = row
        coverage[name]['verified'] += 1
        searches[name]['ok'] = True
        if row['published'] is None:
            gap(name, 'wemprss_unknown_publication_date')
        return row

    def article(job, review):
        name = job['account_name']
        try:
            url = review_url(job, review)
            key = (name, url)
            if key in seen:
                return indexed.get(key)
            if not ready(name):
                return None
            seen.add(key)
            coverage[name]['candidates'] += 1
            delay(2)
            return add(name, verify_review(reader, job, review, now))
        except Exception as exc:
            coverage[name]['unverified'] += 1
            failed(name, exc, 'article')
            return None

    # A denied list backend is not retried for each publisher. Authentication or quota
    # failures stop every subsequent private request, without switching reader accounts.
    for job in jobs:
        name = job['account_name']; cov = coverage[name]
        if private_blocked:
            cov['state'] = 'blocked'
            searches[name]['error'] = 'wemprss_stopped_after_auth_or_quota_error'
            gap(name, searches[name]['error'])
            continue
        if not list_available or not hasattr(reader, '_get_mp_articles_page'):
            gap(name, 'wemprss_list_backend_unavailable')
            continue
        offset, last_date, ordered = 0, None, True
        for _ in range(max_pages):
            if not ready(name) or private_blocked:
                break
            try:
                delay(2)
                data = reader._get_mp_articles_page(job['book_id'], offset=offset)
                groups = data.get('reviews') if isinstance(data, dict) else None
                if not isinstance(groups, list):
                    raise CollectionError('invalid_list')
                cov['list_pages'] += 1
                searches[name]['ok'] = True
                if not groups:
                    cov['list_complete'] = True
                    break
                all_old = True
                count = 0
                for group in groups:
                    children = group.get('subReviews') if isinstance(group, dict) else None
                    if not isinstance(children, list) or not children:
                        gap(name, 'wemprss_list_failed'); all_old = False
                        continue
                    for child in children:
                        if private_blocked or not ready(name):
                            all_old = False
                            break
                        review = child.get('review', child) if isinstance(child, dict) else {}
                        review_id = review.get('reviewId') or child.get('reviewId') if isinstance(child, dict) else None
                        count += 1
                        row = article(job, review_id)
                        published = published_datetime(row['published']) if row else None
                        if not published or published >= now - timedelta(hours=24):
                            all_old = False
                        if published:
                            if last_date and published > last_date:
                                ordered = False
                            last_date = published
                # Finish the entire page, including every subarticle, before using
                # an observed ordered, fully verified old page as the time boundary.
                if count and all_old and ordered:
                    cov['list_complete'] = True
                    break
                offset += len(groups)
            except Exception as exc:
                failed(name, exc, 'list')
                break
        else:
            cov['state'] = 'limited'
            gap(name, 'wemprss_list_limit')
        if cov['list_complete'] and not any(e['account_name'] == name for e in result['errors']):
            cov['state'] = 'complete'

    fallback_jobs = [j for j in jobs if coverage[j['account_name']]['state'] != 'complete']
    for job in fallback_jobs:
        name = job['account_name']
        if private_blocked:
            coverage[name]['state'] = 'blocked'
            gap(name, 'wemprss_stopped_after_auth_or_quota_error')
            searches[name]['error'] = 'wemprss_stopped_after_auth_or_quota_error'
            continue
        if not ready(name):
            continue
        try:
            delay(2)
            cover = reader._get_mp_cover(job['book_id'])
            if normalized_name(cover.get('name')) != normalized_name(name):
                raise CollectionError('publisher_id_mismatch')
            article(job, cover.get('reviewId'))
        except Exception as exc:
            failed(name, exc, 'article')

    if fallback_jobs and clock() < deadline:
        discovery = (public_discovery or discover_public)(fallback_jobs, now, deadline=deadline,
                                                          clock=clock, max_articles=max_articles)
        for job in fallback_jobs:
            if not discovery.get('ok'):
                gap(job['account_name'], 'wemprss_public_discovery_failed')
            if discovery.get('truncated'):
                gap(job['account_name'], 'wemprss_public_discovery_truncated')
        for candidate in discovery.get('candidates', []):
            if public_blocked:
                break
            name = candidate.get('account_name')
            job = by_name.get(name)
            if job not in fallback_jobs or candidate.get('company_id') != job['company_id']:
                continue
            try:
                url = canonical_url(candidate.get('url'))
                key = (name, url)
                if key in seen or not ready(name):
                    continue
                seen.add(key); coverage[name]['candidates'] += 1
                delay(2)
                row = (public_verifier(candidate, job, now) if public_verifier else
                       verify_public(candidate, job, now, None if private_blocked else reader))
                add(name, row)
            except Exception as exc:
                coverage[name]['unverified'] += 1
                failed(name, exc, 'public')
    elif fallback_jobs:
        for job in fallback_jobs:
            gap(job['account_name'], 'wemprss_budget_exceeded')

    result['searches'] = list(searches.values())
    result['account_coverage'] = list(coverage.values())
    result['coverage_complete'] = all(c['state'] == 'complete' for c in coverage.values())
    return result


def merge_result(result, existing, jobs, now):
    indexed = {(r["company_id"], r["url"]): r for r in result["rows"]}
    def verified(candidate, _now):
        return dict(indexed[(candidate["company_id"], candidate["url"])])
    snapshot = sync(result, existing, now, verifier=verified,
                    expected_accounts=[r["account_name"] for r in jobs], max_candidates_per_account=100)
    run = snapshot["last_run"]
    run["errors"].extend(result.get("errors", []))
    run["coverage_complete"] = result.get("coverage_complete", False)
    run["account_coverage"] = result.get("account_coverage", [])
    run["candidates"] = sum(c["candidates"] for c in run["account_coverage"])
    run["ok"] = not run["errors"] and run["coverage_complete"]
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
        result = collect(SingleAccountReader(reader), jobs, datetime.now(timezone.utc))
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
