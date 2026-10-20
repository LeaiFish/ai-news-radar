"""Application sources must have a verified origin, dated entries and stable identities."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import official_app_updates as app
from scripts.build_topics import canonicalize_url, load_topic_config, record_identity, record_matches_topic
from scripts.source_tiers import resolve_select_tier
from scripts.update_news import fetch_official_app_source, normalize_url

NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)
TOPICS = load_topic_config(Path(__file__).resolve().parents[1] / "config/topics.json")["topics"]


def spec(kind):
    return next(source for source in app.APP_SOURCES if source["kind"] == kind)


def rows(kind, body):
    source = spec(kind)
    return app.keep_rows(app.PARSERS[kind](body, source), source, NOW)


def test_qwen_issues_keep_separate_real_anchors_and_dates():
    body = '''<section class="wn-issue" id="d20261014"><article class="wn-item"><h2>电商版上线</h2><p>面向商家的经营工具。</p></article></section>
    <section class="wn-issue" id="d20260930"><article class="wn-item"><h2>手机端上线</h2></article></section>
    <section class="wn-issue" id="d20260231"><article class="wn-item"><h2>无效日期</h2></article></section>
    <section class="wn-issue" id="d20261021"><article class="wn-item"><h2>未来</h2></article></section>'''
    result = rows("qwen", body)
    assert len(result) == 2
    assert result[0]["published_at"].date().isoformat() == "2026-10-14"
    assert "电商版上线" in result[0]["title"]
    assert len({record_identity(row) for row in result}) == 2
    assert normalize_url(result[0]["url"]).endswith("#d20261014")


def test_qwen_desktop_records_version_and_source_excerpt():
    result = rows("qwen_desktop", '''<div class="update-container" id="2026-10-15">
    <div data-component-part="update-description">千问办公 1.3.1</div>
    <div data-component-part="update-content"><ul><li>新增电商经营模式</li></ul></div></div>''')
    assert result[0]["title"].endswith("1.3.1")
    assert result[0]["summary"] == "新增电商经营模式"
    assert result[0]["url"].endswith("#2026-10-15")


def test_gemini_dates_stay_distinct_without_build_hash_selectors():
    result = rows("gemini", '''<main><div><h2>2026.10.13</h2><div><h3>Connected apps</h3><p>More tools.</p></div></div>
    <div><h2>2026.09.30</h2><h3>Skills</h3><p>Reusable tasks.</p></div>
    <div><h2>2025.01.01</h2><h3>Old</h3></div></main>''')
    assert len(result) == 2
    assert len({canonicalize_url(row["url"]) for row in result}) == 2
    assert ":~:text=2026.10.13" in result[0]["url"]
    assert "Connected apps" in result[0]["summary"]


def test_chatgpt_weekly_dates_use_explicit_period_and_filter_api_only_blocks():
    result = rows("chatgpt", '''<article id="mainContent"><h2 id="october-59-2026"><span>October 5–9, 2026</span></h2>
    <div data-update-products="chatgpt dots"></div><h3>Mobile dots</h3><p>Set up on mobile.</p>
    <div data-update-products="api"></div><h3>API endpoint</h3><p>Developer details</p>
    <h2 id="september-28october-2-2026"><span>September 28–October 2, 2026</span></h2>
    <div data-update-products="chatgpt"></div><h3>Work across devices</h3>
    <h2 id="devday-2026"><span>DevDay 2026</span></h2><p>Undated event</p></article>''')
    assert len(result) == 2
    assert result[0]["published_at"].day == 5
    assert "Mobile dots" in result[0]["summary"]
    assert "Developer details" not in result[0]["summary"]
    assert result[1]["published_at"].date().isoformat() == "2026-09-28"


def yuanbao_payload(**extra):
    return {"results": [{"trackId": 6480446430, "sellerName": "Tencent Technology (Shenzhen) Company Limited",
                         "version": "2.89.0", "currentVersionReleaseDate": "2026-10-15T14:29:41Z",
                         "releaseNotes": "录音结束生成总结", **extra}]}


def test_yuanbao_requires_tencent_identity_and_real_release_date():
    result = rows("yuanbao", yuanbao_payload())
    assert result[0]["published_at"].hour == 14
    assert "2.89.0" in result[0]["url"]
    assert rows("yuanbao", yuanbao_payload(sellerName="Someone Else")) == []
    assert rows("yuanbao", yuanbao_payload(trackId=123)) == []
    assert rows("yuanbao", yuanbao_payload(currentVersionReleaseDate="")) == []
    assert rows("yuanbao", yuanbao_payload(releaseNotes="")) == []
    later = rows("yuanbao", yuanbao_payload(version="2.90.0"))[0]
    assert record_identity(later) != record_identity(result[0])


def test_meta_rss_keeps_ai_only_and_rejects_external_and_undated_links():
    source = spec("rss")
    body = '''<rss><channel>
      <item><title>Muse for small business</title><link>https://about.fb.com/news/2026/10/muse/</link><pubDate>Thu, 15 Oct 2026 12:00:00 GMT</pubDate><description>&lt;p&gt;New tools&lt;/p&gt;</description></item>
      <item><title>Instagram sports</title><link>https://about.fb.com/news/sport/</link><pubDate>Thu, 15 Oct 2026 12:00:00 GMT</pubDate></item>
      <item><title>Muse external</title><link>https://example.com/muse/</link><pubDate>Thu, 15 Oct 2026 12:00:00 GMT</pubDate></item>
      <item><title>Meta AI undated</title><link>https://about.fb.com/news/undated/</link></item>
    </channel></rss>'''
    result = app.keep_rows(app.parse_rss(body, source), source, NOW)
    assert len(result) == 1
    assert result[0]["summary"] == "New tools"
    assert result[0]["published_at"] != NOW


def test_gemini_feed_excludes_cross_posted_model_and_other_google_news():
    source = next(x for x in app.APP_SOURCES if x["id"] == "official_app_gemini_blog")
    def item(path):
        return f'<item><title>Gemini</title><link>https://blog.google/{path}</link><pubDate>Thu, 15 Oct 2026 12:00:00 GMT</pubDate></item>'
    body = '<rss><channel>' + item('innovation-and-ai/products/gemini-app/connected-apps/') + item('innovation-and-ai/models-and-research/gemini-models/model/') + '</channel></rss>'
    assert len(app.parse_rss(body, source)) == 1


@pytest.mark.parametrize("value", ["2026", "October 2026", "", "2026-13-80"])
def test_partial_dates_do_not_become_today(value):
    assert app.dated(value) is None


@pytest.mark.parametrize("url", ["https://example.com/news#date", "https://gemini.google/other/#:~:text=2026.10.13", "https://docs.qwenwork.cn/release-notes/desktop#tracking"])
def test_ordinary_or_unrecognized_fragments_still_disappear(url):
    assert "#" not in normalize_url(url)
    assert "#" not in canonicalize_url(url)


def test_sources_match_their_company_topics_and_tiers():
    for source, topic_id in [(spec("qwen"), "qwen"), (spec("yuanbao"), "hunyuan"),
                             (spec("chatgpt"), "openai"), (spec("gemini"), "google-gemini"),
                             (spec("rss"), "meta-llama")]:
        topic = next(t for t in TOPICS if t["id"] == topic_id)
        assert record_matches_topic({"source": source["title"], "title": "Product update"}, topic)
        assert resolve_select_tier(source=source["title"]) == "T1"


class Response:
    url = spec("qwen")["url"]
    text = '<section class="wn-issue" id="d20261014"><article class="wn-item"><h2>电商版上线</h2></article></section>'
    content = text.encode()

    def raise_for_status(self):
        pass


class Session:
    def __init__(self, response):
        self.response = response

    def get(self, *args, **kwargs):
        return self.response


def test_collector_maps_verified_rows_to_existing_official_records():
    result = fetch_official_app_source(Session(Response()), spec("qwen"), NOW)
    assert result[0].site_id == "official_ai"
    assert result[0].meta["select_tier"] == "T1"
    assert result[0].meta["feed_url"] == spec("qwen")["url"]


def test_challenge_and_nonofficial_redirect_fail_visibly():
    response = Response()
    response.text = "<html>Checking your browser</html>"
    with pytest.raises(ValueError, match="structure"):
        app.fetch_source(Session(response), spec("qwen"), NOW)
    response.url = "https://example.com/mirror"
    with pytest.raises(ValueError, match="verified domains"):
        app.fetch_source(Session(response), spec("qwen"), NOW)


def test_one_failed_application_source_does_not_hide_other_sources(monkeypatch):
    from scripts import update_news as collector
    for name in ("fetch_official_ai_updates", "fetch_curated_ai_media", "fetch_ai_breakfast", "fetch_follow_builders",
                 "fetch_techurls", "fetch_buzzing", "fetch_iris", "fetch_bestblogs", "fetch_zeli",
                 "fetch_hacker_news_algolia", "fetch_ai_hubtoday", "fetch_aibase", "fetch_aihot", "fetch_newsnow"):
        monkeypatch.setattr(collector, name, lambda *args: [])
    def fetch(session, source, now):
        if source["id"] == "official_app_meta":
            raise ValueError("DNS unavailable")
        return [source["id"]]
    monkeypatch.setattr(collector, "fetch_official_app_source", fetch)
    items, statuses = collector.collect_all(None, NOW)
    assert len(items) == len(app.APP_SOURCES) - 1
    meta = next(s for s in statuses if s["site_id"] == "official_app_meta")
    assert meta["ok"] is False and meta["error"] == "DNS unavailable"
    assert next(s for s in statuses if s["site_id"] == "official_app_yuanbao")["ok"] is True


def test_distinct_release_urls_survive_topics_and_public_projection(tmp_path, monkeypatch):
    import importlib.util
    import json
    from scripts.build_topics import write_topics_payload
    from scripts.update_news import make_item_id
    releases = rows("qwen", '''<section class="wn-issue" id="d20261014"><article class="wn-item"><h2>电商版</h2></article></section>
    <section class="wn-issue" id="d20260930"><article class="wn-item"><h2>手机端</h2></article></section>''')
    records = [{**row, "url": normalize_url(row["url"]), "site_id": "official_ai",
                "id": make_item_id("official_ai", row["source"], row["title"], row["url"]),
                "published_at": row["published_at"].isoformat()} for row in releases]
    for name, payload in [("archive", {"items": records}), ("latest-24h-all", {"items_all": []}),
                          ("stories-merged", {"stories": []}), ("daily-brief", {"items": []})]:
        (tmp_path / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False))
    write_topics_payload(tmp_path, generated_at=NOW.isoformat())
    root = Path(__file__).resolve().parents[1]
    export_spec = importlib.util.spec_from_file_location("app_updates_export", root / "scripts/export-public-news.py")
    exporter = importlib.util.module_from_spec(export_spec)
    export_spec.loader.exec_module(exporter)
    monkeypatch.setattr(exporter, "NEWS", tmp_path)
    result = exporter.export()
    assert len(result["items"]) == 2
    assert len({item["id"] for item in result["items"]}) == 2
    assert len(next(topic for topic in result["topics"] if topic["id"] == "qwen")["itemIds"]) == 2
    assert all(item["source"]["name"] == "千问办公产品更新" for item in result["items"])
