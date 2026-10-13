"""Free public-news excerpts: no model API, paid reader, cookie or full-body storage."""
from __future__ import annotations

import argparse
import html
import ipaddress
import json
import re
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from scripts.focus_sources import focus_priority
except ModuleNotFoundError:
    from focus_sources import focus_priority

ALLOWED_HOSTS = frozenset({
    "www.aibase.com", "aibase.com", "qwen.ai", "seed.bytedance.com",
    "www.marktechpost.com", "marktechpost.com", "techcrunch.com",
    "www.ithome.com", "www.moonshot.cn", "www.minimaxi.com",
    "openai.com", "www.anthropic.com", "blog.google", "github.blog",
    "huggingface.co", "www.theverge.com", "the-decoder.com",
})


def clean_text(value: str) -> str:
    raw = value or ""
    text = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True) if "<" in raw else html.unescape(raw)
    return re.sub(r"\s+", " ", text).strip()


def excerpt(value: str, title: str = "") -> str:
    text = clean_text(value)
    if len(text) < 30 or text.casefold() == clean_text(title).casefold():
        return ""
    if re.search(r"access denied|verify you are human|enable javascript|验证码|访问被拒绝", text, re.I):
        return ""
    sentences = re.split(r"(?<=[。！？])|(?<=[.!?])\s+", text)
    result = " ".join(sentences[:3]).strip()
    if len(result) > 500:
        result = result[:499].rsplit(" ", 1)[0] + "…" if " " in result[:499] else result[:499] + "…"
    return result


def extract_excerpt(html: bytes | str, title: str = "") -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(tag.string or tag.get_text())
        except (ValueError, TypeError):
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in list(nodes):
            if isinstance(node, dict):
                nodes.extend(node.get("@graph", []) if isinstance(node.get("@graph"), list) else [])
        for node in nodes:
            if not isinstance(node, dict):
                continue
            kind = node.get("@type", "")
            kinds = kind if isinstance(kind, list) else [kind]
            if not any(k in {"Article", "NewsArticle", "BlogPosting"} for k in kinds):
                continue
            for field in ("description", "articleBody"):
                value = node.get(field)
                result = excerpt(value, title) if isinstance(value, str) else ""
                if result:
                    return result, "source_description" if field == "description" else "article_excerpt"
    for node in soup.select("script, style, nav, footer, aside, form"):
        node.decompose()
    article = soup.select_one("article, [itemprop='articleBody'], .entry-content, .article-content")
    if article:
        paragraphs = [node.get_text(" ", strip=True) for node in article.select("p") if len(node.get_text(strip=True)) >= 30]
        result = excerpt(" ".join(paragraphs[:3]), title)
        if result:
            return result, "article_excerpt"
    for selector in ('meta[property="og:description"]', 'meta[name="description"]'):
        node = soup.select_one(selector)
        value = str(node.get("content") or "") if node else ""
        result = excerpt(value, title)
        # Generic landing-page descriptions are not article summaries.
        if result and not re.search(r"最新资讯|一站式|关注我们|subscribe to|sign up for", result, re.I):
            return result, "source_description"
    return "", ""


def public_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.path in ("", "/"):
            return False
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(row[4][0]).is_global for row in addresses)
    except (OSError, ValueError):
        return False


def fetch_excerpt(session: requests.Session, url: str, title: str) -> tuple[str, str]:
    for _ in range(4):
        if not public_url(url):
            return "", ""
        with session.get(url, timeout=10, stream=True, allow_redirects=False) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers.get("Location", ""))
                continue
            if response.status_code != 200 or "html" not in response.headers.get("Content-Type", "").lower():
                return "", ""
            chunks, size = [], 0
            for chunk in response.iter_content(8192):
                size += len(chunk)
                if size > 512 * 1024:
                    return "", ""
                chunks.append(chunk)
            return extract_excerpt(b"".join(chunks), title)
    return "", ""


def enrich(data_dir: Path, max_fetch: int = 40, max_translate: int = 20) -> dict[str, int]:
    try:
        from scripts.update_news import create_session, translate_to_zh_cn
        from scripts.build_topics import DOMESTIC_TOPIC_IDS, load_topic_config, record_matches_topic, parse_time, write_topics_payload
    except ModuleNotFoundError:
        from update_news import create_session, translate_to_zh_cn
        from build_topics import DOMESTIC_TOPIC_IDS, load_topic_config, record_matches_topic, parse_time, write_topics_payload
    archive = json.loads((data_dir / "archive.json").read_text())
    config = load_topic_config(Path(__file__).resolve().parents[1] / "config/topics.json")
    topics = [t for t in config["topics"] if t.get("group") == "company"]
    domestic_topics = [t for t in topics if t["id"] in DOMESTIC_TOPIC_IDS]
    now = datetime.now(timezone.utc)
    end = parse_time(archive.get("generated_at")) or now
    cache_path = data_dir / "news-summary-cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    counts = {"fetched": 0, "translated": 0, "available": 0}
    seen = set()
    with create_session() as session:
        for row in sorted(archive.get("items", []), key=lambda x: (any(record_matches_topic(x,t) for t in domestic_topics), focus_priority(x), str(x.get("published_at") or "")), reverse=True):
            url, title = row.get("url", ""), row.get("title", "")
            stamp = parse_time(row.get("published_at"))
            if url in seen or not stamp or not end - timedelta(days=30) <= stamp <= end:
                continue
            if not focus_priority(row) and not any(record_matches_topic(row, t) for t in topics):
                continue
            seen.add(url)
            saved = cache.get(url, {})
            summary = excerpt(str(row.get("summary") or saved.get("summary_original") or ""), title)
            origin = saved.get("summary_origin", "source_description")
            checked = parse_time(saved.get("checked_at"))
            if not summary and urlparse(url).hostname in ALLOWED_HOSTS and counts["fetched"] < max_fetch and (not checked or now - checked >= timedelta(days=1)):
                counts["fetched"] += 1
                try:
                    summary, origin = fetch_excerpt(session, url, title)
                except (requests.RequestException, ValueError):
                    summary, origin = "", ""
                saved = {"checked_at": now.isoformat()}
            if not summary:
                if saved:
                    cache[url] = saved
                continue
            translated = saved.get("summary_zh", "")
            if len(re.findall(r"[一-鿿]", summary)) >= max(4, len(re.findall(r"[A-Za-z]", summary)) * .15):
                translated = summary
            elif not translated and counts["translated"] < max_translate:
                counts["translated"] += 1
                translated = translate_to_zh_cn(session, summary) or ""
            cache[url] = {**saved, "summary_original": summary, "summary_zh": translated,
                          "summary_origin": origin, "updated_at": now.isoformat()}
            counts["available"] += 1
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n")
    write_topics_payload(data_dir)
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--max-fetch", type=int, default=40)
    parser.add_argument("--max-translate", type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(enrich(args.data_dir, max(0, args.max_fetch), max(0, args.max_translate))))
