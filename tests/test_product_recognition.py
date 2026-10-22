"""Real dropped product posts and counterexamples from the Oct21 source audit."""
import pytest

from scripts.ai_relevance import score_ai_relevance
from scripts.editorial_focus import editorial_focus
from scripts.product_context import product_context


def record(title, url="https://example.com/post", **fields):
    return {"title": title, "url": url, "site_id": "techurls", **fields}


@pytest.mark.parametrize("row", [
    record("火山引擎Seedance Managed Agent上线：一个Agent完成视觉创作全链路", "https://mp.weixin.qq.com/s/seedance",
           site_id="wechat_bridge", company_id="doubao", account_name="火山引擎", account_verified=True),
    record("Seedance2.0支持多镜头编辑", "https://mp.weixin.qq.com/s/versioned"),
    record("双11想省心，来千问解锁新逛法", "https://mp.weixin.qq.com/s/qwen",
           site_id="wechat_bridge", company_id="qwen", account_name="千问APP", account_verified=True),
    record("千问新增优惠券自动匹配功能，支持购物比价", "https://mp.weixin.qq.com/s/shopping",
           site_id="wechat_bridge", company_id="qwen", account_name="千问APP", account_verified=True),
    record("One model that generates 3D characters, motion, and scenes. JST-2 is now live in our API.",
           "https://x.com/ViggleAI/status/2112612250762514709", site_id="x_bridge"),
    record("Perplexity Computer Can Now Run Fully Locally on Mac"),
    record("All three models have EU-hosted and zero-data-retention endpoints, through the same /audio/transcriptions API.",
           "https://x.com/OpenRouter/status/2112595992096977366", site_id="x_bridge"),
    record("Meta suspends Muse chats sharing feature after it left private details exposed"),
    record("MiniMax Design - 手册与指南", site_id="waytoagi"),
    record("千问办公杀入电商经营！一个Agent接管多平台生意", site_id="opmlrss", source="InfoQ CN"),
    record("我用 WorkBuddy + ima 把公众号文章做成了知识库。", "https://juejin.cn/post/7698208410021527594", site_id="newsnow"),
    record("通过 Kimi 把研究资料整理成团队知识库"),
    record("使用 Claude 将公众号文章收录到知识库"),
    record("更优成本，更多创意！来看TA们用Seedance 2.5 Draft拍了什么？", "https://mp.weixin.qq.com/s/0NGPK4kZb3FTTcbnXwvJMA", site_id="wechat_bridge"),
    record("How Numan built an eval-first AI health coach with LangGraph and LangSmith",
           "https://www.langchain.com/blog/health-coach", source="LangChain Blog"),
])
def test_dropped_product_function_usage_and_experience_posts_are_kept(row):
    assert score_ai_relevance(row)["is_ai_related"]
    assert editorial_focus(row) == "product"


@pytest.mark.parametrize("row", [
    record("这个商业模型终于跑通了"),
    record("Precursor", "https://blog.cloudflare.com/introducing-precursor"),
    record("A new museum opens with interactive exhibits"),
    record("Meta adds new museum exhibits to its collection"),
    record("The DNS Museum", "https://dns.museum"),
    record("New MacBook model launches with a faster chip"),
    record("千问APP充值会员送优惠券，关注领红包", "https://mp.weixin.qq.com/s/promo", site_id="wechat_bridge",
           company_id="qwen", account_name="千问APP", account_verified=True),
    record("新版控制台上线，支持云主机续费", "https://mp.weixin.qq.com/s/cloud", site_id="wechat_bridge",
           company_id="doubao", account_name="火山引擎", account_verified=True),
    record("Introducing the all-new Black Shiba: featuring an ultra-soft coat. More API access: Qwen Cloud",
           "https://x.com/alibaba_cloud/status/1", site_id="x_bridge"),
    record("Use it now: https://t.co/short Read more:", "https://x.com/OpenRouter/status/1", site_id="x_bridge"),
    record("Happy holidays!", "https://x.com/ViggleAI/status/1", site_id="x_bridge"),
    record("New motion API is now live", "https://viggle.example/post", source="ViggleAI"),
    record("我用纸质剪报把公众号文章做成了知识库"),
    record("WorkBuddy 知识库抽奖，关注领取优惠券"),
    record("我用 WorkBuddy 把图片做成了蛋糕"),
    record("我用单反拍了什么？"),
])
def test_product_context_does_not_blanket_whitelist_sources_or_promotions(row):
    assert product_context(row) is None
    assert not score_ai_relevance(row)["is_ai_related"]


@pytest.mark.parametrize("row", [
    record("How to run Qwen inference benchmarks on Mac"),
    record("MiniMax M3.1 Flash：重新定义 Agent 的性能与成本"),
    record("MiniMax模型成本降70%，霸榜12天"),
    record("New ChatGPT image editing benchmark"),
    record("New model reaches #1 on Code Arena", "https://x.com/arena/status/1"),
    record("Day 0 support for Beam", "https://vllm.ai/blog/beam"),
    record("通过 Qwen 把资料整理成知识库的检索评测与推理优化"),
])
def test_evaluation_and_model_technology_do_not_gain_product_priority(row):
    assert editorial_focus(row) == "technical"


def test_vague_verified_account_title_still_needs_a_real_capability_or_usage_signal():
    generic = record("新逛法使用指南", "https://mp.weixin.qq.com/s/example", site_id="wechat_bridge",
                     company_id="qwen", account_name="千问APP", account_verified=True)
    assert score_ai_relevance(generic)["is_ai_related"]
    for fields in [{"account_verified": False}, {"company_id": "quark"},
                   {"account_name": "千问资讯搬运"}, {"url": "https://example.com/copy"}]:
        assert product_context(generic | fields) is None


def test_unsafe_promotion_remains_blocked_even_with_valid_product_evidence():
    row = record("Viggle launches new API for uncensored nude virtual girlfriends", "https://x.com/ViggleAI/status/1")
    assert score_ai_relevance(row)["reason"] == "unsafe_promotional_content"


def test_existing_strong_ai_relevance_is_not_downgraded_by_the_rescue_rule():
    row = record("ChatGPT launches a new collaboration app", site_id="aihot", source="AI HOT")
    assert score_ai_relevance(row)["score"] == 1.0


def test_lookalike_domain_never_supplies_trusted_product_identity():
    row = record("New motion API is now live", "https://viggle.ai.attacker/post")
    assert product_context(row) is None
    assert score_ai_relevance(row)["reason"] != "product_function_or_usage"


def test_rescued_wechat_product_outranks_a_model_leaderboard_in_selected_feed():
    from datetime import datetime, timezone
    from scripts.ai_relevance import add_ai_relevance_fields
    from scripts.update_news import build_story_record
    from scripts.story_select import assign_selection_tiers
    now = datetime(2026, 10, 21, 3, 18, tzinfo=timezone.utc)
    product = add_ai_relevance_fields(record(
        "双11想省心，来千问解锁新逛法", "https://mp.weixin.qq.com/s/qwen",
        id="qwen", site_id="wechat_bridge", source="公众号：千问APP",
        company_id="qwen", account_name="千问APP", account_verified=True,
        published_at="2026-10-20T07:04:00Z", select_tier="T1_5"))
    technical = add_ai_relevance_fields(record(
        "New model reaches #1 on Code Arena", "https://x.com/arena/status/1",
        id="arena", site_id="aihot", source="Arena", published_at=now.isoformat()))
    stories = [build_story_record("tech", [technical], now, 24), build_story_record("product", [product], now, 24)]
    # Both qualify independently; compare editorial priority within eligible news.
    for story in stories:
        story["importance_label"] = "官方更新"
    assign_selection_tiers(stories, limit=1, company_topics=[], lens_topics=[], now=now)
    assert stories[1]["tier"] == "selected"
    assert stories[1]["editorial_focus"] == "product"
    assert stories[0]["tier"] == "all"
    assert stories[0]["editorial_focus"] == "technical"
