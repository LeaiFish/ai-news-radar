"""Link follow-up stories without a second merge or an LLM grouper.

Same-story merge stays in ``merge_story_items`` (canonical URL, or a very
similar title inside a short window). This pass only hangs a later story
under an earlier parent when the titles share a vendor or model and are
related, but were not merged into one story.

Every story gets:

- ``relation``: ``primary`` or ``follow_up``
- ``parent_story_id`` / ``follow_up_of`` on a follow-up
- ``follow_ups`` / ``follow_up_count`` on the parent
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

FOLLOW_UP_WINDOW_HOURS = 48
# Below the same-story title merge threshold (0.86). Shared entity + this
# much title overlap is enough to call the later story progress.
FOLLOW_UP_MIN_VENDOR_SIMILARITY = 0.55
FOLLOW_UP_MIN_MODEL_SIMILARITY = 0.5
FOLLOW_UP_MIN_ENTITY_SIMILARITY = 0.34
FOLLOW_UP_MIN_TOKENS = 3


def _tools():
    try:
        from scripts.update_news import normalized_story_title, title_entities, title_similarity, title_tokens
    except ModuleNotFoundError:  # pragma: no cover - direct script execution
        from update_news import normalized_story_title, title_entities, title_similarity, title_tokens

    return normalized_story_title, title_entities, title_similarity, title_tokens


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


def story_anchor_time(story: dict[str, Any]) -> datetime | None:
    for key in ("earliest_at", "latest_at", "published_at"):
        parsed = _parse_time(story.get(key))
        if parsed:
            return parsed
    primary = story.get("primary_item")
    if isinstance(primary, dict):
        return _parse_time(primary.get("published_at"))
    return None


def follow_up_signal(earlier: dict[str, Any], later: dict[str, Any]) -> dict[str, Any] | None:
    """Return a relation payload when ``later`` is progress on ``earlier``.

    Requires a shared vendor or model, a time gap inside
    ``FOLLOW_UP_WINDOW_HOURS``, and title overlap below the same-story merge.
    Vendor-only overlap still needs a clearer title match so two unrelated
    posts from the same company stay separate.
    """
    normalized_story_title, title_entities, title_similarity, title_tokens = _tools()
    title_a = normalized_story_title(earlier)
    title_b = normalized_story_title(later)
    if len(title_tokens(title_a)) < FOLLOW_UP_MIN_TOKENS or len(title_tokens(title_b)) < FOLLOW_UP_MIN_TOKENS:
        return None
    time_a = story_anchor_time(earlier)
    time_b = story_anchor_time(later)
    if time_a is None or time_b is None:
        return None
    delta_hours = abs((time_b - time_a).total_seconds()) / 3600
    if delta_hours > FOLLOW_UP_WINDOW_HOURS:
        return None

    vendors_a, models_a = title_entities(title_a)
    vendors_b, models_b = title_entities(title_b)
    shared_vendors = vendors_a & vendors_b
    shared_models = models_a & models_b
    if vendors_a and vendors_b and vendors_a.isdisjoint(vendors_b):
        return None
    if not shared_vendors and not shared_models:
        return None

    similarity = float(title_similarity(title_a, title_b))
    # Already the same headline. Same-story merge owns that case.
    if similarity >= 0.86:
        return None
    if shared_vendors and shared_models and similarity >= FOLLOW_UP_MIN_ENTITY_SIMILARITY:
        reason = "shared_entity"
    elif shared_models and similarity >= FOLLOW_UP_MIN_MODEL_SIMILARITY:
        reason = "title_and_model"
    elif shared_vendors and similarity >= FOLLOW_UP_MIN_VENDOR_SIMILARITY:
        reason = "title_and_vendor"
    else:
        return None
    return {"reason": reason, "similarity": round(similarity, 4)}


def _clear_relation(story: dict[str, Any]) -> None:
    story["relation"] = "primary"
    story["parent_story_id"] = None
    story["follow_up_of"] = None
    story["follow_up_count"] = 0
    story["follow_ups"] = []


def link_story_follow_ups(stories: list[Any]) -> list[Any]:
    """Hang clear follow-ups under the earliest story in the chain.

    Returns the same list. Stories that are not dicts are left untouched.
    """
    usable = [story for story in stories if isinstance(story, dict) and story.get("story_id")]
    for story in usable:
        _clear_relation(story)

    ordered = sorted(
        usable,
        key=lambda story: (
            story_anchor_time(story) or datetime.max.replace(tzinfo=timezone.utc),
            str(story.get("story_id") or ""),
        ),
    )
    parent_of: dict[str, str] = {}
    signal_of: dict[str, dict[str, Any]] = {}

    def root_id(story_id: str) -> str:
        seen: set[str] = set()
        current = story_id
        while current in parent_of and current not in seen:
            seen.add(current)
            current = parent_of[current]
        return current

    for index, story in enumerate(ordered):
        story_id = str(story.get("story_id") or "")
        best_parent = ""
        best_signal: dict[str, Any] | None = None
        best_similarity = -1.0
        for earlier in ordered[:index]:
            signal = follow_up_signal(earlier, story)
            if signal is None:
                continue
            similarity = float(signal["similarity"])
            if similarity > best_similarity:
                best_similarity = similarity
                best_parent = str(earlier.get("story_id") or "")
                best_signal = signal
        if not best_parent or best_parent == story_id or best_signal is None:
            continue
        root = root_id(best_parent)
        if not root or root == story_id:
            continue
        parent_of[story_id] = root
        signal_of[story_id] = best_signal

    by_id = {str(story.get("story_id") or ""): story for story in ordered}
    children: dict[str, list[dict[str, Any]]] = {}
    for story in ordered:
        story_id = str(story.get("story_id") or "")
        parent_id = parent_of.get(story_id)
        if not parent_id or parent_id not in by_id:
            continue
        signal = signal_of.get(story_id) or {}
        parent = by_id[parent_id]
        story["relation"] = "follow_up"
        story["parent_story_id"] = parent_id
        story["follow_up_of"] = {
            "story_id": parent_id,
            "title": parent.get("title"),
            "reason": signal.get("reason"),
            "similarity": signal.get("similarity"),
        }
        children.setdefault(parent_id, []).append(
            {
                "story_id": story_id,
                "title": story.get("title"),
                "url": story.get("url") or story.get("primary_url"),
                "latest_at": story.get("latest_at") or story.get("earliest_at"),
                "reason": signal.get("reason"),
                "similarity": signal.get("similarity"),
            }
        )

    for parent_id, follow_ups in children.items():
        parent = by_id.get(parent_id)
        if parent is None:
            continue
        parent["follow_ups"] = follow_ups
        parent["follow_up_count"] = len(follow_ups)
    return stories
