"""Parsers for first-party domestic lab blogs and changelogs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from scripts.build_topics import load_topic_config, record_matches_topic
from scripts.update_news import (
    parse_deepseek_updates_html,
    parse_hunyuan_blog_payload,
    parse_kimi_changelog_markdown,
    parse_minimax_release_notes,
    parse_quark_article_news,
    parse_qwen_blog_payload,
    parse_seed_blog_payload,
    parse_zhipu_release_notes,
)

NOW = datetime(2026, 9, 29, tzinfo=timezone.utc)
ROOT_TOPICS = load_topic_config(Path(__file__).resolve().parents[1] / "config" / "topics.json")


def topic(topic_id: str) -> dict:
    return next(item for item in ROOT_TOPICS["topics"] if item["id"] == topic_id)


def test_qwen_blog_payload_uses_chinese_article_path():
    items = parse_qwen_blog_payload(
        {
            "data": {
                "articles": [
                    {
                        "title": "Qwen3.8-Max：编程与办公，全面跃升",
                        "path": "qwen3.8-max",
                        "extra": {"date": "2026-09-18T15:00:00+08:00"},
                    },
                    {
                        "title": "旧文",
                        "path": "old",
                        "extra": {"date": "2026-01-01T00:00:00+08:00"},
                    },
                ]
            }
        },
        NOW,
    )
    assert len(items) == 1
    assert items[0].source == "Qwen Blog"
    assert items[0].url == "https://qwen.ai/blog?id=qwen3.8-max"
    assert items[0].meta["select_tier"] == "T1"
    assert record_matches_topic({"title": items[0].title, "source": items[0].source}, topic("qwen"))


def test_seed_blog_payload_prefers_chinese_title():
    # 2026-08-04 is inside the 90-day domestic window of 2026-09-29.
    # 2026-01-01 is outside it.
    items = parse_seed_blog_payload(
        {
            "sub_article_list": [
                {
                    "ArticleMeta": {"PublishDate": 1785859200000},
                    "ArticleSubContentZh": {
                        "Title": "Seedance 2.5 正式发布",
                        "TitleKey": "一镜成片",
                    },
                    "ArticleSubContentEn": {"Title": "Introducing Seedance 2.5", "TitleKey": "en-slug"},
                },
                {
                    "ArticleMeta": {"PublishDate": 1767225600000},
                    "ArticleSubContentZh": {"Title": "旧文", "TitleKey": "old-post"},
                },
            ]
        },
        NOW,
    )
    assert len(items) == 1
    assert items[0].source == "ByteDance Seed Blog"
    assert items[0].title == "Seedance 2.5 正式发布"
    assert items[0].url == "https://seed.bytedance.com/zh/blog/%E4%B8%80%E9%95%9C%E6%88%90%E7%89%87"
    assert "en-slug" not in items[0].url
    assert record_matches_topic({"title": "Seedance 2.5 正式发布"}, topic("doubao"))


def test_hunyuan_blog_payload_uses_slug_and_hy_alias():
    items = parse_hunyuan_blog_payload(
        {
            "data": {
                "list": [
                    {
                        "id": 100100,
                        "title": "Introducing Hy4 preview",
                        "customUrl": "hy4-preview",
                        "displayPublishTime": 1787846400,
                    }
                ]
            }
        },
        NOW,
    )
    assert len(items) == 1
    assert items[0].url == "https://hunyuan.tencent.com/blog/hy4-preview"
    assert record_matches_topic({"title": items[0].title, "source": items[0].source}, topic("hunyuan"))


def test_quark_article_index_drops_generic_scan_skus():
    html = """
    <div class="article-list-item">
      <a class="article-card-link" href="https://scan.quark.cn/business/news-detail/26082804.html">
        <div class="article-title">夸克扫描王全能Skill全面赋能主流AI Agent生态</div>
        <div class="article-date">2026.08.28</div>
      </a>
    </div>
    <div class="article-list-item">
      <a href="https://scan.quark.cn/business/news-detail/26082518.html">
        <div class="article-title">转PDF｜文档一键批量转标准PDF</div>
        <div class="article-date">2026.08.25</div>
      </a>
    </div>
    """
    items = parse_quark_article_news(html, NOW)
    assert len(items) == 1
    assert items[0].source == "夸克 Quark News"
    assert items[0].url.endswith("/26082804.html")
    assert record_matches_topic({"title": items[0].title}, topic("quark"))


def test_deepseek_changelog_pairs_dates_with_following_headings():
    html = """
    <h2 id="date-2026-09-10">时间: 2026-09-10<a class="hash-link" href="#date-2026-09-10">​</a></h2>
    <h3 id="deepseek-v41-flash">DeepSeek-V4.1-Flash 发布<a class="hash-link">​</a></h3>
    <h2 id="date-2026-01-01">时间: 2026-01-01</h2>
    <h3 id="old">旧模型</h3>
    """
    items = parse_deepseek_updates_html(html, NOW)
    assert len(items) == 1
    assert items[0].title == "DeepSeek-V4.1-Flash 发布"
    assert items[0].url.endswith("#deepseek-v41-flash")
    mojibake = """
    <h2>时间: 2026-09-10</h2>
    <h3 id="deepseek-v41-flash-åå¸">DeepSeek-V4.1-Flash åå¸</h3>
    """
    repaired = parse_deepseek_updates_html(mojibake, NOW)
    assert repaired[0].title == "DeepSeek-V4.1-Flash 发布"
    assert repaired[0].url.endswith("#deepseek-v41-flash-发布")
    assert record_matches_topic({"title": items[0].title}, topic("deepseek"))


def test_kimi_changelog_splits_month_sections_into_headings():
    text = """
<Update label="2026年9月">
  ### 🤖 Kimi 托管智能体 Beta 上线
  ### 联网搜索 API
</Update>
<Update label="2026年8月">
  * `kimi-k2.5` 下线
  * `kimi-k2.5` 与 `moonshot-v1` 全系列模型（含 `-vision-preview`、`moonshot-v1-auto`）在国内外全平台下线，调用将返回 404 错误，请迁移至 [Kimi K3](/docs/guide/kimi-k3-quickstart)
</Update>
<Update label="2026年4月">
  ### 旧功能
</Update>
"""
    items = parse_kimi_changelog_markdown(text, NOW)
    assert [item.title for item in items] == [
        "Kimi 托管智能体 Beta 上线",
        "联网搜索 API",
        "kimi-k2.5 下线",
        "kimi-k2.5 与 moonshot-v1 全系列模型（含 -vision-preview、moonshot-v1-auto）在国内外全平台下线",
    ]
    assert all(item.source == "Kimi API Changelog" for item in items)
    assert record_matches_topic({"title": items[0].title}, topic("kimi"))
    late = datetime(2026, 9, 29, 20, 25, tzinfo=timezone.utc)
    july = parse_kimi_changelog_markdown(
        '<Update label="2026年7月">\n  ### Kimi K3 上线开放平台 API\n</Update>',
        late,
    )
    assert [item.title for item in july] == ["Kimi K3 上线开放平台 API"]


def test_minimax_release_notes_read_card_links():
    text = """
## 2026 年 8 月 20 日
<Card title="MiniMax H3" icon="video" href="https://www.minimax.cn/blog/minimax-h3" cta="了解更多">
## 2026 年 1 月 1 日
<Card title="Old" href="https://www.minimax.cn/news/old">
"""
    items = parse_minimax_release_notes(text, NOW)
    assert len(items) == 1
    assert items[0].title == "MiniMax H3"
    assert items[0].url == "https://www.minimax.cn/blog/minimax-h3"
    assert record_matches_topic({"title": items[0].title, "source": items[0].source}, topic("minimax"))


def test_zhipu_release_notes_use_description_and_doc_link():
    text = """
<Update label="2026-08-26" description="GLM-5.3-Flash 原生多模态模型上线">
  [**GLM-5.3-Flash**](/cn/guide/models/vlm/glm-5.3-flash)
</Update>
<Update label="2026-01-02" description="旧模型">
  [old](/cn/guide/models/text/old)
</Update>
"""
    items = parse_zhipu_release_notes(text, NOW)
    assert len(items) == 1
    assert items[0].source == "智谱 GLM Releases"
    assert items[0].url == "https://docs.bigmodel.cn/cn/guide/models/vlm/glm-5.3-flash"
    assert record_matches_topic({"title": items[0].title, "source": items[0].source}, topic("zhipu"))
