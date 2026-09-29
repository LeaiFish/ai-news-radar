"""Daily 精选 cap for stories-merged.

Writes ``tier`` onto each story:

- ``selected``: at most ``SELECTED_STORY_LIMIT`` candidates
- ``all``: every other story

A story is a candidate when any of these hold:

- it matches a company topic in ``config/topics.json`` (core companies, including
  the overseas benchmarks tracked on the competition overview)
- it matches a lens topic (the four industry lenses)
- ``importance_label`` is ``官方更新`` or ``多源热议``
- ``source_count`` is at least 2

T2 sources (media, personal, unknown) use a soft gate: topic match alone is
not enough. They still need a strong signal (``官方更新``, ``多源热议``, or
``source_count`` >= 2). T1 and T1_5 keep the topic path. If the soft gate
would leave 精选 empty, the previous candidate rules fill it.

Candidates are ranked by independent-source heat, then select tier, then
``importance_score``. Heat counts each distinct outlet once inside 48 hours.
A contribution older than 24 hours has half weight, and the same outlet or
the same URL cannot add a second point. T1 / T1_5 add a small heat bonus so
they rise when other signals are close. ``story_id`` then input order break
remaining ties so the same input always picks the same fifteen.

This does not choose ``daily-brief.json`` items. Callers that share story
objects with the brief should pass copies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

try:
    from scripts.story_archive import load_company_and_lens_topics, match_story_topic_ids
except ModuleNotFoundError:  # pragma: no cover - direct `python scripts/story_select.py`
    from story_archive import load_company_and_lens_topics, match_story_topic_ids

try:
    from scripts.source_tiers import (
        SELECT_TIER_HEAT_BONUS,
        SELECT_TIER_RANK,
        SELECT_TIER_T2,
        best_select_tier,
        item_select_tier,
        source_identity,
    )
except ModuleNotFoundError:  # pragma: no cover - direct `python scripts/story_select.py`
    from source_tiers import (
        SELECT_TIER_HEAT_BONUS,
        SELECT_TIER_RANK,
        SELECT_TIER_T2,
        best_select_tier,
        item_select_tier,
        source_identity,
    )

SELECTED_TIER = "selected"
ALL_TIER = "all"
SELECTED_STORY_LIMIT = 15
HIGH_IMPORTANCE_LABELS = frozenset({"官方更新", "多源热议"})
HEAT_WINDOW_HOURS = 48
HEAT_FRESH_HOURS = 24
FOLLOW_UP_HEAT_PENALTY = 0.2
_HEAT_QUERY_DROPS = {"ref", "fbclid", "gclid", "spm"}


def story_source_count(story: dict[str, Any]) -> int:
    try:
        return int(story.get("source_count") or 0)
    except (TypeError, ValueError):
        return 0


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def heat_url_key(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
    except Exception:
        return raw.lower()
    if not parsed.scheme and not parsed.netloc:
        return raw.lower()
    query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in _HEAT_QUERY_DROPS:
            continue
        query.append((key, value))
    parsed = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        fragment="",
        query=urlencode(query),
    )
    return urlunparse(parsed).rstrip("/").lower()


def _story_source_refs(story: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("sources", "items"):
        refs = story.get(key)
        if isinstance(refs, list) and refs:
            return [ref for ref in refs if isinstance(ref, dict)]
    return []


def _ref_has_tier_signal(ref: dict[str, Any]) -> bool:
    return bool(
        ref.get("select_tier")
        or ref.get("site_id")
        or ref.get("source")
        or ref.get("source_name")
        or ref.get("feed_url")
        or ref.get("handle")
    )


def story_select_tier(story: dict[str, Any]) -> str:
    """Best select tier across the story's sources. Unknown stays T2."""
    tiers: list[Any] = []
    for ref in _story_source_refs(story):
        if _ref_has_tier_signal(ref):
            tiers.append(item_select_tier(ref))
    primary = story.get("primary_item")
    if isinstance(primary, dict) and _ref_has_tier_signal(primary):
        tiers.append(item_select_tier(primary))
    if not tiers and story.get("select_tier"):
        tiers.append(story.get("select_tier"))
    if not tiers:
        return SELECT_TIER_T2
    return best_select_tier(tiers)


def _contribution_weight(published: datetime | None, now: datetime) -> float | None:
    if published is None:
        return 1.0
    age_hours = (now - published).total_seconds() / 3600
    if age_hours > HEAT_WINDOW_HOURS:
        return None
    if age_hours > HEAT_FRESH_HOURS:
        return 0.5
    return 1.0


def independent_source_heat(story: dict[str, Any], now: datetime | None = None) -> float:
    """Distinct-outlet heat inside 48h. Same outlet or same URL counts once.

    Fresh contributions (24h or newer, or a missing timestamp) weigh 1.
    Contributions older than 24h and still inside 48h weigh 0.5.
    When the story has no source list, ``source_count`` is treated as that
    many fresh distinct outlets so older fixtures keep a stable rank.
    """
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    refs = _story_source_refs(story)
    if not refs:
        return float(story_source_count(story))

    candidates: list[tuple[float, str, str]] = []
    for ref in refs:
        weight = _contribution_weight(_parse_time(ref.get("published_at")), clock)
        if weight is None:
            continue
        identity = source_identity(ref)
        url_key = heat_url_key(str(ref.get("url") or ""))
        if not identity and not url_key:
            continue
        candidates.append((weight, identity, url_key))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))

    seen_outlets: set[str] = set()
    seen_urls: set[str] = set()
    heat = 0.0
    for weight, identity, url_key in candidates:
        if identity and identity in seen_outlets:
            continue
        if url_key and url_key in seen_urls:
            continue
        if identity:
            seen_outlets.add(identity)
        if url_key:
            seen_urls.add(url_key)
        heat += weight
    return heat


def selection_rank_heat(story: dict[str, Any], now: datetime | None = None) -> float:
    heat = independent_source_heat(story, now)
    tier = story_select_tier(story)
    heat += float(SELECT_TIER_HEAT_BONUS.get(tier, 0.0))
    if str(story.get("relation") or "") == "follow_up":
        heat -= FOLLOW_UP_HEAT_PENALTY
    return heat


def story_importance_score(story: dict[str, Any]) -> float:
    raw = story.get("importance_score")
    if raw is None:
        raw = story.get("importance")
    if raw is None:
        raw = story.get("score")
    try:
        return float(raw or 0)
    except (TypeError, ValueError):
        return 0.0


def story_has_strong_signal(story: dict[str, Any]) -> bool:
    label = str(story.get("importance_label") or "").strip()
    if label in HIGH_IMPORTANCE_LABELS:
        return True
    return story_source_count(story) >= 2


def story_matches_topic(
    story: dict[str, Any],
    company_topics: list[dict[str, Any]],
    lens_topics: list[dict[str, Any]],
) -> bool:
    if not company_topics and not lens_topics:
        return False
    company_ids, lens_ids = match_story_topic_ids(story, company_topics, lens_topics)
    return bool(company_ids or lens_ids)


def story_is_selection_candidate(
    story: dict[str, Any],
    company_topics: list[dict[str, Any]],
    lens_topics: list[dict[str, Any]],
    *,
    tier_gate: bool = True,
) -> bool:
    strong = story_has_strong_signal(story)
    topic = story_matches_topic(story, company_topics, lens_topics)
    if tier_gate and story_select_tier(story) == SELECT_TIER_T2:
        return strong
    return strong or topic


def _selection_rank(story: dict[str, Any], index: int, now: datetime) -> tuple[float, int, float, str, int]:
    tier = story_select_tier(story)
    return (
        -selection_rank_heat(story, now),
        int(SELECT_TIER_RANK.get(tier, SELECT_TIER_RANK[SELECT_TIER_T2])),
        -story_importance_score(story),
        str(story.get("story_id") or ""),
        index,
    )


def assign_selection_tiers(
    stories: list[Any],
    *,
    limit: int = SELECTED_STORY_LIMIT,
    company_topics: list[dict[str, Any]] | None = None,
    lens_topics: list[dict[str, Any]] | None = None,
    topics_config: Path | None = None,
    now: datetime | None = None,
) -> list[Any]:
    """Set ``tier`` on each story dict. Returns the same list."""
    if company_topics is None or lens_topics is None:
        loaded_company, loaded_lens = load_company_and_lens_topics(topics_config)
        if company_topics is None:
            company_topics = loaded_company
        if lens_topics is None:
            lens_topics = loaded_lens

    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)

    cap = max(0, int(limit))
    indexed = [(story, index) for index, story in enumerate(stories) if isinstance(story, dict)]
    candidates = [
        pair
        for pair in indexed
        if story_is_selection_candidate(pair[0], company_topics, lens_topics, tier_gate=True)
    ]
    if not candidates:
        candidates = [
            pair
            for pair in indexed
            if story_is_selection_candidate(pair[0], company_topics, lens_topics, tier_gate=False)
        ]
    candidates.sort(key=lambda pair: _selection_rank(pair[0], pair[1], clock))
    selected_object_ids = {id(story) for story, _index in candidates[:cap]}

    for story in stories:
        if not isinstance(story, dict):
            continue
        story["select_tier"] = story_select_tier(story)
        story["source_heat"] = round(independent_source_heat(story, clock), 4)
        story["tier"] = SELECTED_TIER if id(story) in selected_object_ids else ALL_TIER
    return stories
