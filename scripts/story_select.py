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

Candidates are ranked by ``source_count`` descending, then ``importance_score``
descending. ``story_id`` then input order break remaining ties so the same
input always picks the same fifteen.

This does not choose ``daily-brief.json`` items. Callers that share story
objects with the brief should pass copies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from scripts.story_archive import load_company_and_lens_topics, match_story_topic_ids
except ModuleNotFoundError:  # pragma: no cover - direct `python scripts/story_select.py`
    from story_archive import load_company_and_lens_topics, match_story_topic_ids

SELECTED_TIER = "selected"
ALL_TIER = "all"
SELECTED_STORY_LIMIT = 15
HIGH_IMPORTANCE_LABELS = frozenset({"官方更新", "多源热议"})


def story_source_count(story: dict[str, Any]) -> int:
    try:
        return int(story.get("source_count") or 0)
    except (TypeError, ValueError):
        return 0


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


def story_is_selection_candidate(
    story: dict[str, Any],
    company_topics: list[dict[str, Any]],
    lens_topics: list[dict[str, Any]],
) -> bool:
    label = str(story.get("importance_label") or "").strip()
    if label in HIGH_IMPORTANCE_LABELS:
        return True
    if story_source_count(story) >= 2:
        return True
    if not company_topics and not lens_topics:
        return False
    company_ids, lens_ids = match_story_topic_ids(story, company_topics, lens_topics)
    return bool(company_ids or lens_ids)


def _selection_rank(story: dict[str, Any], index: int) -> tuple[int, float, str, int]:
    return (
        -story_source_count(story),
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
) -> list[Any]:
    """Set ``tier`` on each story dict. Returns the same list."""
    if company_topics is None or lens_topics is None:
        loaded_company, loaded_lens = load_company_and_lens_topics(topics_config)
        if company_topics is None:
            company_topics = loaded_company
        if lens_topics is None:
            lens_topics = loaded_lens

    cap = max(0, int(limit))
    candidates: list[tuple[dict[str, Any], int]] = []
    for index, story in enumerate(stories):
        if not isinstance(story, dict):
            continue
        if story_is_selection_candidate(story, company_topics, lens_topics):
            candidates.append((story, index))
    candidates.sort(key=lambda pair: _selection_rank(pair[0], pair[1]))
    selected_object_ids = {id(story) for story, _index in candidates[:cap]}

    for story in stories:
        if not isinstance(story, dict):
            continue
        story["tier"] = SELECTED_TIER if id(story) in selected_object_ids else ALL_TIER
    return stories
