from scripts.focus_sources import load_sources, matched_sources, focus_priority


def test_catalog_preserves_48_user_channels_and_wechat_identity():
    rows = load_sources()
    assert len(rows) == 48
    assert len({row["id"] for row in rows}) == 48
    assert all(row["authority"] in {1, 2, 3} for row in rows)
    app = next(row for row in rows if row["name"] == "千问")
    lab = next(row for row in rows if row["name"] == "通义实验室")
    assert app["account_name"] == "千问APP"
    assert lab["account_name"] == "通义实验室"


def test_x_handle_matching_is_exact_and_accepts_legacy_twitter_host():
    record = {"url": "https://twitter.com/OpenAIDevs/status/123"}
    assert [row["name"] for row in matched_sources(record)] == ["OpenAI Developers"]
    assert not matched_sources({"url": "https://x.com/OpenAIDevsFake/status/123"})
    assert not matched_sources({"url": "https://x.com.attacker.example/OpenAIDevs/status/123"})


def test_github_platform_is_not_a_blanket_priority_source():
    assert focus_priority({"url": "https://github.com/huggingface/open-r1/releases"}) == 3
    assert focus_priority({"url": "https://github.com/unrelated/project"}) == 0


def test_user_priority_does_not_promote_every_aggregator_item():
    assert focus_priority({"source": "TechCrunch AI"}) == 2
    assert focus_priority({"source": "AI HOT", "url": "https://unrelated.example/news"}) == 0
