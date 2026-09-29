"""Deterministic fixtures for the daily 精选 tier cap."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scripts.story_select import (
    ALL_TIER,
    SELECTED_STORY_LIMIT,
    SELECTED_TIER,
    assign_selection_tiers,
    independent_source_heat,
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
    select_tier: str | None = None,
) -> dict:
    row = {
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
    if select_tier:
        row["select_tier"] = select_tier
    return row


def assign(stories: list[dict], *, limit: int = SELECTED_STORY_LIMIT, now=None) -> list[dict]:
    return assign_selection_tiers(
        stories,
        limit=limit,
        company_topics=COMPANY,
        lens_topics=LENS,
        now=now,
    )


def selected_ids(stories: list[dict]) -> list[str]:
    return [item["story_id"] for item in stories if item.get("tier") == SELECTED_TIER]


def test_company_lens_labels_and_multi_source_are_candidates():
    cases = [
        story("company", title="OpenAI ships a desktop app", select_tier="T1"),
        story("near", title="OpenAI ships a desktop app", select_tier="T1_5"),
        story("lens", title="模型订阅涨价", select_tier="T1"),
        story("official", importance_label="官方更新"),
        story("heat", importance_label="多源热议"),
        story("multi", source_count=2),
    ]
    for item in cases:
        assert story_is_selection_candidate(item, COMPANY, LENS)

    media_company = story("media-company", title="OpenAI ships a desktop app")
    assert not story_is_selection_candidate(media_company, COMPANY, LENS)

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
        story("lens", title="企业版定价调整", importance_score=0.9, select_tier="T1"),
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
    # Single-source topic matches are T2, so the soft gate would skip them.
    # With nothing stronger in the pool, 精选 falls back and still keeps them.
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


NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


def sourced(story_id: str, refs: list[dict], **kwargs) -> dict:
    row = story(story_id, source_count=kwargs.pop("source_count", len(refs)), **kwargs)
    row["sources"] = refs
    return row


def ref(name: str, url: str, *, hours_ago: int = 1, tier: str = "T2", site_id: str = "curated_media") -> dict:
    published = (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "source": name,
        "site_id": site_id,
        "url": url,
        "published_at": published,
        "select_tier": tier,
    }


def test_heat_counts_each_outlet_once_and_halves_after_24h():
    single = sourced("one", [ref("The Verge", "https://verge.example/a")])
    assert independent_source_heat(single, NOW) == 1

    repeated = sourced(
        "repeat",
        [
            ref("TechCrunch", "https://tc.example/1", hours_ago=1),
            ref("TechCrunch", "https://tc.example/2", hours_ago=2),
            ref("TechCrunch", "https://tc.example/1?utm_source=rss", hours_ago=30),
        ],
    )
    assert independent_source_heat(repeated, NOW) == 1

    mixed = sourced(
        "mixed",
        [
            ref("The Verge", "https://verge.example/fresh"),
            ref("The Decoder", "https://decoder.example/stale", hours_ago=30),
            ref("Wired", "https://wired.example/old", hours_ago=60),
        ],
    )
    assert independent_source_heat(mixed, NOW) == 1.5

    same_url = sourced(
        "syndicated",
        [
            ref("The Verge", "https://openai.com/news/gpt-5"),
            ref("TechCrunch", "https://openai.com/news/gpt-5?ref=feed"),
        ],
    )
    assert independent_source_heat(same_url, NOW) == 1


def test_tier_bonus_lifts_official_when_heat_is_close_but_not_when_heat_is_wider():
    official = sourced(
        "official",
        [
            ref("OpenAI News", "https://openai.com/a", tier="T1", site_id="official_ai"),
            ref("Anthropic News", "https://anthropic.com/a", tier="T1", site_id="official_ai"),
        ],
        importance_score=0.2,
    )
    media = sourced(
        "media",
        [
            ref("The Verge", "https://verge.example/a"),
            ref("TechCrunch", "https://tc.example/a"),
        ],
        importance_score=0.99,
    )
    wide_media = sourced(
        "wide",
        [ref(name, f"https://media.example/{name}", tier="T2") for name in ("A", "B", "C", "D")],
        importance_score=0.3,
    )
    stories = [media, official, wide_media]
    assign(stories, limit=3, now=NOW)
    assert set(selected_ids(stories)) == {"official", "media", "wide"}
    # Re-rank with a cap of 2: four distinct T2 outlets stay ahead of two T1 outlets,
    # and those two T1 outlets stay ahead of two T2 outlets with a higher score.
    assign(stories, limit=2, now=NOW)
    assert set(selected_ids(stories)) == {"wide", "official"}


def test_equal_rank_heat_prefers_better_tier_over_importance():
    official = sourced(
        "official",
        [ref("OpenAI News", "https://openai.com/only", tier="T1", site_id="official_ai")],
        importance_score=0.1,
    )
    media = sourced(
        "media",
        [
            ref("The Verge", "https://verge.example/fresh"),
            ref("The Decoder", "https://decoder.example/stale", hours_ago=30),
        ],
        importance_score=0.99,
    )
    assign([official, media], limit=1, now=NOW)
    assert selected_ids([official, media]) == ["official"]


def test_follow_up_ranks_below_its_parent_when_heat_matches():
    parent = story("parent", source_count=2, importance_score=0.4)
    child = story("child", source_count=2, importance_score=0.9)
    child["relation"] = "follow_up"
    assign([child, parent], limit=1)
    assert selected_ids([child, parent]) == ["parent"]


def test_t2_topic_only_fills_selection_only_when_nothing_stronger_exists():
    alone = [story("only", title="OpenAI desktop app")]
    assign(alone)
    assert selected_ids(alone) == ["only"]

    mixed = [
        story("media", title="OpenAI desktop app", importance_score=0.99),
        story("official", importance_label="官方更新", importance_score=0.1),
    ]
    assign(mixed)
    assert selected_ids(mixed) == ["official"]
