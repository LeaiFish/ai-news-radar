"""Follow-up links stay separate from same-story merge."""

from pathlib import Path

from scripts.story_followups import follow_up_signal, link_story_follow_ups
from scripts.update_news import merge_story_items


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-29T12:00:00Z"


def story(story_id: str, title: str, *, hours_ago: int) -> dict:
    # Anchor times are ISO strings. 12:00Z minus hours.
    hour = 12 - hours_ago
    day = 29
    if hour < 0:
        hour += 24
        day -= 1
    return {
        "story_id": story_id,
        "title": title,
        "url": f"https://example.com/{story_id}",
        "earliest_at": f"2026-09-{day:02d}T{hour:02d}:00:00Z",
        "latest_at": f"2026-09-{day:02d}T{hour:02d}:00:00Z",
    }


def test_shared_model_progress_hangs_under_the_earlier_story():
    parent = story("parent", "OpenAI launches GPT-5 for ChatGPT Plus subscribers", hours_ago=20)
    child = story("child", "OpenAI rolls out GPT-5 API access for developers", hours_ago=2)
    other = story("other", "Anthropic launches Claude 4 coding model for agents", hours_ago=3)

    assert follow_up_signal(parent, child) is not None
    assert follow_up_signal(parent, other) is None

    link_story_follow_ups([child, other, parent])

    assert parent["relation"] == "primary"
    assert parent["follow_up_count"] == 1
    assert parent["follow_ups"][0]["story_id"] == "child"
    assert child["relation"] == "follow_up"
    assert child["parent_story_id"] == "parent"
    assert other["relation"] == "primary"
    assert other["follow_up_count"] == 0


def test_vendor_only_headlines_do_not_cluster():
    earlier = story("a", "OpenAI acquires a hardware startup for consumer devices", hours_ago=10)
    later = story("b", "OpenAI publishes a new cookbook for API users today", hours_ago=1)
    assert follow_up_signal(earlier, later) is None


def test_chain_points_at_the_root_parent():
    first = story("first", "OpenAI launches GPT-5 for ChatGPT Plus subscribers", hours_ago=30)
    second = story("second", "OpenAI rolls out GPT-5 API access for developers", hours_ago=16)
    third = story("third", "OpenAI extends GPT-5 API access for enterprise developers", hours_ago=2)
    link_story_follow_ups([third, first, second])
    assert second["parent_story_id"] == "first"
    assert third["parent_story_id"] == "first"
    assert first["follow_up_count"] == 2
    assert second["follow_up_count"] == 0


def test_same_story_merge_still_collapses_near_duplicate_titles():
    from datetime import datetime, timezone

    now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
    items = [
        {
            "id": "a",
            "site_id": "curated_media",
            "site_name": "Curated Media",
            "source": "The Verge",
            "title": "OpenAI launches GPT-5 for ChatGPT Plus subscribers today",
            "url": "https://www.theverge.com/openai-gpt-5",
            "published_at": "2026-09-29T08:00:00Z",
            "select_tier": "T2",
        },
        {
            "id": "b",
            "site_id": "curated_media",
            "site_name": "Curated Media",
            "source": "TechCrunch AI",
            "title": "OpenAI launches GPT-5 for ChatGPT Plus subscribers today",
            "url": "https://techcrunch.com/openai-gpt-5",
            "published_at": "2026-09-29T09:00:00Z",
            "select_tier": "T2",
        },
    ]
    stories, events = merge_story_items(items, now, 24)
    assert len(stories) == 1
    assert events[0]["reason"] == "title_similarity"
    assert stories[0]["other_source_count"] == 1
    assert stories[0]["relation"] == "primary"


def test_feed_and_workbench_can_show_other_outlets_and_progress():
    app = (ROOT / "assets" / "app.js").read_text(encoding="utf-8")
    workbench = (ROOT / "assets" / "perspective.js").read_text(encoding="utf-8")
    assert "另有" in app and "进展" in app
    assert "follow_up_count" in app
    assert "other_source_count" in app
    assert "另有" in workbench and "进展" in workbench
    assert "follow_up_count" in workbench
