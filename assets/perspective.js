(function () {
  "use strict";

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
    topics: [],
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

  function renderExampleRow() {
    const row = el("tr", "is-example");
    const product = el("td");
    product.append(el("span", "product-name", "示例产品"), el("span", "tag tag-example", "示例"));
    row.append(
      product,
      el("td", "metric-pending", "待接入"),
      el("td", "metric-pending", "—"),
      el("td", "metric-pending", "—"),
      el("td", null, "示例行，不是实测数据"),
    );
    return row;
  }

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
      el("td", null, "近窗相关故事"),
      el("td", null, `${row.count} 条`),
      el("td", "metric-pending", "待接入"),
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
    } else {
      rows.forEach((row) => body.append(renderMetricRow(row)));
    }
    body.append(renderExampleRow());
  }

  function renderJudgments() {
    clear(judgmentGrid);
    const items = pickJudgments();
    if (!items.length) {
      judgmentGrid.append(el("p", "placeholder-line", "当日简报暂时没有可用条目。"));
      return;
    }
    items.forEach((item) => {
      const card = el("article", "judgment-card");
      const top = el("div", "judgment-top");
      top.append(el("h3", null, preferZh(item.title)));
      top.append(el("span", "tag tag-draft", "AI 草稿"));
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
      const link = el("a", null, topic.name || topic.id);
      link.href = new URL(`topics/${encodeURIComponent(topic.id)}/`, ROOT).href;
      relatedList.append(link);
    });
  }

  function renderWindowNote() {
    const stamp = formatStamp(state.generatedAt);
    const when = stamp ? `更新于 ${stamp}` : "更新时间待接入";
    windowNote.textContent = `${when} · 数据窗 ${state.windowHours} 小时 · 本月值是故事条数，环比待接入`;
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
    params.delete("space");
    params.delete("month");
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
    if (event.target.closest("a, button")) setMenu(false);
  });

  applySpace(state.space);
  applyLens(readParam("lens") || "product");
  preserveNavLinks();

  Promise.allSettled([
    loadJson("data/daily-brief.json"),
    loadJson("data/stories-merged.json"),
    loadJson("data/topics.json"),
  ]).then(([briefResult, storiesResult, topicsResult]) => {
    if (briefResult.status === "fulfilled") {
      state.briefItems = briefResult.value.items || [];
      state.generatedAt = briefResult.value.generated_at || state.generatedAt;
      state.windowHours = briefResult.value.window_hours || state.windowHours;
    }
    if (storiesResult.status === "fulfilled") {
      state.stories = storiesResult.value.stories || [];
      state.generatedAt = state.generatedAt || storiesResult.value.generated_at || "";
      state.windowHours = storiesResult.value.window_hours || state.windowHours;
    }
    if (topicsResult.status === "fulfilled") {
      state.topics = topicsResult.value.topics || [];
      state.generatedAt = state.generatedAt || topicsResult.value.generated_at || "";
    }
    state.currentMonth = monthKey(state.generatedAt) || monthKey(new Date().toISOString());
    const requestedMonth = readParam("month");
    state.month = /^\d{4}-\d{2}$/.test(requestedMonth) ? requestedMonth : state.currentMonth;
    if (!state.generatedAt && briefResult.status !== "fulfilled" && storiesResult.status !== "fulfilled") {
      windowNote.textContent = "数据没有载入。下面先保留示例行。";
      state.currentMonth = monthKey(new Date().toISOString());
      state.month = state.currentMonth;
    }
    renderMonthSelect();
    renderOverview();
  });
})();
