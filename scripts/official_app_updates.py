"""Dated first-party application updates; no account sessions or model calls.

Parsers return plain rows so the existing collector owns ranking and storage.
An unavailable source raises an error for its own source-status entry.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlparse

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

UTC = timezone.utc
MAX_AGE_DAYS = 45
MAX_ITEMS = 20
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
APP_SOURCES = (
    {"id": "official_app_meta", "title": "Meta AI / Muse Newsroom", "kind": "rss",
     "url": "https://about.fb.com/feed/", "home": "https://about.fb.com/news/", "host": "about.fb.com"},
    {"id": "official_app_gemini_blog", "title": "Gemini App Blog", "publisher": "Google Gemini", "kind": "rss",
     "url": "https://blog.google/innovation-and-ai/products/gemini-app/rss/",
     "home": "https://blog.google/innovation-and-ai/products/gemini-app/", "host": "blog.google"},
    {"id": "official_app_gemini_product", "title": "Gemini Product Blog", "publisher": "Google Gemini", "kind": "rss",
     "url": "https://blog.google/products-and-platforms/products/gemini/rss/",
     "home": "https://blog.google/products-and-platforms/products/gemini/", "host": "blog.google"},
    {"id": "official_app_gemini_notes", "title": "Gemini App Release Notes", "kind": "gemini",
     "url": "https://gemini.google/release-notes/", "home": "https://gemini.google/", "host": "gemini.google"},
    {"id": "official_app_chatgpt", "title": "ChatGPT Product Updates", "kind": "chatgpt",
     "url": "https://learn.chatgpt.com/docs/whats-new", "home": "https://learn.chatgpt.com/", "host": "learn.chatgpt.com"},
    {"id": "official_app_qwen_work", "title": "千问办公产品更新", "kind": "qwen",
     "url": "https://learn.qwenwork.cn/whatsnew/", "home": "https://qwenwork.cn/", "host": "learn.qwenwork.cn"},
    {"id": "official_app_qwen_desktop", "title": "千问办公客户端更新", "kind": "qwen_desktop",
     "url": "https://docs.qwenwork.cn/release-notes/desktop", "home": "https://qwenwork.cn/", "host": "docs.qwenwork.cn"},
    {"id": "official_app_yuanbao", "title": "元宝官方版本更新", "kind": "yuanbao",
     "url": "https://itunes.apple.com/lookup?id=6480446430&country=cn", "home": "https://yuanbao.tencent.com/", "host": "apps.apple.com"},
)


def update_fragment(parsed) -> str:
    """Keep version/issue identities only on these first-party update pages.

    Native anchors are used where available. Gemini and App Store have no
    per-release anchors; standard text-fragment links point to the visible
    date/version instead. Ordinary article tracking fragments still disappear.
    """
    host, path, fragment = parsed.hostname, parsed.path.rstrip("/"), parsed.fragment
    patterns = {
        ("learn.qwenwork.cn", "/whatsnew"): r"d\d{8}",
        ("docs.qwenwork.cn", "/release-notes/desktop"): r"\d{4}-\d{2}-\d{2}",
        ("learn.chatgpt.com", "/docs/whats-new"): r"[a-z0-9-]+",
        ("gemini.google", "/release-notes"): r":~:text=\d{4}\.\d{2}\.\d{2}",
        ("apps.apple.com", "/cn/app/id6480446430"): r":~:text=\d+(?:\.\d+){1,3}",
    }
    pattern = patterns.get((host, path))
    return fragment if pattern and re.fullmatch(pattern, fragment) else ""


def plain(value: str, limit: int = 500) -> str:
    soup = BeautifulSoup(value or "", "html.parser")
    for node in soup.select("script,style,button,nav"):
        node.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()[:limit]


def dated(value: str) -> datetime | None:
    # Do not let a missing year/month/day inherit today's date from dateutil.
    value = str(value or "").strip()
    if not (re.search(r"\b20\d{2}-\d{2}-\d{2}", value)
            or re.search(r"\b\d{1,2} [A-Za-z]{3,9} 20\d{2}\b", value)
            or re.search(r"\b[A-Za-z]{3,9} \d{1,2},? 20\d{2}\b", value)):
        return None
    try:
        result = date_parser.parse(value)
        return (result.replace(tzinfo=UTC) if result.tzinfo is None else result).astimezone(UTC)
    except (ValueError, OverflowError):
        return None


def keep_rows(rows: list[dict], spec: dict, now: datetime) -> list[dict]:
    result, seen = [], set()
    for row in rows:
        stamp, url = row.get("published_at"), str(row.get("url") or "")
        title = re.sub(r"\s+", " ", str(row.get("title") or "")).strip()
        parsed = urlparse(url)
        if not title or parsed.scheme != "https" or parsed.hostname != spec["host"]:
            continue
        if parsed.username or parsed.password or parsed.port not in (None, 443):
            continue
        if not stamp or not now - timedelta(days=MAX_AGE_DAYS) <= stamp <= now:
            continue
        if url in seen:
            continue
        seen.add(url)
        result.append({**row, "title": title, "source": spec.get("publisher", spec["title"]), "feed_url": spec["url"],
                       "feed_home": spec["home"], "select_tier": "T1"})
    return sorted(result, key=lambda row: row["published_at"], reverse=True)[:MAX_ITEMS]


def parse_rss(text: str, spec: dict) -> list[dict]:
    root = ET.fromstring(text)
    if root.tag.split("}")[-1] not in ("rss", "feed", "RDF"):
        raise ValueError("Expected an official RSS/Atom document")
    rows = []
    for item in root.iter():
        if item.tag.split("}")[-1] not in ("item", "entry"):
            continue
        fields = {child.tag.split("}")[-1]: child for child in item}
        def value(*keys):
            for key in keys:
                node = fields.get(key)
                if node is not None:
                    text = "".join(node.itertext()).strip()
                    if text:
                        return text
            return ""
        link = value("link")
        if not link and fields.get("link") is not None:
            link = fields["link"].get("href", "")
        title, summary = plain(value("title"), 300), plain(value("description", "summary", "encoded", "content"))
        if spec["id"].startswith("official_app_gemini_") and not re.search(r"/products/(?:gemini|gemini-app)/", urlparse(link).path):
            continue  # Product feeds cross-post model/API/general Google news too.
        if spec["id"] == "official_app_meta" and not re.search(
            r"\b(?:muse|meta ai|artificial intelligence|ai glasses|ray-ban|oakley)\b", title + " " + summary, re.I
        ):
            continue
        rows.append({"title": title, "url": link, "summary": summary,
                     "published_at": dated(value("pubDate", "published", "date"))})
    return rows


def parse_qwen(text: str, spec: dict) -> list[dict]:
    soup, rows = BeautifulSoup(text, "html.parser"), []
    for issue in soup.select("section.wn-issue[id]"):
        identity = issue["id"]
        if not re.fullmatch(r"d\d{8}", identity):
            continue
        headings = [plain(str(h), 160) for h in issue.select("article.wn-item h2")]
        if not headings:
            continue
        try:
            stamp = datetime.strptime(identity[1:], "%Y%m%d").replace(tzinfo=UTC)
        except ValueError:
            continue
        rows.append({"title": "千问办公产品更新：" + "；".join(headings)[:220],
                     "url": spec["url"] + "#" + identity,
                     "published_at": stamp,
                     "summary": plain(str(issue.select_one(".wn-content-col") or issue))})
    return rows


def parse_qwen_desktop(text: str, spec: dict) -> list[dict]:
    soup, rows = BeautifulSoup(text, "html.parser"), []
    for issue in soup.select(".update-container[id]"):
        stamp = issue["id"]
        if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", stamp):
            continue
        version = issue.select_one('[data-component-part="update-description"]')
        content = issue.select_one('[data-component-part="update-content"]')
        if not content:
            continue
        rows.append({"title": "千问办公客户端更新：" + (version.get_text(" ", strip=True) if version else stamp),
                     "url": spec["url"] + "#" + stamp, "published_at": dated(stamp),
                     "summary": plain(str(content))})
    return rows


def parse_gemini(text: str, spec: dict) -> list[dict]:
    soup, rows = BeautifulSoup(text, "html.parser"), []
    for heading in soup.select("main h2"):
        stamp = heading.get_text(" ", strip=True)
        if not re.fullmatch(r"20\d{2}\.\d{2}\.\d{2}", stamp):
            continue
        card = heading.parent
        titles = [h.get_text(" ", strip=True) for h in card.select("h3")]
        if not titles:
            continue
        rows.append({"title": "Gemini 应用更新：" + "；".join(titles)[:240],
                     "url": spec["url"] + "#:~:text=" + stamp,
                     "published_at": dated(stamp.replace(".", "-")), "summary": plain(str(card))})
    return rows


def week_start(label: str) -> datetime | None:
    match = re.fullmatch(r"([A-Za-z]+) (\d{1,2})[–—-](?:[A-Za-z]+ )?\d{1,2}, (20\d{2})", label)
    return dated(f"{match[1]} {match[2]}, {match[3]}") if match else None


def parse_chatgpt(text: str, spec: dict) -> list[dict]:
    soup, rows = BeautifulSoup(text, "html.parser"), []
    for heading in soup.select("#mainContent h2[id]"):
        label = (heading.select_one("span") or heading).get_text(" ", strip=True)
        stamp = week_start(label)
        if not stamp:
            continue  # Event headings without a dated period need their own dated source.
        blocks, products = [], set()
        for sibling in heading.next_siblings:
            if getattr(sibling, "name", None) == "h2":
                break
            if not getattr(sibling, "name", None):
                continue
            if sibling.has_attr("data-update-products"):
                products = set(sibling["data-update-products"].split())
            if products & {"chatgpt", "dots"} and sibling.name in ("h3", "p", "ul", "ol"):
                blocks.append(plain(str(sibling)))
        if blocks:
            rows.append({"title": "ChatGPT 产品周报：" + label,
                         "url": spec["url"] + "#" + quote(heading["id"], safe="-"),
                         "published_at": stamp, "summary": " ".join(blocks)[:500]})
    return rows


def parse_yuanbao(payload: dict, spec: dict) -> list[dict]:
    rows = []
    for item in payload.get("results", []):
        if item.get("trackId") != 6480446430 or item.get("sellerName") != "Tencent Technology (Shenzhen) Company Limited":
            continue
        version = str(item.get("version") or "")
        if not re.fullmatch(r"\d+(?:\.\d+){1,3}", version):
            continue
        if not item.get("releaseNotes"):
            continue
        rows.append({"title": f"元宝 {version} 官方版本更新", "url": "https://apps.apple.com/cn/app/id6480446430#:~:text=" + version,
                     "published_at": dated(item.get("currentVersionReleaseDate")),
                     "summary": plain(item["releaseNotes"])})
    return rows


PARSERS = {"rss": parse_rss, "qwen": parse_qwen, "qwen_desktop": parse_qwen_desktop,
           "gemini": parse_gemini, "chatgpt": parse_chatgpt, "yuanbao": parse_yuanbao}


def fetch_source(session, spec: dict, now: datetime) -> list[dict]:
    response = session.get(spec["url"], timeout=(8, 20), headers={"User-Agent": "AI-News-Radar/1.0 OfficialAppUpdates"})
    response.raise_for_status()
    allowed_hosts = {urlparse(spec["url"]).hostname}
    # OpenAI shares its official documentation across these two hostnames.
    if spec["kind"] == "chatgpt":
        allowed_hosts.add("developers.openai.com")
    final = urlparse(response.url)
    if final.scheme != "https" or final.hostname not in allowed_hosts:
        raise ValueError("Official update redirected outside its verified domains")
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise ValueError("Official update response exceeds size limit")
    if spec["kind"] != "rss" and spec["kind"] != "yuanbao":
        # Challenge pages must not become a green, empty-source result.
        text = response.text
        markers = {"qwen": "wn-issue", "qwen_desktop": "update-container", "gemini": "<h2", "chatgpt": "mainContent"}
        if markers[spec["kind"]] not in text:
            raise ValueError("Official update page structure was not recognized")
    payload = response.json() if spec["kind"] == "yuanbao" else response.text
    rows = PARSERS[spec["kind"]](payload, spec)
    if not rows and spec["kind"] != "rss":
        raise ValueError("No dated official updates were recognized; verify page structure or app identity")
    return keep_rows(rows, spec, now)
