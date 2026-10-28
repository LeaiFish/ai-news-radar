"""User-selected public sources: processing priority, independent of trust tiers."""
from functools import lru_cache
import json
import re
from pathlib import Path
from urllib.parse import urlparse

CATALOG = Path(__file__).resolve().parents[1] / "config/focus_sources.json"


def normalize_name(value):
    return re.sub(r"[^a-z0-9一-鿿]", "", str(value or "").casefold())


@lru_cache(maxsize=1)
def load_sources():
    return json.loads(CATALOG.read_text(encoding="utf-8"))["sources"]


@lru_cache(maxsize=1)
def load_supplemental_sources():
    return json.loads(CATALOG.read_text(encoding="utf-8")).get("supplemental_sources", [])


def url_parts(value):
    parsed = urlparse(str(value or ""))
    host = (parsed.hostname or "").casefold().removeprefix("www.")
    if host == "twitter.com":
        host = "x.com"
    return host, parsed.path.rstrip("/").casefold()


@lru_cache(maxsize=1)
def source_rules():
    return [
        (row, {normalize_name(alias) for alias in row.get("aliases", [])},
         [url_parts(url) for url in row.get("match_urls", [row.get("source_url")]) if url])
        for row in load_sources() + load_supplemental_sources()
    ]


def matched_sources(record):
    refs = [record]
    if isinstance(record.get("primary_item"), dict):
        refs.append(record["primary_item"])
    names = {normalize_name(row.get(key)) for row in refs for key in ("source", "source_name", "site_name") if row.get(key)}
    urls = [url_parts(row.get(key)) for row in refs for key in ("url", "primary_url") if row.get(key)]
    matches = []
    for source, aliases, targets in source_rules():
        by_url = any(host == target_host and (not prefix or path == prefix or path.startswith(prefix + "/"))
                     for host, path in urls for target_host, prefix in targets)
        if aliases.intersection(names) or by_url:
            matches.append(source)
    return matches


def focus_priority(record):
    matches = matched_sources(record)
    return 4 - min(source["authority"] for source in matches) if matches else 0
