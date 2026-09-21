"""Per-tab inner layout: filter + 速览, backed by existing radar data."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_home_markup_has_distinct_pane_regions():
    source = read("index.html")
    assert 'id="paneTop"' in source
    assert 'id="paneKicker"' in source
    assert 'id="sectionTabs"' in source
    assert 'id="sourceKindChips"' in source
    assert 'id="hotStripWrap"' in source
    assert "当前热点" in source
    assert 'id="hotBoardWrap"' in source
    assert 'id="briefWrap"' in source
    assert 'id="briefDigest"' in source
    assert 'id="topicsPane"' in source
    assert 'id="topicsFilter"' in source
    assert 'id="topicsMain"' in source
    assert 'class="topics-entry"' in source
    assert 'href="./topics/"' in source
    assert "GitHub 与接入指南" not in source
    assert "github.com/LearnPrompt/ai-news-radar" not in source
    assert "模型榜" not in source
    assert "Tibo" not in source


def test_home_keeps_pages_relative_links():
    source = read("index.html")
    assert 'href="/ai-news-radar/' not in source
    assert 'src="/ai-news-radar/' not in source
    assert 'href="./topics/"' in source
    assert 'src="./assets/app.js' in source


def test_app_maps_real_filters_and_omits_unbacked_invented_heat_api():
    source = read("assets/app.js")
    assert "PANE_CATEGORY_DEFS" in source
    for label in ("全部", "模型", "产品", "行业", "论文", "教程", "观点"):
        assert label in source
    assert "一手信源" in source
    assert "资讯" in source
    assert "推文" in source
    assert "这一天的" in source
    assert "daily-brief.json" in source
    assert "HOT_STRIP_LIMIT = 5" in source
    assert "function buildHotCard(" in source
    assert "function renderHotStrip(" in source
    assert "function renderBriefPane(" in source
    assert "function renderSourceKindChips(" in source
    assert "item.summary" in source
    assert "heat.api" not in source.lower()
    assert "fetch(" in source
    assert "aihot.news/api" not in source
    assert "模型榜" not in source
    assert "Tibo" not in source


def test_overlay_chips_are_data_backed_not_required():
    source = read("assets/app.js")
    assert "overlay: true" in source
    assert "section.overlay && count === 0" in source
    assert 'id: "tutorials"' in source
    assert 'id: "opinion"' in source
    assert 'id: "devtools"' in source  # still used for card badges
    assert "PANE_CATEGORY_DEFS" in source
    assert "devtools" not in source.split("PANE_CATEGORY_DEFS")[1].split("SOURCE_KIND_FILTERS")[0]


def test_hot_and_brief_use_existing_json_signals():
    source = read("assets/app.js")
    assert "storyHotScore" in source
    assert "hotBoardStories" in source
    assert "briefStories" in source
    assert "dataWindowHours" in source
    assert "window_hours" in source
    assert "function renderPaneChrome(" in source
    assert 'nav !== "hot"' in source or 'nav === "hot"' in source
    assert 'nav === "brief"' in source


def test_favorites_pane_stays_localstorage_only():
    source = read("assets/sidebar.js")
    assert "本机收藏" in source
    assert "localStorage" in source
    assert "aiNewsRadarFavorites" in source
    assert "不会上传" in source


def test_topics_hub_keeps_group_filter():
    hub = read("topics/index.html")
    js = read("assets/topics.js")
    home = read("index.html")
    app = read("assets/app.js")
    assert 'id="topicsFilter"' in hub
    assert "topics-filter" in hub
    assert "function renderGroupFilter" in js or "topicsFilter" in js
    assert "data-radar-surface=\"topics\"" in hub
    assert "function showHub(" in js
    assert "function isEmbeddedHub(" in js
    assert 'id="topicsPane"' in home
    assert 'next === "topics"' in app
    assert "AINewsRadarTopics" in app
    assert 'if (group.filter === "topics")' not in js
    assert "kind: \"topic\"" not in js
    assert "按哪一个主题" not in js


def test_topics_hub_chips_stay_group_level():
    js = read("assets/topics.js")
    assert "function hubFilterOptions(" in js
    assert 'label: "全部"' in js
    assert 'kind: "group"' in js
    assert 'if (group.filter === "topics")' not in js
    hub_fn = js.split("function hubFilterOptions(")[1].split("function resolveHubFilter(")[0]
    assert "topicsForGroup" not in hub_fn
    config = read("config/topics.json")
    assert '"id": "lens"' in config
    assert '"id": "company"' in config
    assert '"id": "tech"' in config


def test_topics_nav_hides_entry_cta_and_empty_chrome():
    css = read("assets/styles.css")
    classic_css = read("classic/assets/styles.css")
    app = read("assets/app.js")
    classic = read("classic/assets/app.js")
    topics_css = read("assets/topics.css")
    assert ".brief-wrap[hidden]" in css
    assert ".section-nav-wrap[hidden]" in css
    assert ".topics-entry[hidden]" in css
    assert "body.is-topics-nav .topics-entry" in css
    assert "body.is-topics-nav .brief-wrap" in css
    assert "body.is-topics-nav .topics-entry" in classic_css
    assert "body.is-topics-nav .section-nav-wrap" in classic_css
    assert 'classList.toggle("is-topics-nav"' in app
    assert 'el.hidden = nav === "topics"' in app
    assert 'el.hidden = next === "topics"' in classic
    assert ".topics-filter:empty" in topics_css
    home = read("index.html")
    classic_html = read("classic/index.html")
    assert 'class="topics-entry"' in home
    assert 'href="./topics/"' in home
    assert 'class="topics-entry"' in classic_html


def test_sidebar_topics_stays_in_shell():
    js = read("assets/sidebar.js")
    assert "homeHref(\"topics\")" in js
    assert "if (nav === \"topics\") return" not in js
    assert "aria-label=\"更多\"" not in js
    assert "Agent 接入" not in js
    assert "关于" not in js
    assert "反馈" not in js


def test_embedded_topics_hub_does_not_steal_document_title():
    js = read("assets/topics.js")
    assert "if (!isEmbeddedHub())" in js
    assert 'document.title = "主题 · AI News Radar"' in js
    home = read("assets/app.js")
    classic = read("classic/assets/app.js")
    for source in (home, classic):
        assert 'a.hero-link[href="./topics/"]' in source
        assert 'topicsPane.hidden' in source or 'topicsPaneEl.hidden' in source


def test_classic_unhides_embedded_topics_pane():
    source = read("classic/assets/app.js")
    assert "topicsPane.hidden = next !== \"topics\"" in source
    assert 'body.classList.toggle("is-topics-nav"' in source or "is-topics-nav" in source
    assert 'a.topics-entry' in source
    assert 'section-nav-wrap' in source
