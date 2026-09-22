"""Regression checks for the shared left sidebar."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_sidebar_assets_exist_and_stay_framework_free():
    css = read("assets/sidebar.css")
    js = read("assets/sidebar.js")
    assert "--radar-sidebar-width: 180px" in css
    assert "position: fixed" in css
    assert "radar-nav-open" in css
    assert "prefers-color-scheme: dark" in css
    assert "react" not in css.lower()
    assert "vue" not in js.lower()
    assert "aiNewsRadarTheme" in js
    assert "aiNewsRadarFavorites" in js


def test_sidebar_maps_to_existing_radar_features_not_aihot_products():
    js = read("assets/sidebar.js")
    for label in ("精选", "全部 AI 动态", "热点榜", "AI 日报", "主题", "收藏"):
        assert label in js
    assert "模型榜" not in js
    assert "Tibo" not in js
    assert "Agent 接入" not in js
    assert "更新日志" not in js
    assert "关于" not in js
    assert "反馈" not in js
    assert "github.com/LearnPrompt" not in js
    assert "function githubRepo" not in js
    assert "function githubUrl" not in js
    assert "aria-label=\"更多\"" not in js
    assert 'data-radar-nav="selected"' in js
    assert 'data-radar-nav="all"' in js
    assert 'data-radar-nav="hot"' in js
    assert 'data-radar-nav="brief"' in js
    assert 'data-radar-nav="topics"' in js
    assert "homeHref(\"topics\")" in js


def test_sidebar_links_are_root_relative_not_pages_absolute():
    js = read("assets/sidebar.js")
    assert '"/ai-news-radar/' not in js
    assert "'/topics/'" not in js
    assert "siteHref(" in js
    assert "dataset.root" in js
    assert "aiNewsRadarViewV2" in js


def test_home_and_classic_load_shared_sidebar():
    for path, root in (("feed/index.html", "./"), ("classic/index.html", "./")):
        source = read(path)
        assert f"{root}assets/sidebar.css?v=pane-3" in source
        assert f"{root}assets/sidebar.js?v=pane-3" in source
        assert "data-radar-nav" not in source  # injected by shared JS, not duplicated markup


def test_topic_template_loads_sidebar_with_depth_root():
    source = read("scripts/build_topics.py")
    assert "{root}assets/sidebar.css?v=pane-3" in source
    assert "{root}assets/sidebar.js?v=pane-3" in source
    assert "Tibo" not in source


def test_mobile_and_classic_apps_honor_nav_query():
    for path in ("assets/app.js", "classic/assets/app.js"):
        source = read(path)
        assert "function readRequestedNav()" in source
        assert "function applyRadarNav(" in source
        assert 'get("nav")' in source
        assert "window.AINewsRadarNav" in source
        assert 'nav === "topics"' in source or 'next === "topics"' in source
