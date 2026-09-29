"""select_tier lookup: explicit value, name, handle, feed URL, site, then T2."""

from __future__ import annotations

from scripts.source_tiers import item_select_tier, normalize_select_tier, resolve_select_tier
from scripts.update_news import CURATED_AI_MEDIA_FEEDS, OFFICIAL_AI_FEEDS, parse_opml_subscriptions


def test_unknown_source_defaults_to_t2():
    assert resolve_select_tier(site_id="not-a-site", source="Some Newsletter") == "T2"
    assert normalize_select_tier("nope") is None
    assert normalize_select_tier("t1.5") == "T1_5"


def test_builtin_feeds_match_the_config_file():
    for feed in OFFICIAL_AI_FEEDS:
        assert feed["select_tier"] == "T1"
        assert resolve_select_tier(feed_url=feed["xml_url"], site_id="curated_media") == "T1"
        assert resolve_select_tier(source=feed["title"], site_id="curated_media") == "T1"
    for feed in CURATED_AI_MEDIA_FEEDS:
        assert resolve_select_tier(source=feed["title"], site_id="curated_media") == feed["select_tier"]
        assert resolve_select_tier(feed_url=feed["xml_url"]) == feed["select_tier"]


def test_official_accounts_and_aihot_names():
    assert resolve_select_tier(site_id="aihot", source="Anthropic：Newsroom（网页）") == "T1"
    assert resolve_select_tier(site_id="aihot", source="X：OpenAI Developers (@OpenAIDevs)") == "T1_5"
    assert resolve_select_tier(site_id="followbuilders", handle="OpenAIDevs") == "T1_5"
    assert resolve_select_tier(site_id="followbuilders", handle="karpathy") == "T2"
    assert resolve_select_tier(site_id="official_ai", source="Anything official") == "T1"


def test_explicit_tier_wins_over_site_default():
    assert resolve_select_tier(site_id="official_ai", explicit="T2") == "T2"
    assert item_select_tier({"site_id": "aihot", "source": "TechCrunch AI", "select_tier": "T1"}) == "T1"


def test_example_opml_select_tier_attribute_is_parsed():
    from pathlib import Path

    example = Path(__file__).resolve().parents[1] / "feeds" / "follow.example.opml"
    feeds = parse_opml_subscriptions(example)
    by_title = {feed["title"]: feed for feed in feeds}
    assert by_title["OpenAI News"]["select_tier"] == "T1"
    assert by_title["NVIDIA Generative AI Blog"]["select_tier"] == "T1"
    assert by_title["Simon Willison"]["select_tier"] == "T2"
    assert by_title["宝玉"]["select_tier"] == "T2"
