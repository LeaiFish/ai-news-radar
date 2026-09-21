from __future__ import annotations

import json
from pathlib import Path

from scripts.build_topics import (
    haystack_text,
    load_topic_config,
    match_topic_items,
    record_matches_topic,
    render_topic_page,
    slim_item,
    term_matches,
    write_topic_pages,
    write_topics_payload,
)


ROOT = Path(__file__).resolve().parents[1]


def topic(**overrides):
    base = {
        "id": "openai",
        "name": "OpenAI / ChatGPT",
        "description": "OpenAI 动态",
        "group": "company",
        "keywords": ["OpenAI", "ChatGPT", "GPT-5"],
        "pools": ["stories", "brief", "latest"],
    }
    base.update(overrides)
    return base


def test_default_config_loads():
    config = load_topic_config(ROOT / "config" / "topics.json")
    ids = [item["id"] for item in config["topics"]]
    assert "openai" in ids
    assert "anthropic" in ids
    assert "agent" in ids
    assert "model-releases" in ids
    assert "doubao" in ids
    assert "quark" in ids
    assert "hunyuan" in ids
    assert "perplexity" in ids
    assert "apple" in ids
    assert "monetization" in ids
    assert "product-entry" in ids
    assert "agent-ecosystem" in ids
    assert "workplace" in ids
    assert len(ids) == len(set(ids))
    group_ids = {item["id"] for item in config["groups"]}
    assert "lens" in group_ids
    for item in config["topics"]:
        assert item["group"] in group_ids


def test_lens_group_leads_hub_filter_contract():
    config = load_topic_config(ROOT / "config" / "topics.json")
    group_ids = [item["id"] for item in config["groups"]]
    assert group_ids[0] == "lens"
    assert group_ids[1:] == ["company", "tech"]
    lens = config["groups"][0]
    assert lens["filter"] == "topics"
    lens_ids = [item["id"] for item in config["topics"] if item["group"] == "lens"]
    assert lens_ids == ["monetization", "product-entry", "agent-ecosystem", "workplace"]


def test_company_topics_follow_lea_override_order():
    config = load_topic_config(ROOT / "config" / "topics.json")
    company_ids = [item["id"] for item in config["topics"] if item["group"] == "company"]
    assert company_ids[:7] == [
        "doubao",
        "qwen",
        "hunyuan",
        "quark",
        "kimi",
        "deepseek",
        "minimax",
    ]
    assert company_ids[7:15] == [
        "openai",
        "anthropic",
        "google-gemini",
        "meta-llama",
        "xai",
        "perplexity",
        "apple",
        "microsoft",
    ]
    assert company_ids[15] == "nvidia"
    for tid in ("zhipu", "huggingface", "cursor", "openrouter"):
        assert company_ids.index(tid) > company_ids.index("nvidia")
    assert company_ids[-4:] == ["zhipu", "huggingface", "cursor", "openrouter"]


def test_tech_topics_lead_with_direction_priorities():
    config = load_topic_config(ROOT / "config" / "topics.json")
    tech_ids = [item["id"] for item in config["topics"] if item["group"] == "tech"]
    assert tech_ids[:7] == [
        "agent",
        "coding",
        "multimodal",
        "on-device",
        "open-source",
        "mcp",
        "model-releases",
    ]
    assert tech_ids[7:] == [
        "image-gen",
        "video",
        "audio",
        "embodied",
        "reasoning",
        "inference",
    ]


def test_lens_copy_asks_business_questions():
    monetization = _config_topic("monetization")
    product_entry = _config_topic("product-entry")
    agent_ecosystem = _config_topic("agent-ecosystem")
    workplace = _config_topic("workplace")
    assert monetization["description"] == "各家怎么收费、谁在抽佣、付费转化与定价在怎么变？"
    assert product_entry["description"] == "国民级 App 的 AI 入口在哪、搜索与助手链路怎么接、谁在抢入口？"
    assert agent_ecosystem["description"] == "各家 Agent 的产品形态、开放生态与落地场景在怎么演进？"
    assert workplace["description"] == "AI 办公产品的进展，以及各家为 AI 做的组织与人事调整？"
    config = load_topic_config(ROOT / "config" / "topics.json")
    assert config["groups"][0]["name"] == "产业透镜"


def _config_topic(topic_id: str) -> dict:
    config = load_topic_config(ROOT / "config" / "topics.json")
    for item in config["topics"]:
        if item["id"] == topic_id:
            return item
    raise AssertionError(f"missing topic {topic_id}")


def test_domestic_product_keywords_match_expected_aliases():
    doubao = _config_topic("doubao")
    qwen = _config_topic("qwen")
    quark = _config_topic("quark")
    hunyuan = _config_topic("hunyuan")

    assert record_matches_topic({"title": "豆包发布新模型"}, doubao)
    assert record_matches_topic({"title": "ByteDance Doubao update"}, doubao)
    assert record_matches_topic({"title": "火山引擎上线 Volcengine Ark"}, doubao)

    assert record_matches_topic({"title": "通义千问发布 Qwen3"}, qwen)
    assert record_matches_topic({"title": "DashScope 上架新千问模型"}, qwen)
    assert not record_matches_topic({"title": "夸克AI 上线浏览器助手"}, qwen)

    assert record_matches_topic({"title": "夸克AI 上线浏览器助手"}, quark)
    assert record_matches_topic({"title": "Alibaba Quark adds AI search"}, quark)
    assert not record_matches_topic({"title": "通义千问发布 Qwen3"}, quark)
    assert not record_matches_topic({"title": "Qwen2.5-VL 开源"}, quark)
    assert not record_matches_topic({"title": "资源直达：夸克网盘 https://example.com"}, quark)

    assert record_matches_topic({"title": "腾讯混元发布新模型"}, hunyuan)
    assert record_matches_topic({"title": "Tencent Yuanbao desktop app"}, hunyuan)
    assert record_matches_topic({"title": "元宝接入混元大模型"}, hunyuan)

    perplexity = _config_topic("perplexity")
    apple = _config_topic("apple")
    assert record_matches_topic({"title": "Perplexity launches Computer agent"}, perplexity)
    assert record_matches_topic({"title": "Aravind Srinivas on Perplexity Comet"}, perplexity)
    assert not record_matches_topic({"title": "A perplexing GPU pricing chart"}, perplexity)

    assert record_matches_topic({"title": "Apple Intelligence adds on-device writing tools"}, apple)
    assert record_matches_topic({"title": "苹果AI 更新 Siri"}, apple)
    assert record_matches_topic({"title": "Siri gets a fully revamped assistant"}, apple)
    assert not record_matches_topic({"title": "iPhone 17 Pro Max camera review"}, apple)
    assert not record_matches_topic({"title": "apples to apples comparison of GPUs"}, apple)


def test_lens_topic_keywords_match_business_and_product_stories():
    monetization = _config_topic("monetization")
    product_entry = _config_topic("product-entry")
    agent_ecosystem = _config_topic("agent-ecosystem")
    workplace = _config_topic("workplace")

    assert record_matches_topic({"title": "OpenAI pauses $200 ChatGPT Pro sign-ups"}, monetization)
    assert record_matches_topic({"title": "DeepSeek 下调 API 定价"}, monetization)
    assert record_matches_topic({"title": "大模型服务上线个人套餐，付费转化看 ARPU"}, monetization)
    assert record_matches_topic({"title": "应用商店抽佣与分成比例上调"}, monetization)
    assert not record_matches_topic({"title": "新学期正版软件付费栏目限时优惠"}, monetization)
    assert not record_matches_topic({"title": "Winamp plans 2027 return with a new streaming subscription"}, monetization)
    assert not record_matches_topic({"title": "Memory pricing suggests iPhones could get even more expensive in 2027"}, monetization)
    assert record_matches_topic({"title": "Qwen3.8-Omni-Flash undercuts Google's Gemini Flash pricing"}, monetization)
    assert not record_matches_topic({"title": "The DJI Mini 5 Pro gets a rare price cut at Amazon"}, monetization)

    assert record_matches_topic({"title": "微信搜索框接入 AI 助手，抢超级入口"}, product_entry)
    assert record_matches_topic({"title": "Anthropic 合并聊天，打造统一办公入口"}, product_entry)
    assert record_matches_topic({"title": "侧边栏助手接入搜索，桌面入口开战"}, product_entry)
    assert not record_matches_topic({"title": "抖音新增冒用声音专属举报入口"}, product_entry)
    assert not record_matches_topic({"title": "机构有了合规入口"}, product_entry)
    assert not record_matches_topic({"title": "也门胡塞武装抵达位于重要航道入口处的战略要岛"}, product_entry)
    assert not record_matches_topic({"title": "PC 网站接入微信登录，这 10 个坑我替你踩完了"}, product_entry)

    assert record_matches_topic({"title": "Agent 落地场景与开放平台插件生态"}, agent_ecosystem)
    assert record_matches_topic({"title": "多智能体通过 MCP 做工具调用"}, agent_ecosystem)
    assert record_matches_topic({"title": "智能体平台开放生态上线"}, agent_ecosystem)

    assert record_matches_topic({"title": "ChatGPT 正式入驻 Word：办公文档里三套 AI"}, workplace)
    assert record_matches_topic({"title": "飞书引入团队智能体，钉钉和 Notion 也在跟"}, workplace)
    assert record_matches_topic({"title": "百度AI底层架构再迎重磅人事变动，新设AI部门"}, workplace)
    assert record_matches_topic({"title": "裁员潮将持续，直到我们学会发掘 AI 的商业价值"}, workplace)
    assert not record_matches_topic(
        {"title": "Big Tech uses guarantees to keep $300B AI exposure off balance sheets"},
        workplace,
    )


def test_topics_payload_preserves_config_array_order(tmp_path: Path):
    config = load_topic_config(ROOT / "config" / "topics.json")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "stories-merged.json").write_text(
        json.dumps({"generated_at": "2026-09-20T00:00:00Z", "stories": []}),
        encoding="utf-8",
    )
    payload = write_topics_payload(data_dir, config_path=ROOT / "config" / "topics.json")
    index = json.loads((data_dir / "topics.json").read_text(encoding="utf-8"))
    config_ids = [item["id"] for item in config["topics"]]
    assert [item["id"] for item in index["topics"]] == config_ids
    assert [item["id"] for item in payload["topics"]] == config_ids
    company_ids = [item["id"] for item in index["topics"] if item["group"] == "company"]
    assert company_ids[:4] == ["doubao", "qwen", "hunyuan", "quark"]
    tech_ids = [item["id"] for item in index["topics"] if item["group"] == "tech"]
    assert tech_ids[:7] == [
        "agent",
        "coding",
        "multimodal",
        "on-device",
        "open-source",
        "mcp",
        "model-releases",
    ]
    assert index["groups"][0]["id"] == "lens"
    assert index["groups"][0]["filter"] == "topics"
    lens_ids = [item["id"] for item in index["topics"] if item["group"] == "lens"]
    assert lens_ids == ["monetization", "product-entry", "agent-ecosystem", "workplace"]


def test_ascii_keywords_use_word_boundaries():
    assert term_matches("GPT-5", "OpenAI ships GPT-5 today")
    assert not term_matches("GPT", "ChatGPT desktop app")
    assert term_matches("Claude", "Anthropic releases Claude Opus")
    assert not term_matches("AI", "OPENAI quarterly letter")


def test_cjk_keywords_use_substring_match():
    assert term_matches("通义千问", "阿里通义千问发布新模型")
    assert term_matches("智谱", "智谱 GLM-4 更新")


def test_story_matches_nested_source_titles():
    story = {
        "story_id": "story-1",
        "title": "多家媒体关注同一事件",
        "primary_item": {"title": "多家媒体关注同一事件", "summary": ""},
        "items": [{"title": "OpenAI 发布 GPT-5", "source_name": "AI HOT"}],
    }
    assert record_matches_topic(story, topic())
    assert "OpenAI 发布 GPT-5" in haystack_text(story)


def test_exclude_keywords_block_a_match():
    record = {"title": "A travel agent books flights with Claude"}
    spec = topic(id="agent", keywords=["Agent"], exclude=["travel"])
    assert not record_matches_topic(record, spec)
    assert record_matches_topic(record, topic(id="agent", keywords=["Agent"]))


def test_regex_patterns_match_model_releases():
    spec = topic(
        id="model-releases",
        keywords=[],
        patterns=[r"(发布|推出).{0,12}模型"],
    )
    assert record_matches_topic({"title": "阿里发布通义千问新模型"}, spec)
    assert not record_matches_topic({"title": "模型卡里写了许可证"}, spec)


def test_microsoft_topic_does_not_match_bare_windows_news():
    spec = topic(
        id="microsoft",
        keywords=["Copilot", "Azure OpenAI", "微软 AI"],
    )
    assert not record_matches_topic({"title": "Microsoft released Windows 11 update"}, spec)
    assert record_matches_topic({"title": "GitHub Copilot adds agent mode"}, spec)


def test_prefers_curated_stories_when_capping():
    spec = topic(keywords=["OpenAI"])
    pools = {
        "stories": [
            {
                "story_id": "old-curated",
                "title": "OpenAI cookbook",
                "url": "https://example.com/a",
                "latest_at": "2026-01-01T00:00:00Z",
                "source_count": 3,
                "_pool": "stories",
            }
        ],
        "latest": [
            {
                "id": "new-raw",
                "title": "OpenAI rumor",
                "url": "https://example.com/b",
                "published_at": "2026-09-01T00:00:00Z",
                "site_id": "newsnow",
                "_pool": "latest",
            }
        ],
        "brief": [{"story_id": "old-curated"}],
        "archive": [],
    }
    items, total = match_topic_items(spec, pools, {"old-curated"}, max_items=1)
    assert total == 2
    assert len(items) == 1
    assert items[0]["id"] == "old-curated"
    assert items[0]["curated"] is True


def test_dedupes_story_and_item_with_the_same_url():
    spec = topic(keywords=["OpenAI"])
    url = "https://www.example.com/openai-gpt5/"
    pools = {
        "stories": [
            {
                "story_id": "cluster",
                "title": "OpenAI GPT-5",
                "primary_url": url,
                "url": url,
                "latest_at": "2026-09-01T12:00:00Z",
                "source_count": 4,
                "primary_item": {"title": "OpenAI GPT-5", "summary": "clustered summary", "url": url},
                "_pool": "stories",
            }
        ],
        "latest": [
            {
                "id": "raw",
                "title": "OpenAI GPT-5",
                "url": url,
                "published_at": "2026-09-01T11:00:00Z",
                "site_id": "newsnow",
                "_pool": "latest",
            }
        ],
        "brief": [],
        "archive": [],
    }
    items, total = match_topic_items(spec, pools, set(), max_items=10)
    assert total == 1
    assert items[0]["story_id"] == "cluster"
    assert items[0]["summary"] == "clustered summary"


def test_slim_item_keeps_card_fields():
    item = slim_item(
        {
            "story_id": "s1",
            "title": "Claude Code 更新",
            "primary_url": "https://example.com/claude",
            "latest_at": "2026-09-20T01:00:00Z",
            "source_count": 2,
            "source_name": "AI HOT",
            "primary_item": {
                "summary": "Anthropic 给 Claude Code 加了新能力",
                "recommend_reason_zh": "官方说明了具体工作流变化",
                "site_id": "aihot",
            },
        },
        {"s1"},
    )
    assert item["curated"] is True
    assert item["source_count"] == 2
    assert item["url"].endswith("/claude")
    assert "Claude Code" in item["title"]


def test_write_topics_payload_emits_index_and_detail_json(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "stories-merged.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-09-20T00:00:00Z",
                "stories": [
                    {
                        "story_id": "s-openai",
                        "title": "OpenAI 发布 GPT-5",
                        "url": "https://example.com/gpt5",
                        "latest_at": "2026-09-20T00:00:00Z",
                        "source_count": 2,
                        "source_name": "AI HOT",
                    },
                    {
                        "story_id": "s-claude",
                        "title": "Anthropic 发布 Claude Opus",
                        "url": "https://example.com/opus",
                        "latest_at": "2026-09-19T00:00:00Z",
                        "source_count": 1,
                        "source_name": "官方",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (data_dir / "daily-brief.json").write_text(
        json.dumps({"items": [{"story_id": "s-openai"}]}),
        encoding="utf-8",
    )
    payload = write_topics_payload(data_dir, config_path=ROOT / "config" / "topics.json")
    index = json.loads((data_dir / "topics.json").read_text(encoding="utf-8"))
    assert "_details" not in index
    assert index["topic_count"] == payload["topic_count"]
    openai = json.loads((data_dir / "topics" / "openai.json").read_text(encoding="utf-8"))
    assert openai["item_count"] >= 1
    assert openai["items"][0]["title"] == "OpenAI 发布 GPT-5"
    assert openai["items"][0]["curated"] is True
    anthropic = json.loads((data_dir / "topics" / "anthropic.json").read_text(encoding="utf-8"))
    assert any("Claude" in item["title"] for item in anthropic["items"])


def test_topic_pages_use_relative_roots(tmp_path: Path):
    config = {
        "groups": [{"id": "company", "name": "公司"}],
        "topics": [topic()],
    }
    written = write_topic_pages(config, tmp_path)
    hub = (tmp_path / "index.html").read_text(encoding="utf-8")
    detail = (tmp_path / "openai" / "index.html").read_text(encoding="utf-8")
    assert 'data-root="../"' in hub
    assert 'href="../"' in hub
    assert 'src="../assets/topics.js' in hub
    assert 'href="../assets/sidebar.css' in hub
    assert 'src="../assets/sidebar.js' in hub
    assert 'data-topic-id="openai"' in detail
    assert 'data-root="../../"' in detail
    assert 'href="../../"' in detail
    assert 'src="../../assets/topics.js' in detail
    assert 'src="../../assets/sidebar.js' in detail
    assert len(written) == 2


def test_hub_template_does_not_hardcode_a_topic_id():
    html = render_topic_page(depth=1)
    assert "data-topic-id" not in html
    assert "按主题看 AI" in html
    assert 'id="topicsFilter"' in html
    assert "assets/topics.js?v=topics-4" in html


def test_committed_topic_pages_cover_config():
    config = load_topic_config(ROOT / "config" / "topics.json")
    assert (ROOT / "topics" / "index.html").exists()
    for topic in config["topics"]:
        page = ROOT / "topics" / topic["id"] / "index.html"
        assert page.exists(), f"missing {page}; run python scripts/build_topics.py --write-pages"
        html = page.read_text(encoding="utf-8")
        assert f'data-topic-id="{topic["id"]}"' in html
        assert 'src="../../assets/topics.js' in html
        assert 'src="../../assets/sidebar.js' in html
