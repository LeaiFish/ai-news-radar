"""精选 feed reads tier=selected; 全量 and the hot board stay on their existing pools."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def function_body(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    end = source.index("\nfunction ", start + 1)
    return source[start:end]


def test_selected_list_requires_tier_and_hot_board_does_not():
    source = read("assets/app.js")
    selected = function_body(source, "mainListStoriesBase")
    tier_helper = function_body(source, "storyHasSelectedTier")
    hot = function_body(source, "hotBoardStories")
    entries = function_body(source, "mainListEntries")

    assert '=== "selected"' in tier_helper
    assert "storyHasSelectedTier" in selected
    assert "tier" not in hot
    assert 'state.mode === "all"' in entries
    assert "mainListRawItems()" in entries


def test_pipeline_tags_stories_after_the_daily_brief():
    source = read("scripts/update_news.py")
    brief_at = source.index("daily_brief_payload = build_daily_brief_payload")
    tier_at = source.index("assign_selection_tiers(stories_for_feed)")
    merged_at = source.index("stories_merged_payload = build_stories_payload")
    assert brief_at < tier_at < merged_at
    assert "dict(story) for story in stories" in source
