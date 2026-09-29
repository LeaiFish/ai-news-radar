"""Selection tiers for the daily 精选 cap.

T1 is official first-party (company blog, changelog, newsroom). T1_5 is an
official account or near-official channel. T2 is media, personal, aggregator,
or anything not listed. Unknown sources resolve to T2.

This is separate from the display ``source_tier`` labels on items
(官方一手源 / AI垂直源 / …). Those stay in ``SOURCE_TIER_BY_SITE``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SELECT_TIER_T1 = "T1"
SELECT_TIER_T1_5 = "T1_5"
SELECT_TIER_T2 = "T2"
SELECT_TIERS = (SELECT_TIER_T1, SELECT_TIER_T1_5, SELECT_TIER_T2)
SELECT_TIER_RANK = {
    SELECT_TIER_T1: 0,
    SELECT_TIER_T1_5: 1,
    SELECT_TIER_T2: 2,
}
# Added to independent-source heat so an official story rises when heat is close,
# without outranking a clearly wider set of distinct outlets.
SELECT_TIER_HEAT_BONUS = {
    SELECT_TIER_T1: 0.5,
    SELECT_TIER_T1_5: 0.25,
    SELECT_TIER_T2: 0.0,
}

_HANDLE_RE = re.compile(r"@([A-Za-z0-9_]+)")
_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "source_tiers.json"
_CACHE: dict[str, Any] | None = None


def normalize_select_tier(value: Any) -> str | None:
    raw = str(value or "").strip().upper().replace(" ", "")
    if not raw:
        return None
    raw = raw.replace(".", "_").replace("-", "_")
    if raw in {SELECT_TIER_T1, "T1_0"}:
        return SELECT_TIER_T1
    if raw in {SELECT_TIER_T1_5, "T15", "T1_50"}:
        return SELECT_TIER_T1_5
    if raw == SELECT_TIER_T2:
        return SELECT_TIER_T2
    return None


def load_source_tier_config(path: Path | None = None, *, reload: bool = False) -> dict[str, Any]:
    global _CACHE
    if path is None and _CACHE is not None and not reload:
        return _CACHE
    config_path = path or _CONFIG_PATH
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    if path is None:
        _CACHE = payload
    return payload


def _table(config: dict[str, Any], key: str) -> dict[str, Any]:
    raw = config.get(key)
    return raw if isinstance(raw, dict) else {}


def _mapped(table: dict[str, Any], key: str) -> str | None:
    if not key or key not in table:
        return None
    return normalize_select_tier(table.get(key))


def _feed_url_keys(url: str) -> list[str]:
    raw = str(url or "").strip()
    if not raw:
        return []
    keys = [raw]
    stripped = raw.rstrip("/")
    if stripped and stripped not in keys:
        keys.append(stripped)
    return keys


def _handle_keys(source: str, handle: str) -> list[str]:
    found: list[str] = []
    explicit = str(handle or "").strip().lstrip("@").lower()
    if explicit:
        found.append(explicit)
    for match in _HANDLE_RE.findall(str(source or "")):
        key = match.lower()
        if key not in found:
            found.append(key)
    return found


def resolve_select_tier(
    *,
    site_id: str = "",
    source: str = "",
    feed_url: str = "",
    handle: str = "",
    explicit: str = "",
    config: dict[str, Any] | None = None,
) -> str:
    """Resolve one source to T1 / T1_5 / T2.

    Order: explicit value, source name, handle, feed URL, site id, config default.
    """
    cfg = config if config is not None else load_source_tier_config()
    chosen = normalize_select_tier(explicit)
    if chosen:
        return chosen
    chosen = _mapped(_table(cfg, "by_source_name"), str(source or "").strip())
    if chosen:
        return chosen
    handles = _table(cfg, "by_handle")
    for key in _handle_keys(str(source or ""), handle):
        chosen = _mapped(handles, key)
        if chosen:
            return chosen
    feeds = _table(cfg, "by_feed_url")
    for key in _feed_url_keys(feed_url):
        chosen = _mapped(feeds, key)
        if chosen:
            return chosen
    sid = str(site_id or "").strip().lower()
    if sid.startswith("opmlrss"):
        sid = "opmlrss"
    chosen = _mapped(_table(cfg, "by_site_id"), sid)
    if chosen:
        return chosen
    return normalize_select_tier(cfg.get("default")) or SELECT_TIER_T2


def item_select_tier(item: dict[str, Any]) -> str:
    return resolve_select_tier(
        site_id=str(item.get("site_id") or ""),
        source=str(item.get("source") or item.get("source_name") or ""),
        feed_url=str(item.get("feed_url") or ""),
        handle=str(item.get("handle") or ""),
        explicit=str(item.get("select_tier") or ""),
    )


def best_select_tier(tiers: list[Any]) -> str:
    best = SELECT_TIER_T2
    best_rank = SELECT_TIER_RANK[best]
    for value in tiers:
        tier = normalize_select_tier(value)
        if tier is None:
            continue
        rank = SELECT_TIER_RANK[tier]
        if rank < best_rank:
            best = tier
            best_rank = rank
    return best


def source_identity(record: dict[str, Any]) -> str:
    """Stable outlet key. Same media with different URLs still collapses."""
    site = str(record.get("site_id") or "").strip().lower()
    name = re.sub(r"\s+", " ", str(record.get("source") or record.get("source_name") or "").strip().lower())
    if not site and not name:
        return ""
    return f"{site}::{name}"


def distinct_outlet_count(refs: list[Any]) -> int:
    seen: list[str] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        identity = source_identity(ref)
        if identity and identity not in seen:
            seen.append(identity)
    return len(seen)


def other_outlet_count(refs: list[Any]) -> int:
    """Outlets besides the one shown on the card. Same media does not add."""
    distinct = distinct_outlet_count(refs)
    if distinct:
        return max(0, distinct - 1)
    usable = [ref for ref in refs if isinstance(ref, dict)]
    return max(0, len(usable) - 1)


def add_select_tier_fields(record: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    tier = item_select_tier(out)
    out["select_tier"] = tier
    out["select_tier_rank"] = SELECT_TIER_RANK[tier]
    return out


def attach_select_tier(record: dict[str, Any], *, site_id: str, source: str, meta: dict[str, Any] | None) -> None:
    """Stamp a normalized select_tier onto an archive record at ingest."""
    payload = meta if isinstance(meta, dict) else {}
    record["select_tier"] = resolve_select_tier(
        site_id=site_id,
        source=source,
        feed_url=str(payload.get("feed_url") or ""),
        handle=str(payload.get("handle") or ""),
        explicit=str(payload.get("select_tier") or record.get("select_tier") or ""),
    )
