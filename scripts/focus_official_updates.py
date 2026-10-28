"""Bounded public first-party pages for the maintainer's focus publishers.

Only explicit publication dates count. No account sessions, sitemap modification
times, page bodies, or fetch-time date substitution enter news records.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

try:
    from .official_app_updates import dated, keep_rows, plain, MAX_RESPONSE_BYTES
except ImportError:
    from official_app_updates import dated, keep_rows, plain, MAX_RESPONSE_BYTES

SOURCES = (
    {"id": "official_focus_xai", "title": "xAI News", "url": "https://x.ai/news", "host": "x.ai", "prefix": "/news/"},
    {"id": "official_focus_grok_bot", "title": "Grok Bot Changelog", "url": "https://x.ai/changelog/bot", "host": "x.ai", "kind": "changelog"},
    {"id": "official_focus_claude", "title": "Claude Articles", "url": "https://claude.com/resources/articles", "host": "claude.com", "prefix": "/resources/articles/"},
    {"id": "official_focus_suno", "title": "Suno Blog", "url": "https://suno.com/blog", "host": "suno.com", "prefix": "/blog/", "kind": "structured"},
    {"id": "official_focus_krea", "title": "Krea Blog", "url": "https://www.krea.ai/blog", "host": "www.krea.ai", "prefix": "/blog/"},
    {"id": "official_focus_luma", "title": "Luma News", "url": "https://lumalabs.ai/news", "host": "lumalabs.ai", "prefix": "/news/", "kind": "structured"},
    {"id": "official_focus_runway", "title": "Runway News", "url": "https://runway.com/news", "host": "runway.com", "prefix": "/news/", "kind": "structured"},
    {"id": "official_focus_siliconflow", "title": "SiliconFlow Blog", "url": "https://www.siliconflow.com/blog", "host": "www.siliconflow.com", "prefix": "/blog/"},
    {"id": "official_focus_alibaba", "title": "Alibaba Cloud Blog", "url": "https://www.alibabacloud.com/blog", "host": "www.alibabacloud.com", "prefix": "/blog/", "ai_only": True},
    {"id": "official_focus_viggle", "title": "Viggle Blog", "url": "https://viggle.ai/blog", "host": "viggle.ai", "prefix": "/blog/", "kind": "details", "max_details": 8},
    {"id": "official_focus_minimax", "title": "MiniMax Blog", "url": "https://www.minimax.io/blog", "host": "www.minimax.io", "prefix": "/blog/"},
)
SOURCES = tuple(dict(s, home=s["url"], max_items=6) for s in SOURCES)
DATE_TEXT = re.compile(r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+20\d{2}|\b20\d{2}-\d{2}-\d{2}\b", re.I)
AI_TEXT = re.compile(r"\b(?:ai|llm|agent|qwen|model|inference|machine learning|mcp)\b|人工智能|千问|通义", re.I)


def valid_url(value, spec):
    url = urljoin(spec["url"], str(value or ""))
    parsed = urlsplit(url)
    return (url if parsed.scheme == "https" and parsed.hostname == spec["host"]
            and not parsed.username and not parsed.password and parsed.port in (None, 443)
            and parsed.path.startswith(spec.get("prefix", "/")) else None)


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def structured_rows(soup, spec):
    """Read public JSON-LD and server-rendered Next data, never execute JS."""
    objects = []
    for script in soup.find_all("script"):
        value = script.string or script.get_text()
        if not value or len(value) > MAX_RESPONSE_BYTES:
            continue
        try:
            objects.append(json.loads(value))
            continue
        except (ValueError, TypeError):
            pass
        match = re.fullmatch(r"self\.__next_f\.push\((.*)\)\s*;?", value.strip(), re.S)
        if not match:
            continue
        try:
            frame = json.loads(match[1])
        except ValueError:
            continue
        if not isinstance(frame, list) or len(frame) < 2 or not isinstance(frame[1], str):
            continue
        for line in frame[1].splitlines():
            payload = line.partition(":")[2]
            if payload.startswith(("[", "{")):
                try:
                    objects.append(json.loads(payload))
                except ValueError:
                    pass
    rows = []
    for obj in objects:
        for node in walk(obj):
            stamp = dated(node.get("datePublished") or node.get("publishedAt") or node.get("date"))
            title = node.get("headline") or node.get("title")
            slug = node.get("slug")
            if isinstance(slug, dict):
                slug = slug.get("current")
            link = node.get("url") or node.get("href")
            if not link and isinstance(slug, str):
                link = "/" + slug.lstrip("/") if "/" in slug else spec.get("prefix", "/") + slug
            url = valid_url(link, spec) if link else None
            if stamp and isinstance(title, str) and url:
                rows.append({"title": plain(title, 300), "url": url, "published_at": stamp,
                             "summary": plain(node.get("description") or node.get("excerpt") or node.get("subtitle") or "")})
    return rows


def card_rows(soup, spec):
    rows = []
    for anchor in soup.find_all("a", href=True):
        url = valid_url(anchor["href"], spec)
        if not url or any(p in urlsplit(url).path for p in ("/category/", "/tag/")):
            continue
        card = anchor
        for _ in range(5):
            # Never borrow a neighbouring card's date from a whole list.
            urls = {valid_url(a.get("href"), spec) for a in card.find_all("a", href=True)} - {None}
            if len(urls) > 1:
                break
            tm = card.find("time")
            match = DATE_TEXT.search(card.get_text(" ", strip=True))
            stamp = dated(tm.get("datetime", "")) if tm else dated(match[0]) if match else None
            heading = anchor.find(["h2", "h3", "h4"]) or card.find(["h2", "h3", "h4"])
            if stamp:
                title = plain(str(heading), 300) if heading else plain(str(anchor), 300)
                if title and not DATE_TEXT.fullmatch(title):
                    title = DATE_TEXT.sub("", title).strip(" ·")
                    rows.append({"title": title, "url": url, "published_at": stamp,
                                 "summary": plain(str(card))})
                break
            if card.parent is None or card.parent.name in ("body", "html"):
                break
            card = card.parent
    return rows


def changelog_rows(soup, spec):
    rows = []
    for article in soup.find_all("article"):
        tm, heading = article.find("time"), article.find("h2", id=True)
        if not tm or not heading or not re.fullmatch(r"v\d+(?:\.\d+){1,3}", heading["id"]):
            continue
        rows.append({"title": f"Grok Bot {heading['id']}: {heading.get_text(' ', strip=True)}",
                     "url": spec["url"] + "#" + heading["id"],
                     "published_at": dated(tm.get("datetime")),
                     "summary": " ".join(li.get_text(" ", strip=True) for li in article.select("section:first-of-type li"))[:500]})
    return rows


def get_page(session, url, spec):
    response = session.get(url, timeout=(5, 20), headers={"User-Agent": "AI-News-Radar/1.0 FocusOfficialUpdates"})
    response.raise_for_status()
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise ValueError("Official focus page exceeds size limit")
    if urlsplit(response.url).hostname != spec["host"] or urlsplit(response.url).scheme != "https":
        raise ValueError("Official focus page redirected outside its verified host")
    return BeautifulSoup(response.text, "html.parser")


def fetch_source(session, spec, now):
    soup = get_page(session, spec["url"], spec)
    if spec.get("kind") == "changelog":
        rows = changelog_rows(soup, spec)
    else:
        rows = structured_rows(soup, spec) + card_rows(soup, spec)
    if spec.get("kind") == "details":
        links = list(dict.fromkeys(valid_url(a["href"], spec) for a in soup.find_all("a", href=True)))
        for url in [u for u in links if u][:spec["max_details"]]:
            rows.extend(structured_rows(get_page(session, url, spec), spec))
    if not rows:
        raise ValueError("No dated focus-publisher entries recognized; verify page structure")
    if spec.get("ai_only"):
        rows = [r for r in rows if AI_TEXT.search(r["title"] + " " + r.get("summary", ""))]
    # Reuse the existing first-party date, host and age checks; independent cap.
    return keep_rows(rows, spec, now)[:spec["max_items"]]
