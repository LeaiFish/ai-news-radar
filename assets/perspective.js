(function () {
  "use strict";

  const THEME_KEY = "aiNewsRadarTheme";
  const THEMES = ["dark", "system", "light"];

  function readTheme() {
    try {
      const value = window.localStorage.getItem(THEME_KEY) || "system";
      return THEMES.includes(value) ? value : "system";
    } catch {
      return "system";
    }
  }

  function resolvedTheme(theme) {
    if (theme === "dark" || theme === "light") return theme;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function applyTheme(theme) {
    const next = THEMES.includes(theme) ? theme : "system";
    document.documentElement.dataset.theme = next;
    const resolved = resolvedTheme(next);
    document.documentElement.style.colorScheme = resolved;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = resolved === "dark" ? "#161513" : "#f6f6f2";
    document.querySelectorAll("[data-radar-theme]").forEach((button) => {
      const active = button.dataset.radarTheme === next;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    try {
      window.localStorage.setItem(THEME_KEY, next);
    } catch {
      // Storage can be unavailable in private or hardened browser contexts.
    }
  }

  applyTheme(readTheme());
  document.querySelectorAll("[data-radar-theme]").forEach((button) => {
    button.addEventListener("click", () => applyTheme(button.dataset.radarTheme || "system"));
  });
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (readTheme() === "system") applyTheme("system");
  });

  const ROOT = new URL(document.documentElement.dataset.root || "./", window.location.href);
  const LENSES = {
    community: "社区 x AI 应用",
    toc: "ToC 视角",
    product: "产品层优先",
  };
  const SPACES = {
    overview: "竞争概览",
    research: "主题研究",
    workbench: "工作台",
  };
  const DOMESTIC = [
    { id: "doubao", name: "豆包", aliases: ["豆包", "Doubao", "即梦", "Seedream", "火山方舟"] },
    { id: "qwen", name: "通义千问", aliases: ["千问", "Qwen", "通义"] },
    { id: "hunyuan", name: "混元 / 元宝", aliases: ["混元", "Hunyuan", "元宝"] },
    { id: "quark", name: "夸克", aliases: ["夸克"] },
    { id: "kimi", name: "Kimi", aliases: ["Kimi", "月之暗面"] },
    { id: "deepseek", name: "DeepSeek", aliases: ["DeepSeek", "深度求索"] },
    { id: "minimax", name: "MiniMax", aliases: ["MiniMax", "海螺"] },
    { id: "zhipu", name: "智谱", aliases: ["智谱", "ChatGLM", "GLM-"] },
  ];
  const OVERSEAS = [
    { id: "openai", name: "ChatGPT", aliases: ["OpenAI", "ChatGPT", "GPT-5", "Sora"] },
    { id: "anthropic", name: "Claude", aliases: ["Anthropic", "Claude"] },
    { id: "google-gemini", name: "Gemini", aliases: ["Gemini", "DeepMind"] },
    { id: "meta-llama", name: "Llama", aliases: ["Llama", "Meta AI"] },
    { id: "xai", name: "Grok", aliases: ["Grok", "xAI"] },
    { id: "perplexity", name: "Perplexity", aliases: ["Perplexity"] },
    { id: "apple", name: "Apple Intelligence", aliases: ["Apple Intelligence"] },
    { id: "microsoft", name: "Copilot", aliases: ["Copilot"] },
    { id: "nvidia", name: "NVIDIA", aliases: ["NVIDIA", "英伟达", "Nemotron"] },
    { id: "huggingface", name: "Hugging Face", aliases: ["Hugging Face", "HuggingFace"] },
    { id: "cursor", name: "Cursor", aliases: ["Cursor"] },
    { id: "openrouter", name: "OpenRouter", aliases: ["OpenRouter"] },
  ];

  const dataBaseUrl = resolveDataBaseUrl();
  const state = {
    space: document.documentElement.dataset.space || "overview",
    lens: "product",
    month: "",
    currentMonth: "",
    generatedAt: "",
    windowHours: 24,
    briefItems: [],
    stories: [],
    storiesLoaded: false,
    topics: [],
    topicConfig: [],
    topicGroups: [],
    topicItems: {},
    storyIndex: [],
    researchReady: false,
  };

  const monthSelect = document.getElementById("monthSelect");
  const windowNote = document.getElementById("windowNote");
  const judgmentGrid = document.getElementById("judgmentGrid");
  const domesticBody = document.getElementById("domesticBody");
  const overseasBody = document.getElementById("overseasBody");
  const relatedList = document.getElementById("relatedList");
  const overviewLive = document.getElementById("overviewLive");
  const overviewEmpty = document.getElementById("overviewEmpty");
  const lensNote = document.getElementById("lensNote");
  const sidebar = document.getElementById("sidebar");
  const scrim = document.getElementById("scrim");
  const navToggle = document.getElementById("navToggle");

  function resolveDataBaseUrl() {
    let fromQuery = "";
    try {
      fromQuery = new URLSearchParams(window.location.search).get("data") || "";
    } catch {
      fromQuery = "";
    }
    if (fromQuery) {
      const normalized = fromQuery.trim().replace(/\/+$/, "");
      try { window.localStorage.setItem("dataBaseUrl", normalized); } catch { /* private mode */ }
      return normalized;
    }
    try {
      return (window.localStorage.getItem("dataBaseUrl") || "").trim().replace(/\/+$/, "");
    } catch {
      return "";
    }
  }

  function dataUrl(path) {
    if (!dataBaseUrl) return new URL(path, ROOT).href;
    const file = String(path || "").split("/").pop();
    return `${dataBaseUrl}/${file}`;
  }

  function readParam(name) {
    try {
      return new URLSearchParams(window.location.search).get(name) || "";
    } catch {
      return "";
    }
  }

  function replaceParams(updates) {
    const url = new URL(window.location.href);
    Object.entries(updates).forEach(([key, value]) => {
      if (!value) url.searchParams.delete(key);
      else url.searchParams.set(key, value);
    });
    const next = `${url.pathname}${url.search}${url.hash}`;
    const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    if (next !== current) window.history.replaceState(null, "", next);
  }

  async function loadJson(path) {
    const response = await fetch(`${dataUrl(path)}?t=${Date.now()}`);
    if (!response.ok) throw new Error(`${path} ${response.status}`);
    return response.json();
  }

  async function loadSiteJson(path) {
    const response = await fetch(`${new URL(path, ROOT).href}?t=${Date.now()}`);
    if (!response.ok) throw new Error(`${path} ${response.status}`);
    return response.json();
  }

  function monthKey(iso) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "";
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Shanghai",
      year: "numeric",
      month: "2-digit",
    }).format(date);
    return parts.slice(0, 7);
  }

  function formatMonth(key) {
    const match = /^(\d{4})-(\d{2})$/.exec(key || "");
    if (!match) return "当前窗口";
    return `${match[1]}年${Number(match[2])}月`;
  }

  function shiftMonth(key, delta) {
    const match = /^(\d{4})-(\d{2})$/.exec(key || "");
    if (!match) return "";
    const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1 + delta, 1));
    const year = date.getUTCFullYear();
    const month = String(date.getUTCMonth() + 1).padStart(2, "0");
    return `${year}-${month}`;
  }

  function formatStamp(iso) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "";
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: "Asia/Shanghai",
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).formatToParts(date);
    const value = (type) => parts.find((part) => part.type === type)?.value || "";
    return `${Number(value("month"))}月${Number(value("day"))}日 ${value("hour")}:${value("minute")}`;
  }

  function preferZh(title) {
    const text = String(title || "").replace(/\s+/g, " ").trim();
    if (!text) return "未命名更新";
    const parts = text.split(/\s+\/\s+/);
    const zh = parts.find((part) => /[\u4e00-\u9fff]/.test(part));
    return (zh || parts[0]).trim();
  }

  function shortText(text, limit) {
    const value = String(text || "").replace(/\s+/g, " ").trim();
    if (value.length <= limit) return value;
    return `${value.slice(0, limit)}…`;
  }

  function safeHttpUrl(value) {
    try {
      const url = new URL(String(value || ""), window.location.href);
      if (url.protocol === "http:" || url.protocol === "https:") return url.href;
    } catch {
      return "";
    }
    return "";
  }

  function storyBlob(story) {
    const primary = story.primary_item || {};
    return [
      story.title,
      primary.title,
      primary.title_zh,
      primary.title_en,
      primary.title_original,
      primary.summary,
    ].filter(Boolean).join(" ");
  }

  function storyUrl(story) {
    const primary = story.primary_item || {};
    return safeHttpUrl(primary.url || story.primary_url || story.url);
  }

  function matchesAlias(blob, alias) {
    if (!alias) return false;
    return blob.toLowerCase().includes(String(alias).toLowerCase());
  }

  function collectRows(products) {
    return products.map((product) => {
      const hits = state.stories.filter((story) => (
        product.aliases.some((alias) => matchesAlias(storyBlob(story), alias))
      ));
      hits.sort((a, b) => String(b.latest_at || "").localeCompare(String(a.latest_at || "")));
      const latest = hits[0];
      return {
        ...product,
        count: hits.length,
        note: latest ? preferZh(latest.title) : "",
        url: latest ? storyUrl(latest) : "",
      };
    }).filter((row) => row.count > 0)
      .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "zh"))
      .slice(0, 6);
  }

  function judgmentScore(item) {
    const importance = Number(item.importance_score || item.importance || 0);
    const sources = Number(item.source_count || (item.sources || []).length || 1);
    const multi = sources >= 2 ? 0.35 : 0;
    const label = String(item.importance_label || "");
    const boost = /高|官方|重要/.test(label) ? 0.15 : 0;
    const zh = /[\u4e00-\u9fff]/.test(String(item.title || "")) ? 0.12 : 0;
    return importance + multi + boost + zh;
  }

  function pickJudgments() {
    return state.briefItems
      .map((item, index) => ({ item, index, score: judgmentScore(item) }))
      .sort((a, b) => b.score - a.score || a.index - b.index)
      .slice(0, 3)
      .map((entry) => entry.item);
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  const INTERNAL_METRIC = "内部信息，待接入";

  function renderMetricRow(row) {
    const tr = document.createElement("tr");
    const product = el("td");
    product.append(el("span", "product-name", row.name));
    const noteCell = el("td");
    const note = shortText(row.note, 42);
    if (row.url) {
      const link = el("a", "note-link", note);
      link.href = row.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      noteCell.append(link);
    } else {
      noteCell.textContent = note || "本窗口有相关故事";
    }
    tr.append(
      product,
      el("td", "metric-pending", INTERNAL_METRIC),
      el("td", "metric-pending", INTERNAL_METRIC),
      el("td", "metric-pending", INTERNAL_METRIC),
      noteCell,
    );
    return tr;
  }

  function renderTable(body, rows) {
    clear(body);
    if (!rows.length) {
      const tr = document.createElement("tr");
      const td = el("td", "empty-copy", "当前窗口没有匹配到这类产品的故事。");
      td.colSpan = 5;
      tr.append(td);
      body.append(tr);
      return;
    }
    rows.forEach((row) => body.append(renderMetricRow(row)));
  }

  function renderJudgments() {
    clear(judgmentGrid);
    const items = pickJudgments();
    if (!items.length) {
      judgmentGrid.append(el("p", "placeholder-line", "当日简报暂时没有可用条目。"));
      return;
    }
    items.forEach((item) => {
      const card = el("article", "judgment-card news-card");
      const top = el("div", "judgment-top");
      top.append(el("h3", null, preferZh(item.title)));
      top.append(el("span", "tag tag-draft ai-tag", "AI 草稿"));
      card.append(top);
      const summary = String(item.primary_item?.summary || item.summary || "").trim();
      if (summary) card.append(el("p", "judgment-summary", summary));
      const sources = Number(item.source_count || (item.sources || []).length || 1);
      const label = item.importance_label || "未分级";
      card.append(el("p", "judgment-meta", `来自当日简报 · ${label} · ${sources} 家信源`));
      const href = safeHttpUrl(item.primary_url || item.url || item.primary_item?.url);
      if (href) {
        const link = el("a", "source-link", "查看来源");
        link.href = href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        card.append(link);
      }
      judgmentGrid.append(card);
    });
  }

  function renderRelated() {
    const lensTopics = state.topics.filter((topic) => topic.group === "lens" && Number(topic.item_count) > 0).slice(0, 4);
    if (!lensTopics.length || !relatedList) return;
    clear(relatedList);
    lensTopics.forEach((topic) => {
      const link = el("a", "ai-tag", topic.name || topic.id);
      link.href = new URL(`topics/${encodeURIComponent(topic.id)}/`, ROOT).href;
      relatedList.append(link);
    });
  }

  function renderWindowNote() {
    const stamp = formatStamp(state.generatedAt);
    const when = stamp ? `更新于 ${stamp}` : "更新时间待接入";
    windowNote.textContent = `${when} · 数据窗 ${state.windowHours} 小时 · 核心指标、本月值与环比为内部信息，待接入`;
  }

  function renderMonthSelect() {
    const months = [0, 1, 2].map((delta) => shiftMonth(state.currentMonth, -delta)).filter(Boolean);
    clear(monthSelect);
    months.forEach((key) => {
      const option = el("option", null, formatMonth(key));
      option.value = key;
      monthSelect.append(option);
    });
    if (!months.includes(state.month)) state.month = state.currentMonth;
    monthSelect.value = state.month;
  }

  function applyMonth() {
    const live = state.month === state.currentMonth;
    overviewLive.hidden = !live;
    overviewEmpty.hidden = live;
  }

  function applyLens(lens) {
    state.lens = LENSES[lens] ? lens : "product";
    document.querySelectorAll("[data-lens]").forEach((button) => {
      button.setAttribute("aria-pressed", button.dataset.lens === state.lens ? "true" : "false");
    });
    lensNote.textContent = `当前标记：${LENSES[state.lens]}。视角筛选尚未接入。`;
  }

  function applySpace(space) {
    state.space = SPACES[space] ? space : "overview";
    document.documentElement.dataset.space = state.space;
    document.title = `${SPACES[state.space]} · AI Perspective`;
    document.querySelectorAll("[data-space-link]").forEach((link) => {
      if (link.dataset.spaceLink === state.space) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  }

  function preserveNavLinks() {
    const params = new URLSearchParams(window.location.search);
    ["space", "month", "tab", "kind", "id"].forEach((key) => params.delete(key));
    document.querySelectorAll("[data-space-link]").forEach((link) => {
      const next = new URLSearchParams(params);
      const space = link.dataset.spaceLink;
      if (space && space !== "overview") next.set("space", space);
      const query = next.toString();
      link.setAttribute("href", query ? `./?${query}` : "./");
    });
  }

  function renderOverview() {
    renderWindowNote();
    applyMonth();
    if (state.month !== state.currentMonth) return;
    renderJudgments();
    renderTable(domesticBody, collectRows(DOMESTIC));
    renderTable(overseasBody, collectRows(OVERSEAS));
    renderRelated();
  }

  const RESEARCH_TABS = new Set(["all", "org", "event", "trend"]);
  const TAB_NOTES = {
    all: "按产业透镜、公司与模型、技术方向浏览。今日条数来自当前故事窗。",
    org: "公司与模型按主题配置的顺序排列。今日条数来自当前故事窗。",
    event: "事件来自当前故事窗里的多源、官方或高重要度条目。",
    trend: "产业透镜与技术方向分开排列。今日条数来自当前故事窗。",
  };
  const TOPIC_GROUP_FALLBACK = [
    { id: "lens", name: "产业透镜", description: "从收费、入口、Agent 落地与办公组织看产业怎么走" },
    { id: "company", name: "公司与模型", description: "按厂商与模型系追踪：谁发了什么、又赢了哪一局" },
    { id: "tech", name: "技术方向", description: "按技术领域深挖：Agent、编码、多模态、端侧与开源" },
  ];
  let packToken = 0;

  function currentTab() {
    const tab = document.documentElement.dataset.researchTab || "all";
    return RESEARCH_TABS.has(tab) ? tab : "all";
  }

  function escapeRegExp(value) {
    return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function termMatches(term, text) {
    const needle = String(term || "").trim();
    if (!needle || !text) return false;
    if (/[\u4e00-\u9fff]/.test(needle)) return text.toLowerCase().includes(needle.toLowerCase());
    return new RegExp(`(?<![A-Za-z0-9])${escapeRegExp(needle)}(?![A-Za-z0-9])`, "i").test(text);
  }

  function storyText(story) {
    const parts = [];
    const pushRecord = (record) => {
      if (!record || typeof record !== "object") return;
      ["title", "title_zh", "title_en", "title_original", "summary", "source", "source_name", "site_name"].forEach((key) => {
        if (record[key]) parts.push(String(record[key]));
      });
    };
    pushRecord(story);
    pushRecord(story.primary_item);
    (story.sources || []).forEach(pushRecord);
    (story.items || []).forEach(pushRecord);
    return parts.join("\n");
  }

  function matchesTopic(text, topic) {
    const excludes = topic.exclude || [];
    if (excludes.some((term) => termMatches(term, text))) return false;
    const keywords = topic.keywords || [];
    if (keywords.some((term) => termMatches(term, text))) return true;
    const patterns = topic.patterns || [];
    return patterns.some((pattern) => {
      try {
        return new RegExp(pattern, "i").test(text);
      } catch {
        return false;
      }
    });
  }

  function rebuildStoryIndex() {
    state.storyIndex = state.stories.map((story) => ({ story, text: storyText(story) }));
  }

  function storiesForTopic(topic) {
    return state.storyIndex
      .filter((entry) => matchesTopic(entry.text, topic))
      .map((entry) => entry.story);
  }

  function companyTopics() {
    return state.topicConfig.filter((topic) => topic.group === "company");
  }

  function trendTopics() {
    const lens = state.topicConfig.filter((topic) => topic.group === "lens");
    const tech = state.topicConfig.filter((topic) => topic.group === "tech");
    return lens.concat(tech);
  }

  function isNotableEvent(story) {
    const sources = Number(story.source_count || (story.sources || []).length || 1);
    const label = String(story.importance_label || "");
    const importance = Number(story.importance_score || story.importance || 0);
    return sources >= 2 || /高|官方|重要/.test(label) || importance >= 0.8;
  }

  const WORKBENCH_STORY_LIMIT = 15;

  function storySourceCount(story) {
    const count = Number(story?.source_count);
    return Number.isFinite(count) ? count : 0;
  }

  function storyImportanceScore(story) {
    const raw = story?.importance_score ?? story?.importance ?? story?.score ?? 0;
    const score = Number(raw);
    return Number.isFinite(score) ? score : 0;
  }

  function workbenchTimelineStories() {
    const stories = state.stories.filter((story) => story && typeof story === "object");
    const tiered = stories.some((story) => story.tier === "selected" || story.tier === "all");
    if (tiered) {
      return {
        stories: stories.filter((story) => story.tier === "selected"),
        fallback: false,
      };
    }
    const ranked = stories.slice().sort((a, b) => {
      const bySources = storySourceCount(b) - storySourceCount(a);
      if (bySources) return bySources;
      const byScore = storyImportanceScore(b) - storyImportanceScore(a);
      if (byScore) return byScore;
      return String(a.story_id || "").localeCompare(String(b.story_id || ""));
    });
    return { stories: ranked.slice(0, WORKBENCH_STORY_LIMIT), fallback: true };
  }

  function storySourceLabel(story) {
    const primary = story.primary_item || {};
    const name = story.source_name || story.source || primary.source_name || primary.source || "";
    const count = storySourceCount(story);
    if (count > 1) return [name, `${count} 家信源`].filter(Boolean).join(" · ");
    return name;
  }

  function renderWorkbench() {
    const note = document.getElementById("workbenchNote");
    const list = document.getElementById("workbenchTimeline");
    if (!list) return;
    clear(list);
    if (!state.storiesLoaded) {
      if (note) note.textContent = "时间线没有载入。可以先打开完整雷达。";
      list.append(el("li", null, "时间线没有载入。"));
      return;
    }
    const { stories, fallback } = workbenchTimelineStories();
    const ordered = stories.slice().sort((a, b) => String(b.latest_at || b.earliest_at || "").localeCompare(String(a.latest_at || a.earliest_at || "")));
    if (note) {
      if (!ordered.length) {
        note.textContent = "今天还没有精选故事。";
      } else if (fallback) {
        note.textContent = `这份数据还没有精选标记，先按多源和重要度列出 ${ordered.length} 条。`;
      } else {
        note.textContent = `精选 ${ordered.length} 条`;
      }
    }
    if (!ordered.length) {
      list.append(el("li", null, "今天还没有精选故事。"));
      return;
    }
    ordered.forEach((story) => {
      const item = el("li");
      const when = story.latest_at || story.earliest_at || "";
      item.append(el("time", null, formatStamp(when) || "时间待补充"));
      const body = el("div");
      const title = preferZh(story.title || story.primary_item?.title);
      const href = storyUrl(story);
      if (href) {
        const link = el("a", "note-link", title);
        link.href = href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        body.append(link);
      } else {
        body.append(el("p", "timeline-title", title));
      }
      const source = storySourceLabel(story);
      if (source) body.append(el("p", "timeline-meta", source));
      item.append(body);
      list.append(item);
    });
  }

  function notableEvents() {
    return state.stories
      .filter((story) => story.story_id && isNotableEvent(story))
      .map((story, index) => ({ story, index, score: judgmentScore(story) }))
      .sort((a, b) => b.score - a.score || a.index - b.index)
      .slice(0, 24)
      .map((entry) => entry.story);
  }

  function researchHref({ tab, kind, id } = {}) {
    const params = new URLSearchParams(window.location.search);
    params.set("space", "research");
    params.delete("month");
    if (tab && tab !== "all") params.set("tab", tab);
    else params.delete("tab");
    if (kind && id) {
      params.set("kind", kind);
      params.set("id", id);
    } else {
      params.delete("kind");
      params.delete("id");
    }
    return `./?${params.toString()}`;
  }

  function writeResearchParams(updates, { push = false } = {}) {
    const url = new URL(window.location.href);
    url.searchParams.set("space", "research");
    Object.entries(updates).forEach(([key, value]) => {
      if (!value) url.searchParams.delete(key);
      else url.searchParams.set(key, value);
    });
    const next = `${url.pathname}${url.search}${url.hash}`;
    const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    if (next === current) return;
    if (push) window.history.pushState({ research: true }, "", next);
    else window.history.replaceState({ research: true }, "", next);
  }

  function isPlainClick(event) {
    return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
  }

  function fillFilterOptions(tab) {
    const select = document.getElementById("researchFilter");
    if (!select) return;
    const options = {
      all: [["all", "全部"], ["active", "今日有更新"], ["quiet", "今日无故事"]],
      org: [["all", "全部"], ["active", "今日有更新"], ["quiet", "今日无故事"], ["domestic", "国内"], ["overseas", "海外"]],
      event: [["all", "全部"], ["multi", "多源"], ["official", "官方更新"]],
      trend: [["all", "全部"], ["lens", "产业透镜"], ["tech", "技术方向"], ["active", "今日有更新"]],
    }[tab] || [["all", "全部"]];
    const previous = select.value;
    clear(select);
    options.forEach(([value, label]) => {
      const option = el("option", null, label);
      option.value = value;
      select.append(option);
    });
    select.value = options.some(([value]) => value === previous) ? previous : "all";
  }

  function syncResearchChrome() {
    const tab = currentTab();
    document.documentElement.dataset.researchTab = tab;
    document.querySelectorAll(".catalog-tab").forEach((button) => {
      const selected = button.dataset.researchTab === tab;
      button.setAttribute("aria-selected", selected ? "true" : "false");
      button.classList.toggle("active", selected);
    });
    fillFilterOptions(tab);
  }

  function topicRow(topic, kind) {
    const count = storiesForTopic(topic).length;
    const tags = [];
    if (kind === "org") tags.push(DOMESTIC.some((item) => item.id === topic.id) ? "国内" : "海外");
    else tags.push(topic.group === "lens" ? "产业透镜" : "技术方向");
    tags.push(count > 0 ? `今日 ${count} 条` : "今日无故事");
    return {
      kind,
      id: topic.id,
      name: topic.name || topic.id,
      blurb: topic.description || "",
      tags,
      count,
      group: topic.group,
      multi: false,
      official: false,
    };
  }

  function eventRow(story) {
    const sources = Number(story.source_count || 1);
    const label = story.importance_label || "";
    const summary = String(story.primary_item?.summary || story.summary || "").trim();
    const names = (story.source_names || []).slice(0, 3).join("、");
    const blurb = summary
      ? shortText(summary, 96)
      : (names || "当前窗口里的一条故事");
    const tags = [];
    if (label) tags.push(label);
    tags.push(sources >= 2 ? `多源 ${sources}` : "单源");
    return {
      kind: "event",
      id: story.story_id,
      name: preferZh(story.title),
      blurb,
      tags,
      count: sources,
      group: "",
      multi: sources >= 2,
      official: /官方/.test(label),
    };
  }

  function catalogRows(tab) {
    if (tab === "event") return notableEvents().map(eventRow);
    if (tab === "trend") return trendTopics().map((topic) => topicRow(topic, "trend"));
    return companyTopics().map((topic) => topicRow(topic, "org"));
  }

  function passesFilter(row) {
    const filter = document.getElementById("researchFilter")?.value || "all";
    if (filter === "all") return true;
    if (filter === "active") return row.count > 0;
    if (filter === "quiet") return row.count === 0;
    if (filter === "domestic") return DOMESTIC.some((item) => item.id === row.id);
    if (filter === "overseas") return row.kind === "org" && !DOMESTIC.some((item) => item.id === row.id);
    if (filter === "multi") return row.multi;
    if (filter === "official") return row.official;
    if (filter === "lens") return row.group === "lens";
    if (filter === "tech") return row.group === "tech";
    return true;
  }

  function passesQuery(row) {
    const query = (document.getElementById("researchSearch")?.value || "").trim().toLowerCase();
    if (!query) return true;
    return `${row.name} ${row.blurb} ${row.id}`.toLowerCase().includes(query);
  }

  function renderCatalogCard(row) {
    const card = el("a", "topic-card");
    card.href = researchHref({ tab: currentTab(), kind: row.kind, id: row.id });
    card.dataset.packKind = row.kind;
    card.dataset.packId = row.id;
    card.append(el("h3", null, row.name));
    if (row.blurb) card.append(el("p", "topic-card-blurb", row.blurb));
    const countTag = row.tags.find((tag) => tag.startsWith("今日") || tag === "单源" || /^多源 \d+$/.test(tag));
    const rest = row.tags.filter((tag) => tag !== countTag);
    const meta = el("div", "topic-card-meta");
    if (countTag) meta.append(el("strong", null, countTag));
    if (rest.length) meta.append(el("span", null, rest.join(" · ")));
    if (meta.childNodes.length) card.append(meta);
    return card;
  }

  function configuredGroups() {
    const fromConfig = (state.topicGroups || []).filter((group) => group && group.id);
    return fromConfig.length ? fromConfig : TOPIC_GROUP_FALLBACK;
  }

  function groupsForTab(tab) {
    const groups = configuredGroups();
    if (tab === "org") return groups.filter((group) => group.id === "company");
    if (tab === "trend") return groups.filter((group) => group.id === "lens" || group.id === "tech");
    if (tab === "event") return [];
    return groups;
  }

  function renderGroupSection(group, rows) {
    const section = el("section", "topics-group");
    const head = el("div", "topics-group-head");
    head.append(el("h2", null, group.name || group.id));
    if (group.description) head.append(el("p", null, group.description));
    const grid = el("div", "topics-grid");
    rows.forEach((row) => grid.append(renderCatalogCard(row)));
    section.append(head, grid);
    return section;
  }

  function renderCatalog() {
    const list = document.getElementById("researchList");
    const note = document.getElementById("researchNote");
    if (!list) return;
    const tab = currentTab();
    if (note) note.textContent = TAB_NOTES[tab];
    clear(list);
    if (!state.researchReady) {
      list.append(el("p", "placeholder-line", "正在整理目录…"));
      return;
    }
    if (!state.topicConfig.length && tab !== "event") {
      list.append(el("p", "placeholder-line", "主题配置没有载入。"));
      return;
    }
    if (tab === "event" && !state.stories.length) {
      list.append(el("p", "placeholder-line", "当前故事窗没有载入。"));
      return;
    }
    if (tab === "event") {
      const rows = catalogRows("event").filter(passesFilter).filter(passesQuery);
      if (!rows.length) {
        list.append(el("p", "placeholder-line", "没有匹配的条目。"));
        return;
      }
      const grid = el("div", "topics-grid");
      rows.forEach((row) => grid.append(renderCatalogCard(row)));
      list.append(grid);
      return;
    }
    const groups = groupsForTab(tab);
    let shown = 0;
    groups.forEach((group) => {
      const rows = state.topicConfig
        .filter((topic) => topic.group === group.id)
        .map((topic) => topicRow(topic, group.id === "company" ? "org" : "trend"))
        .filter(passesFilter)
        .filter(passesQuery);
      if (!rows.length) return;
      shown += rows.length;
      list.append(renderGroupSection(group, rows));
    });
    if (!shown) list.append(el("p", "placeholder-line", "没有匹配的条目。"));
  }

  function setResearchTab(tab, { push = false } = {}) {
    const next = RESEARCH_TABS.has(tab) ? tab : "org";
    document.documentElement.dataset.researchTab = next;
    syncResearchChrome();
    const select = document.getElementById("researchFilter");
    if (select) select.value = "all";
    writeResearchParams({ tab: next === "all" ? "" : next, kind: "", id: "" }, { push });
    document.documentElement.dataset.researchView = "catalog";
    document.title = "主题研究 · AI Perspective";
    const main = document.getElementById("main");
    if (main) main.scrollTop = 0;
    renderCatalog();
  }

  function lookupRecord(kind, id) {
    if (kind === "event") {
      const story = state.stories.find((item) => item.story_id === id);
      if (!story) return null;
      return {
        kind,
        id,
        name: preferZh(story.title),
        description: "",
        group: "",
        windowStories: [story],
        story,
      };
    }
    const pool = kind === "trend" ? trendTopics() : companyTopics();
    const topic = pool.find((item) => item.id === id);
    if (!topic) return null;
    return {
      kind,
      id: topic.id,
      name: topic.name || topic.id,
      description: topic.description || "",
      group: topic.group,
      windowStories: storiesForTopic(topic).sort((a, b) => String(b.latest_at || "").localeCompare(String(a.latest_at || ""))),
      story: null,
    };
  }

  function topicItemBeat(item) {
    return {
      title: item.title || "",
      url: safeHttpUrl(item.url),
      source: item.source || item.source_name || "",
      published_at: item.published_at || "",
      summary: item.summary || "",
      sourceCount: Number(item.source_count || 1),
    };
  }

  function storyBeat(story) {
    return {
      title: story.title || "",
      url: storyUrl(story),
      source: story.source || (story.source_names || [])[0] || "",
      published_at: story.latest_at || story.earliest_at || "",
      summary: story.primary_item?.summary || story.summary || "",
      sourceCount: Number(story.source_count || 1),
    };
  }

  function eventBeats(story) {
    const rows = Array.isArray(story.items) && story.items.length ? story.items : (story.sources || []);
    const beats = rows.map((item) => ({
      title: item.title || story.title || "",
      url: safeHttpUrl(item.url),
      source: item.source || item.source_name || "",
      published_at: item.published_at || story.latest_at || "",
      summary: item.summary || "",
      sourceCount: 1,
    }));
    if (!beats.length) beats.push(storyBeat(story));
    beats.sort((a, b) => String(b.published_at).localeCompare(String(a.published_at)));
    return beats;
  }

  async function loadTopicItems(id) {
    if (Object.prototype.hasOwnProperty.call(state.topicItems, id)) return state.topicItems[id];
    try {
      const payload = await loadJson(`data/topics/${id}.json`);
      state.topicItems[id] = Array.isArray(payload.items) ? payload.items : [];
    } catch {
      state.topicItems[id] = [];
    }
    return state.topicItems[id];
  }

  function appendJudgmentCard(slot, title, meta, url) {
    const card = el("article", "judgment-card news-card");
    const top = el("div", "judgment-top");
    top.append(el("h3", null, title), el("span", "tag tag-draft ai-tag", "AI 草稿"));
    card.append(top, el("p", "judgment-meta", meta));
    const href = safeHttpUrl(url);
    if (href) {
      const link = el("a", "source-link", "查看来源");
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      card.append(link);
    }
    slot.append(card);
  }

  function renderJudgment(record, beats) {
    const slot = document.getElementById("packJudgment");
    clear(slot);
    const top = record.windowStories
      .map((story, index) => ({ story, index, score: judgmentScore(story) }))
      .sort((a, b) => b.score - a.score || a.index - b.index)[0]?.story;
    if (top) {
      const brief = state.briefItems.find((item) => item.story_id === top.story_id);
      const label = brief?.importance_label || top.importance_label || "未分级";
      const sources = Number(top.source_count || brief?.source_count || 1);
      appendJudgmentCard(
        slot,
        preferZh(brief?.title || top.title),
        `依据当前数据窗 · ${label} · ${sources} 家信源`,
        storyUrl(top),
      );
      return;
    }
    const beat = beats[0];
    if (beat && beat.title) {
      appendJudgmentCard(slot, preferZh(beat.title), "依据主题目录最近一条。这条不在当前数据窗里。", beat.url);
      return;
    }
    slot.append(el("p", "placeholder-line", "当前窗口和主题目录里都没有足够信号，判断先留白。"));
  }

  function deltaItem(title, url, published) {
    const li = el("li");
    const href = safeHttpUrl(url);
    const label = preferZh(title);
    if (href) {
      const link = el("a", "note-link", label);
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      li.append(link);
    } else {
      li.append(document.createTextNode(label));
    }
    li.append(el("span", "delta-meta", ` · ${formatStamp(published) || "时间待补充"}`));
    return li;
  }

  function renderDelta(record) {
    const slot = document.getElementById("packDelta");
    clear(slot);
    if (record.kind === "event") {
      const beats = eventBeats(record.story);
      if (beats.length <= 1) {
        slot.append(el("p", "placeholder-line", "本期报道集中在这一条。"));
        return;
      }
      const list = el("ul", "delta-list");
      beats.slice(0, 6).forEach((beat) => list.append(deltaItem(beat.title, beat.url, beat.published_at)));
      slot.append(list);
      return;
    }
    const stories = record.windowStories.slice(0, 4);
    if (!stories.length) {
      slot.append(el("p", "placeholder-line", "这个数据窗里没有新的匹配故事。"));
      return;
    }
    const list = el("ul", "delta-list");
    stories.forEach((story) => list.append(deltaItem(story.title, storyUrl(story), story.latest_at || story.earliest_at)));
    slot.append(list);
  }

  function renderTimeline(beats) {
    const slot = document.getElementById("packFacts");
    clear(slot);
    if (!beats.length) {
      slot.append(el("p", "placeholder-line", "还没有可排列的相关故事。"));
      return;
    }
    const shown = beats.slice(0, 12);
    const list = el("ol", "timeline");
    shown.forEach((beat) => {
      const li = el("li");
      li.append(el("time", null, formatStamp(beat.published_at) || "时间待补充"));
      const body = el("div");
      const label = preferZh(beat.title);
      if (beat.url) {
        const link = el("a", "note-link", label);
        link.href = beat.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        body.append(link);
      } else {
        body.append(el("p", "timeline-title", label));
      }
      const meta = [beat.source, beat.sourceCount > 1 ? `${beat.sourceCount} 家信源` : ""].filter(Boolean).join(" · ");
      if (meta) body.append(el("p", "timeline-meta", meta));
      const summary = String(beat.summary || "").trim();
      if (summary) body.append(el("p", "timeline-summary", shortText(summary, 140)));
      li.append(body);
      list.append(li);
    });
    slot.append(list);
    if (beats.length > shown.length) {
      slot.append(el("p", "timeline-more", `目录里还有 ${beats.length - shown.length} 条，这里先列最近 12 条。`));
    }
  }

  function renderOpenQuestions(record, beats) {
    const slot = document.getElementById("packOpen");
    clear(slot);
    const notes = [];
    const top = record.windowStories[0];
    const sources = Number(top?.source_count || beats[0]?.sourceCount || 0);
    if (!top && !beats.length) notes.push("信号不足，待验证先留白。");
    else if (sources && sources < 2) notes.push("目前主要是单源，交叉验证待接入。");
    if (top && !String(top.primary_item?.summary || top.summary || "").trim()) {
      notes.push("摘要字段为空，阐述先用标题。");
    }
    notes.push("人工确认与 Rubric 打分待接入。");
    const list = el("ul", "open-list");
    notes.forEach((note) => list.append(el("li", null, note)));
    slot.append(list);
  }

  function renderSourceIndex(beats) {
    const slot = document.getElementById("packSources");
    clear(slot);
    const seen = new Set();
    const rows = [];
    beats.forEach((beat) => {
      const key = beat.url || beat.source;
      if (!key || seen.has(key)) return;
      seen.add(key);
      rows.push(beat);
    });
    if (!rows.length) {
      slot.append(el("p", "placeholder-line", "信源索引待补充。"));
      return;
    }
    const list = el("ul", "source-index");
    rows.slice(0, 10).forEach((beat) => {
      const li = el("li");
      const label = beat.source || "来源";
      if (beat.url) {
        const link = el("a", null, label);
        link.href = beat.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        li.append(link);
        if (beat.title) li.append(el("span", "source-title", ` · ${shortText(preferZh(beat.title), 36)}`));
      } else {
        li.textContent = label;
      }
      list.append(li);
    });
    slot.append(list);
  }

  function renderPackRail(record, beats) {
    const related = document.getElementById("packRelated");
    const materials = document.getElementById("packMaterials");
    clear(related);
    clear(materials);
    let topics = [];
    if (record.kind === "event") {
      const text = storyText(record.story);
      topics = companyTopics().filter((topic) => matchesTopic(text, topic)).slice(0, 4);
    } else {
      const siblings = state.topicConfig.filter((topic) => topic.group === record.group && topic.id !== record.id);
      const active = siblings.filter((topic) => storiesForTopic(topic).length > 0);
      topics = (active.length ? active : siblings).slice(0, 4);
    }
    if (!topics.length) related.append(el("p", "toc-empty", "暂无"));
    topics.forEach((topic) => {
      const kind = record.kind === "trend" ? "trend" : "org";
      const link = el("a", null, topic.name || topic.id);
      link.href = researchHref({ tab: kind === "trend" ? "trend" : "org", kind, id: topic.id });
      link.dataset.packKind = kind;
      link.dataset.packId = topic.id;
      related.append(link);
    });
    if (record.kind !== "event") {
      const library = el("a", null, "主题库页面");
      library.href = new URL(`topics/${encodeURIComponent(record.id)}/`, ROOT).href;
      materials.append(library);
    }
    const sourceUrl = record.kind === "event" ? storyUrl(record.story) : (beats[0] && beats[0].url);
    if (sourceUrl) {
      const link = el("a", null, "最新来源");
      link.href = sourceUrl;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      materials.append(link);
    }
    if (!materials.childNodes.length) materials.append(el("p", "toc-empty", "暂无"));
  }

  function clearPackSlots(message) {
    ["packJudgment", "packDelta", "packFacts", "packOpen", "packSources"].forEach((id) => {
      const slot = document.getElementById(id);
      if (!slot) return;
      clear(slot);
      if (message) slot.append(el("p", "placeholder-line", message));
    });
  }

  async function renderPack(kind, id) {
    const title = document.getElementById("packTitle");
    const lede = document.getElementById("packLede");
    const back = document.getElementById("packBack");
    if (back) back.href = researchHref({ tab: currentTab() });
    if (!state.researchReady) {
      if (title) title.textContent = "正在打开";
      if (lede) lede.textContent = "正在读取目录…";
      clearPackSlots("正在整理…");
      return;
    }
    const token = ++packToken;
    const record = lookupRecord(kind, id);
    if (!record) {
      if (title) title.textContent = "未找到条目";
      if (lede) lede.textContent = "这个条目不在当前目录里。";
      document.title = "未找到条目 · 主题研究 · AI Perspective";
      clearPackSlots("这个条目没有事实包。");
      clear(document.getElementById("packRelated"));
      clear(document.getElementById("packMaterials"));
      return;
    }
    if (title) title.textContent = record.name;
    if (lede) {
      if (record.kind === "event") {
        const names = (record.story.source_names || []).join("、");
        lede.textContent = [record.story.importance_label, names].filter(Boolean).join(" · ");
      } else {
        lede.textContent = record.description;
      }
    }
    document.title = `${record.name} · 主题研究 · AI Perspective`;
    clearPackSlots("正在整理相关故事…");
    let beats = [];
    if (record.kind === "event") {
      beats = eventBeats(record.story);
    } else {
      const items = await loadTopicItems(record.id);
      if (token !== packToken) return;
      beats = items.map(topicItemBeat).sort((a, b) => String(b.published_at).localeCompare(String(a.published_at)));
      if (!beats.length) beats = record.windowStories.map(storyBeat);
    }
    if (token !== packToken) return;
    renderJudgment(record, beats);
    renderDelta(record);
    renderTimeline(beats);
    renderOpenQuestions(record, beats);
    renderSourceIndex(beats);
    renderPackRail(record, beats);
  }

  function openResearchPack(kind, id, { push = true } = {}) {
    const tab = currentTab() === "all"
      ? "all"
      : (kind === "event" ? "event" : (kind === "trend" ? "trend" : "org"));
    document.documentElement.dataset.researchTab = tab;
    syncResearchChrome();
    writeResearchParams({ tab: tab === "all" ? "" : tab, kind, id }, { push });
    document.documentElement.dataset.researchView = "pack";
    const main = document.getElementById("main");
    if (main) main.scrollTop = 0;
    renderPack(kind, id);
  }

  function renderResearch() {
    if (state.space !== "research") return;
    const kind = readParam("kind");
    const id = readParam("id");
    if (id && RESEARCH_TABS.has(kind)) {
      document.documentElement.dataset.researchView = "pack";
      renderPack(kind, id);
      return;
    }
    document.documentElement.dataset.researchView = "catalog";
    if (state.space === "research") document.title = "主题研究 · AI Perspective";
    renderCatalog();
  }

  function setMenu(open) {
    sidebar.classList.toggle("is-open", open);
    scrim.hidden = !open;
    navToggle.setAttribute("aria-expanded", open ? "true" : "false");
  }

  monthSelect.addEventListener("change", () => {
    state.month = monthSelect.value;
    replaceParams({ month: state.month === state.currentMonth ? "" : state.month });
    applyMonth();
    if (state.month === state.currentMonth) renderOverview();
  });

  document.querySelectorAll("[data-lens]").forEach((button) => {
    button.addEventListener("click", () => {
      applyLens(button.dataset.lens || "product");
      replaceParams({ lens: state.lens === "product" ? "" : state.lens });
      preserveNavLinks();
    });
  });

  navToggle.addEventListener("click", () => {
    setMenu(!sidebar.classList.contains("is-open"));
  });
  scrim.addEventListener("click", () => setMenu(false));
  sidebar.addEventListener("click", (event) => {
    if (event.target.closest("[data-radar-theme]")) return;
    if (event.target.closest("a, button")) setMenu(false);
  });

  document.querySelectorAll(".catalog-tab").forEach((button) => {
    button.addEventListener("click", () => setResearchTab(button.dataset.researchTab || "org", { push: true }));
  });
  document.getElementById("researchSearch")?.addEventListener("input", () => {
    if (document.documentElement.dataset.researchView !== "pack") renderCatalog();
  });
  document.getElementById("researchFilter")?.addEventListener("change", () => renderCatalog());
  document.getElementById("researchList")?.addEventListener("click", (event) => {
    const link = event.target.closest("[data-pack-kind]");
    if (!link || !isPlainClick(event)) return;
    event.preventDefault();
    openResearchPack(link.dataset.packKind, link.dataset.packId);
  });
  document.getElementById("packRelated")?.addEventListener("click", (event) => {
    const link = event.target.closest("[data-pack-kind]");
    if (!link || !isPlainClick(event)) return;
    event.preventDefault();
    openResearchPack(link.dataset.packKind, link.dataset.packId);
  });
  document.getElementById("packBack")?.addEventListener("click", (event) => {
    if (!isPlainClick(event)) return;
    event.preventDefault();
    const tab = currentTab();
    writeResearchParams({ tab: tab === "all" ? "" : tab, kind: "", id: "" }, { push: true });
    document.documentElement.dataset.researchView = "catalog";
    document.title = "主题研究 · AI Perspective";
    const main = document.getElementById("main");
    if (main) main.scrollTop = 0;
    renderCatalog();
  });
  document.querySelector(".pack-toc")?.addEventListener("click", (event) => {
    const link = event.target.closest("a[href^='#pack-']");
    if (!link) return;
    event.preventDefault();
    document.getElementById(link.getAttribute("href").slice(1))?.scrollIntoView({ block: "start" });
  });
  window.addEventListener("popstate", () => {
    applySpace(readParam("space") || "overview");
    const tab = readParam("tab");
    document.documentElement.dataset.researchTab = tab === "org" || tab === "event" || tab === "trend" ? tab : "all";
    syncResearchChrome();
    applyLens(readParam("lens") || "product");
    const month = readParam("month");
    if (/^\d{4}-\d{2}$/.test(month)) state.month = month;
    else if (state.currentMonth) state.month = state.currentMonth;
    if (monthSelect && monthSelect.options.length) monthSelect.value = state.month;
    applyMonth();
    renderResearch();
  });

  applySpace(state.space);
  applyLens(readParam("lens") || "product");
  preserveNavLinks();
  syncResearchChrome();
  if (state.space === "research") renderResearch();

  Promise.allSettled([
    loadJson("data/daily-brief.json"),
    loadJson("data/stories-merged.json"),
    loadJson("data/topics.json"),
    loadSiteJson("config/topics.json"),
  ]).then(([briefResult, storiesResult, topicsResult, configResult]) => {
    if (briefResult.status === "fulfilled") {
      state.briefItems = briefResult.value.items || [];
      state.generatedAt = briefResult.value.generated_at || state.generatedAt;
      state.windowHours = briefResult.value.window_hours || state.windowHours;
    }
    state.storiesLoaded = storiesResult.status === "fulfilled";
    if (storiesResult.status === "fulfilled") {
      state.stories = storiesResult.value.stories || [];
      state.generatedAt = state.generatedAt || storiesResult.value.generated_at || "";
      state.windowHours = storiesResult.value.window_hours || state.windowHours;
    }
    if (topicsResult.status === "fulfilled") {
      state.topics = topicsResult.value.topics || [];
      state.generatedAt = state.generatedAt || topicsResult.value.generated_at || "";
    }
    if (configResult.status === "fulfilled") {
      state.topicConfig = configResult.value.topics || [];
      state.topicGroups = configResult.value.groups || [];
    }
    rebuildStoryIndex();
    state.researchReady = true;
    state.currentMonth = monthKey(state.generatedAt) || monthKey(new Date().toISOString());
    const requestedMonth = readParam("month");
    state.month = /^\d{4}-\d{2}$/.test(requestedMonth) ? requestedMonth : state.currentMonth;
    if (!state.generatedAt && briefResult.status !== "fulfilled" && storiesResult.status !== "fulfilled") {
      windowNote.textContent = "数据没有载入。核心指标、本月值与环比先标为内部信息，待接入。";
      state.currentMonth = monthKey(new Date().toISOString());
      state.month = state.currentMonth;
    }
    renderMonthSelect();
    renderOverview();
    renderResearch();
    renderWorkbench();
  });
})();
