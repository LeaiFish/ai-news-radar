#!/usr/bin/env python3
"""Public, metadata-only case discovery. Deliberately separate from news pools."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import requests

FEED = 'https://agentusecases.ai/feed.xml'
CATEGORIES = {
    'Shopping & Errands': ('shopping', '购物'),
    'Life Admin & Home': ('life', '生活事务'),
    'Money, Bills & Benefits': ('life', '生活事务'),
    'Work & Operations': ('office', '办公协作'),
}
FIELDS = {'id', 'title', 'summary', 'case_url', 'original_url', 'category', 'category_name',
          'collected_at', 'first_seen_at', 'original_published_at', 'original_date_label',
          'original_date_precision', 'date_source', 'evidence_type'}


def stamp(now=None):
    return (now or datetime.now(timezone.utc)).isoformat(timespec='seconds').replace('+00:00', 'Z')


def public_url(value):
    try:
        u = urlsplit(value)
        if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password:
            return False
        host = u.hostname.lower()
        if '.' not in host or host.endswith(('.local', '.internal', '.localhost')):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return True
    except (TypeError, ValueError):
        return False


def case_url(value):
    return bool(public_url(value) and re.fullmatch(r'https://agentusecases\.ai/use-case/[a-z0-9-]+', value))


def fetch(url):
    # Never fetch originals or follow redirects to another origin.
    for _ in range(4):
        if urlsplit(url).netloc != 'agentusecases.ai' or not url.startswith('https://'):
            raise ValueError('Unexpected case-directory origin')
        with requests.get(url, timeout=20, allow_redirects=False, stream=True) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers['Location'])
                continue
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_content(16384):
                data.extend(chunk)
                if len(data) > 512 * 1024:
                    raise ValueError('Case-directory response too large')
            return bytes(data)
    raise ValueError('Too many redirects')


def clean_summary(value):
    return (BeautifulSoup(value, 'html.parser').get_text(' ', strip=True) if '<' in value else value).strip()[:1200]


def parse_feed(raw, now=None):
    now = now or datetime.now(timezone.utc)
    rows = {}
    for item in ET.fromstring(raw).findall('./channel/item'):
        url = item.findtext('link', '').strip()
        if not case_url(url):
            continue
        try:
            at = parsedate_to_datetime(item.findtext('pubDate', ''))
            if at.tzinfo is None or at > now + timedelta(minutes=5):
                continue
        except (TypeError, ValueError):
            continue
        title = item.findtext('title', '').strip()[:500]
        if title:
            rows.setdefault(url, {'id': hashlib.sha256(url.encode()).hexdigest()[:24],
                'title': title, 'summary': clean_summary(item.findtext('description', '')),
                'case_url': url, 'collected_at': stamp(at)})
    return list(rows.values())[:60]


def parse_detail(raw):
    main = BeautifulSoup(raw, 'html.parser').find('main')
    if main is None:
        raise ValueError('Case page has no main content')
    category_link = main.select_one('a[href^="/category/"]')
    category = CATEGORIES.get(category_link.get_text(' ', strip=True)) if category_link else None
    if category is None:
        return None
    original = next((a.get('href') for a in main.find_all('a') if 'Read the original' in a.get_text(' ', strip=True)), None)
    original = original if public_url(original) else None
    source = next((p.get_text(' ', strip=True) for p in main.find_all('p') if p.get_text(' ', strip=True).startswith('Source:')), '')
    label = source.rsplit('·', 1)[-1].strip() if '·' in source else ''
    published, precision = None, 'unknown'
    if re.fullmatch(r'[A-Z][a-z]{2} \d{1,2}, \d{4}', label):
        try:
            published = datetime.strptime(label, '%b %d, %Y').date().isoformat()
            precision = 'day'
        except ValueError:
            pass
    elif re.fullmatch(r'[A-Z][a-z]{2} \d{4}', label):
        precision = 'month'
    elif re.fullmatch(r'\d{4}', label):
        precision = 'year'
    if precision == 'unknown':
        label = ''
    return {'category': category[0], 'category_name': category[1], 'original_url': original,
            'original_published_at': published, 'original_date_label': label or None,
            'original_date_precision': precision, 'date_source': 'case_directory' if label else None,
            'evidence_type': 'reported_case'}


def sanitize(row):
    if not isinstance(row, dict) or not case_url(row.get('case_url', '')) or row.get('category') not in {'shopping', 'life', 'office'}:
        return None
    clean = {k: row.get(k) for k in FIELDS}
    if not public_url(clean.get('original_url')):
        clean['original_url'] = None
    return clean


def collect(previous=None, now=None, getter=fetch):
    previous = previous or {}
    now = now or datetime.now(timezone.utc)
    at = stamp(now)
    old = {r['case_url']: r for row in previous.get('items', []) if (r := sanitize(row))}
    try:
        candidates = parse_feed(getter(FEED), now)
        if not candidates:
            raise ValueError('No valid RSS cases')
    except Exception:
        return {**previous, 'version': 1, 'source_url': FEED, 'last_attempt_at': at,
                'status': {'ok': False, 'partial': True, 'error': 'feed_unavailable'}, 'items': list(old.values())}
    failures = 0
    def detail(row):
        try:
            return row, parse_detail(getter(row['case_url'])), False
        except Exception:
            return row, None, True
    with ThreadPoolExecutor(max_workers=6) as pool:
        for row, metadata, failed in pool.map(detail, candidates):
            failures += int(failed)
            if metadata:
                prior = old.get(row['case_url'], {})
                old[row['case_url']] = {**row, **metadata, 'first_seen_at': prior.get('first_seen_at') or at}
            elif not failed:
                old.pop(row['case_url'], None)
    cutoff = stamp(now - timedelta(days=120))
    items = [r for r in old.values() if (r.get('collected_at') or '') >= cutoff]
    items.sort(key=lambda r: (r.get('collected_at') or '', r['case_url']), reverse=True)
    return {'version': 1, 'source_url': FEED, 'generated_at': at, 'last_attempt_at': at,
            'last_success_at': at, 'status': {'ok': True, 'partial': bool(failures),
                'feed_items': len(candidates), 'detail_failures': failures}, 'items': items[:500]}


def refresh(output):
    output = Path(output)
    try:
        previous = json.loads(output.read_text()) if output.exists() else {}
        if not isinstance(previous, dict):
            previous = {}
    except (OSError, ValueError):
        previous = {}
    result = collect(previous)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(output)
    print(f"Case leads: {len(result['items'])}; status={result['status']}")
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=Path('data/case-leads.json'))
    args = p.parse_args()
    refresh(args.output)


if __name__ == '__main__':
    main()
