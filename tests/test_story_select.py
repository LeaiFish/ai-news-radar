"""Deterministic fixtures for the daily 精选 tier cap."""

from __future__ import annotations

from scripts.story_select import (
    ALL_TIER,
    SELECTED_STORY_LIMIT,
    SELECTED_TIER,
    assign_selection_tiers,
    story_is_selection_candidate,
)
from scripts.update_news import build_daily_brief_payload


COMPANY = [
    {
        "id": "openai",
        "group": "company",
        "keywords": ["OpenAI", "ChatGPT"],
        "exclude": ["openai gym"],
    }
]
LENS = [
    {
        "id": "monetization",
        "group": "lens",
        "keywords": ["订阅", "定价"],
    }
]


def story(
    story_id: str,
    *,
    title: str = "Quiet local note",
    source_count: int = 1,
    importance_score: float = 0.2,
    importance_label: str = "值得关注",
) -> dict:
    return {
        "story_id": story_id,
        "title": title,
        "source": "Example",
        "source_name": "Example",
        "source_count": source_count,
        "importance_score": importance_score,
        "importance": importance_score,
        "score": importance_score,
        "importance_label": importance_label,
    }


def assign(stories: list[dict], *, limit: int = SELECTED_STORY_LIMIT) -> list[dict]:
    return assign_selection_tiers(
        stories,
        limit=limit,
        company_topics=COMPANY,
        lens_topics=LENS,
    )


def selected_ids(stories: list[dict]) -> list[str]:
    return [item["story_id"] for item in stories if item.get("tier") == SELECTED_TIER]


def test_company_lens_labels_and_multi_source_are_candidates():
    cases = [
        story("company", title="OpenAI ships a desktop app"),
        story("lens", title="模型订阅涨价"),
        story("official", importance_label="官方更新"),
        story("heat", importance_label="多源热议"),
        story("multi", source_count=2),
    ]
    for item in cases:
        assert story_is_selection_candidate(item, COMPANY, LENS)

    quiet = story("quiet", title="周末菜谱", importance_label="行业动态")
    assert not story_is_selection_candidate(quiet, COMPANY, LENS)


def test_company_exclude_does_not_match():
    item = story("gym", title="openai gym tutorial")
    assert not story_is_selection_candidate(item, COMPANY, LENS)


def test_cap_ranks_by_source_count_then_importance_score():
    stories = [
        story("low-multi", source_count=2, importance_score=0.99),
        story("top-heat", source_count=4, importance_score=0.1),
        story("mid-heat", source_count=3, importance_score=0.4),
        story("company", title="ChatGPT desktop", source_count=1, importance_score=0.95),
        story("quiet", title="周末菜谱"),
    ]
    # Twenty extra multi-source stories so the cap has to drop someone.
    for index in range(20):
        stories.append(story(f"fill-{index:02d}", source_count=2, importance_score=0.3 + index / 1000))

    assign(stories, limit=15)

    picked = set(selected_ids(stories))
    assert len(picked) == 15
    assert {"top-heat", "mid-heat", "low-multi"} <= picked
    assert "company" not in picked
    assert "quiet" not in picked
    # Among source_count == 2, the lowest scores fall outside the cap.
    assert {f"fill-{index:02d}" for index in range(8)}.isdisjoint(picked)
    assert {f"fill-{index:02d}" for index in range(8, 20)} <= picked


def test_fewer_than_cap_keeps_every_candidate_and_marks_the_rest_all():
    stories = [
        story("official", importance_label="官方更新", importance_score=0.4),
        story("lens", title="企业版定价调整", importance_score=0.9),
        story("quiet", title="城市天气"),
    ]
    assign(stories)

    assert set(selected_ids(stories)) == {"lens", "official"}
    assert stories[2]["tier"] == ALL_TIER


def test_tie_breaks_on_story_id_then_input_order():
    stories = [
        story("b", source_count=2, importance_score=0.5),
        story("a", source_count=2, importance_score=0.5),
        story("a", source_count=2, importance_score=0.5),
    ]
    assign(stories, limit=2)

    assert [item["tier"] for item in stories] == [ALL_TIER, SELECTED_TIER, SELECTED_TIER]


def test_importance_score_falls_back_to_score_field():
    first = story("plain", source_count=1, importance_label="官方更新")
    first.pop("importance_score")
    first.pop("importance")
    first["score"] = 0.2
    hotter = story("hotter", source_count=1, importance_label="官方更新", importance_score=0.8)
    stories = [first, hotter]
    assign(stories, limit=1)

    assert selected_ids(stories) == ["hotter"]


def test_real_topic_config_matches_company_and_lens_keywords():
    stories = [
        story("openai", title="OpenAI updates ChatGPT"),
        story("lens", title="办公套件接入 Copilot"),
        story("noise", title="周末菜场营业时间", importance_label="行业动态"),
        story("pie", title="apple pie recipe", importance_label="值得关注"),
    ]
    assign_selection_tiers(stories)

    assert set(selected_ids(stories)) == {"openai", "lens"}
    assert stories[2]["tier"] == ALL_TIER
    assert stories[3]["tier"] == ALL_TIER


def test_assigning_tiers_does_not_leak_into_daily_brief_objects():
    stories = [
        story("brief-me", title="OpenAI ships Codex", source_count=2, importance_score=0.9),
        story("also", title="Claude subscription pricing", source_count=1, importance_score=0.8, importance_label="官方更新"),
    ]
    brief = build_daily_brief_payload(stories, generated_at="2026-09-23T00:00:00Z", window_hours=24)
    copies = [dict(item) for item in stories]
    assign(copies)

    assert all("tier" not in item for item in brief["items"])
    assert all(item["tier"] in {SELECTED_TIER, ALL_TIER} for item in copies)
    assert all("tier" not in item for item in stories)
