"""AI Perspective shell: three spaces, competition overview, honest placeholders."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_perspective_home_is_the_new_shell_with_relative_links():
    page = read("index.html")
    css = read("assets/perspective.css")
    js = read("assets/perspective.js")

    assert "AI Perspective" in page
    assert "三个空间" in page
    assert "研究空间" in page
    assert "竞争概览" in page
    assert "主题研究" in page
    assert "工具空间" in page
    assert "工作台" in page
    assert "关注视角" in page
    assert "社区 x AI 应用" in page
    assert "ToC 视角" in page
    assert "产品层优先" in page
    assert 'href="./?space=research"' in page
    assert 'href="./?space=workbench"' in page
    assert 'href="./feed/"' in page
    assert 'src="./assets/perspective.js' in page
    assert 'href="./assets/perspective.css' in page
    assert 'href="./assets/styles.css' in page
    assert 'href="./assets/sidebar.css' in page
    assert "aiNewsRadarTheme" in page
    assert "aiNewsRadarTheme" in js
    assert 'data-radar-theme="dark"' in page
    assert 'data-radar-theme="system"' in page
    assert 'data-radar-theme="light"' in page
    assert 'href="/ai-news-radar/' not in page
    assert 'src="/ai-news-radar/' not in page
    assert '"/ai-news-radar/' not in js
    for retired in ("精选", "热点榜", "全部 AI 动态", "data-radar-nav"):
        assert retired not in page
    assert "assets/sidebar.js" not in page
    for token in ("var(--bg)", "var(--surface)", "var(--surface-soft)", "var(--ink)", "var(--accent)", "var(--radius)", "var(--line-soft)"):
        assert token in css
    assert "news-card" in js
    assert "section-tab" in page
    assert "Avenir Next" not in css
    assert "#12b5a9" not in css
    assert "--teal" not in css
    assert "color-scheme: light" not in css


def test_competition_overview_matches_mock_structure_and_marks_placeholders():
    page = read("index.html")
    js = read("assets/perspective.js")

    assert "月度：先看全局变化" in page
    assert 'id="monthSelect"' in page
    assert "本月核心判断" in page
    assert ">国内<" in page
    assert ">海外<" in page
    for column in ("产品", "核心指标", "本月值", "环比", "追踪备注"):
        assert column in page
    assert "关联研究" in page
    assert "示例" in page
    assert "待接入" in page
    assert "AI 草稿" in js
    assert "近窗相关故事" in js
    assert "daily-brief.json" in js
    assert "stories-merged.json" in js
    assert "topics.json" in js
    assert "importance_label" in js
    assert "heat.api" not in js.lower()
    assert "mau" not in js.lower()


def test_research_catalog_and_workbench_placeholder():
    page = read("index.html")
    js = read("assets/perspective.js")
    research = read("research/index.html")
    workbench = read("workbench/index.html")

    assert 'data-space-panel="research"' in page
    assert 'data-space-panel="workbench"' in page
    assert "机构、事件与趋势目录" in page
    for label in ("机构", "事件", "趋势"):
        assert f'data-research-tab="{label}"' in page or f">{label}<" in page
    assert 'id="researchSearch"' in page
    assert 'id="researchFilter"' in page
    assert "当前判断" in page
    assert "本期变化" in page
    assert "事实与阐述" in page
    assert "待验证" in page
    assert "信源索引" in page
    assert "本页目录" in page
    assert "相关研究" in page
    assert "相关材料" in page
    assert "返回目录" in page
    assert "即将推出" in page
    assert "工作台" in page
    assert "时间线、AIHOT 简报" in page
    assert "打开 →" in js
    assert "config/topics.json" in js
    assert "AI 草稿" in js
    assert 'topic.group === "company"' in js
    company = js.split("function companyTopics()")[1].split("function trendTopics()")[0]
    assert ".sort(" not in company
    assert 'params.set("space", "research")' in research
    assert 'params.set("space", "workbench")' in workbench
    assert "/ai-news-radar/" not in research
    assert "/ai-news-radar/" not in workbench
    assert "mau" not in js.lower()


def test_old_radar_home_moves_to_feed_without_absolute_pages_paths():
    view_mode = read("assets/view-mode.js")
    sidebar = read("assets/sidebar.js")
    feed = read("feed/index.html")

    assert 'view === "classic" ? "classic/" : "feed/"' in view_mode
    assert 'return "feed/"' in sidebar
    assert "<base href=\"../\" />" in feed
    assert 'data-root="../"' in feed
    assert 'href="/ai-news-radar/' not in feed
    assert 'src="/ai-news-radar/' not in feed
