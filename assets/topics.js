(function () {
  "use strict";

  const pageRoot = document.documentElement.dataset.root || "../";
  const pageRootUrl = new URL(pageRoot, window.location.href);

  function resolveDataBaseUrl() {
    let fromQuery = "";
    try {
      fromQuery = new URLSearchParams(window.location.search).get("data") || "";
    } catch {
      fromQuery = "";
    }
    if (fromQuery) {
      const normalized = fromQuery.trim().replace(/\/+$/, "");
      try { localStorage.setItem("dataBaseUrl", normalized); } catch {}
      return normalized;
    }
    try {
      return (localStorage.getItem("dataBaseUrl") || "").trim().replace(/\/+$/, "");
    } catch {
      return "";
    }
  }

  const dataBaseUrl = resolveDataBaseUrl();

  function dataUrl(path) {
    const relative = String(path || "").replace(/^\/?data\//, "");
    if (dataBaseUrl) return `${dataBaseUrl}/${relative}`;
    return new URL(`data/${relative}`, pageRootUrl).href;
  }

  function homeUrl(subpath) {
    return new URL(subpath || "./", pageRootUrl).href;
  }

  function topicIdFromLocation() {
    const params = new URLSearchParams(window.location.search);
    const fromQuery = (params.get("id") || params.get("topic") || "").trim();
    if (fromQuery) return fromQuery;
    const fromDataset = (document.documentElement.dataset.topicId || "").trim();
    if (fromDataset) return fromDataset;
    const parts = window.location.pathname.replace(/\/+$/, "").split("/");
    const idx = parts.lastIndexOf("topics");
    if (idx >= 0) {
      const next = parts[idx + 1] || "";
      if (next && next !== "index.html") return next;
    }
    return "";
  }

  const fmtNumber = (n) => new Intl.NumberFormat("zh-CN").format(n || 0);

  function fmtTime(iso) {
    if (!iso) return "时间未知";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "时间未知";
    return new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  }

  function fmtHHMM(ms) {
    if (!ms) return "--:--";
    const date = new Date(ms);
    if (Number.isNaN(date.getTime())) return "--:--";
    return new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
  }

  function dateGroupKey(ms) {
    if (!ms) return "unknown";
    const date = new Date(ms);
    return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
  }

  function dateGroupLabel(ms) {
    if (!ms) return "时间未知";
    const date = new Date(ms);
    const now = new Date();
    const sameYear = date.getFullYear() === now.getFullYear();
    return new Intl.DateTimeFormat("zh-CN", sameYear
      ? { month: "long", day: "numeric" }
      : { year: "numeric", month: "long", day: "numeric" }).format(date);
  }

  function dateGroupWeekday(ms) {
    if (!ms) return "";
    return new Intl.DateTimeFormat("zh-CN", { weekday: "long" }).format(new Date(ms));
  }

  function safeTopicHref(topicId) {
    const params = new URLSearchParams(window.location.search);
    params.delete("id");
    params.delete("topic");
    const query = params.toString();
    const currentId = topicIdFromLocation();
    const base = currentId
      ? new URL(`../${topicId}/`, window.location.href)
      : new URL(`./${topicId}/`, window.location.href);
    if (query) base.search = query;
    return base.href;
  }

  const mainEl = document.getElementById("topicsMain");
  const statusEl = document.getElementById("topicsStatus");
  const titleEl = document.getElementById("topicsTitle");
  const leadEl = document.getElementById("topicsLead");
  const updatedAtEl = document.getElementById("updatedAt");
  const filterEl = document.getElementById("topicsFilter");
  const itemTpl = document.getElementById("itemTpl");

  function setStatus(text) {
    if (!statusEl) return;
    statusEl.hidden = !text;
    statusEl.textContent = text || "";
  }

  function renderEmpty(title, message) {
    const empty = document.createElement("div");
    empty.className = "empty";
    const heading = document.createElement("h3");
    heading.textContent = title;
    const body = document.createElement("p");
    body.textContent = message;
    empty.append(heading, body);
    return empty;
  }

  function topicsForGroup(topics, groupId) {
    // Preserve config/topics.json array order. Do not sort by name or item count.
    return (Array.isArray(topics) ? topics : []).filter((topic) => topic.group === groupId);
  }

  function hubFilterFromLocation() {
    try {
      return (new URLSearchParams(window.location.search).get("group") || "").trim();
    } catch {
      return "";
    }
  }

  function setHubFilter(id) {
    const url = new URL(window.location.href);
    if (!id || id === "all") url.searchParams.delete("group");
    else url.searchParams.set("group", id);
    history.replaceState({}, "", url);
  }

  function hubFilterOptions(index) {
    const groups = Array.isArray(index.groups) ? index.groups : [];
    const topics = Array.isArray(index.topics) ? index.topics : [];
    const options = [{ id: "all", label: "全部", kind: "all" }];
    groups.forEach((group) => {
      options.push({
        id: group.id,
        label: group.name || group.id,
        kind: "group",
        groupId: group.id,
      });
      if (group.filter === "topics") {
        topicsForGroup(topics, group.id).forEach((topic) => {
          options.push({
            id: topic.id,
            label: topic.name,
            kind: "topic",
            groupId: group.id,
          });
        });
      }
    });
    return options;
  }

  function resolveHubFilter(index) {
    const raw = hubFilterFromLocation();
    const options = hubFilterOptions(index);
    return options.find((option) => option.id === raw) || options[0];
  }

  function applyHubFilter(index, selected) {
    const groups = Array.isArray(index.groups) ? index.groups : [];
    const topics = Array.isArray(index.topics) ? index.topics : [];
    if (!selected || selected.kind === "all") {
      return { groups, topics };
    }
    if (selected.kind === "group") {
      return {
        groups: groups.filter((group) => group.id === selected.id),
        topics: topics.filter((topic) => topic.group === selected.id),
      };
    }
    const topic = topics.find((item) => item.id === selected.id);
    if (!topic) return { groups, topics };
    return {
      groups: groups.filter((group) => group.id === topic.group),
      topics: [topic],
    };
  }

  function hideHubFilter() {
    if (!filterEl) return;
    filterEl.hidden = true;
    filterEl.replaceChildren();
  }

  function renderHubFilter(index) {
    if (!filterEl) return;
    const selected = resolveHubFilter(index);
    filterEl.hidden = false;
    filterEl.replaceChildren();
    const label = document.createElement("p");
    label.className = "topics-filter-label";
    label.id = "topicsFilterLabel";
    label.textContent = "按哪一个主题";
    const chips = document.createElement("div");
    chips.className = "topics-filter-chips";
    chips.setAttribute("role", "group");
    chips.setAttribute("aria-labelledby", "topicsFilterLabel");
    hubFilterOptions(index).forEach((option) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "topics-filter-chip";
      btn.textContent = option.label;
      const pressed = option.id === selected.id;
      btn.setAttribute("aria-pressed", pressed ? "true" : "false");
      if (pressed) btn.classList.add("active");
      btn.addEventListener("click", () => {
        setHubFilter(option.id);
        renderHub(index);
      });
      chips.appendChild(btn);
    });
    filterEl.append(label, chips);
  }

  function renderHub(index) {
    document.title = "主题 · AI News Radar";
    if (titleEl) titleEl.textContent = "按主题看 AI";
    if (leadEl) {
      leadEl.textContent = "按产业透镜、公司与模型、技术方向浏览主题。匹配来自标题/摘要/来源的关键词，不是分类模型。";
    }
    renderHubFilter(index);
    const selected = resolveHubFilter(index);
    const filtered = applyHubFilter(index, selected);
    const groups = filtered.groups;
    const topics = filtered.topics;
    const frag = document.createDocumentFragment();

    groups.forEach((group) => {
      const section = document.createElement("section");
      section.className = "topics-group";
      const head = document.createElement("div");
      head.className = "topics-group-head";
      const heading = document.createElement("h2");
      heading.textContent = group.name || group.id;
      const desc = document.createElement("p");
      desc.textContent = group.description || "";
      head.append(heading, desc);
      const grid = document.createElement("div");
      grid.className = "topics-grid";
      topicsForGroup(topics, group.id).forEach((topic) => {
        const card = document.createElement("a");
        card.className = "topic-card";
        card.href = safeTopicHref(topic.id);
        const name = document.createElement("h3");
        name.textContent = topic.name;
        const blurb = document.createElement("p");
        blurb.className = "topic-card-blurb";
        blurb.textContent = topic.description || "";
        const meta = document.createElement("div");
        meta.className = "topic-card-meta";
        const count = document.createElement("strong");
        count.textContent = `${fmtNumber(topic.item_count || 0)} 条`;
        const latest = document.createElement("span");
        latest.textContent = topic.latest_title
          ? `最新：${topic.latest_title}`
          : "暂无匹配条目";
        meta.append(count, latest);
        card.append(name, blurb, meta);
        grid.appendChild(card);
      });
      section.append(head, grid);
      frag.appendChild(section);
    });

    const note = document.createElement("p");
    note.className = "topics-footnote";
    note.textContent = (index.matching && index.matching.limitations) || "";
    frag.appendChild(note);
    mainEl.innerHTML = "";
    mainEl.appendChild(frag);
  }

  function renderItemCard(item) {
    const node = itemTpl.content.firstElementChild.cloneNode(true);
    const curatedEl = node.querySelector(".curated-badge");
    if (curatedEl) curatedEl.hidden = !item.curated;
    const siteEl = node.querySelector(".site");
    if (siteEl) siteEl.textContent = item.source_name || item.source || "";
    const sourceEl = node.querySelector(".source");
    if (sourceEl) {
      sourceEl.textContent = item.source_count > 1 ? `多源 ${fmtNumber(item.source_count)}` : (item.source || "");
    }
    const titleEl = node.querySelector(".title");
    titleEl.textContent = "";
    if (item.title_en && item.title_en !== item.title) {
      const primary = document.createElement("span");
      primary.textContent = item.title;
      const sub = document.createElement("span");
      sub.className = "title-sub";
      sub.textContent = item.title_en;
      titleEl.append(primary, sub);
    } else {
      titleEl.textContent = item.title || "未命名条目";
    }
    titleEl.href = item.url || "#";
    const summaryEl = node.querySelector(".news-summary");
    if (summaryEl) {
      summaryEl.textContent = item.summary || "";
      summaryEl.hidden = !item.summary;
    }
    const whyBox = node.querySelector(".why-box");
    if (whyBox) {
      if (item.recommend_reason_zh) {
        whyBox.hidden = false;
        node.querySelector(".why-text").textContent = item.recommend_reason_zh;
      } else {
        whyBox.hidden = true;
      }
    }
    const original = document.createElement("a");
    original.className = "original-link original-action";
    original.href = item.url || "#";
    original.target = "_blank";
    original.rel = "noopener noreferrer";
    original.textContent = "查看原文 ↗";
    node.querySelector(".meta-row").appendChild(original);
    return node;
  }

  function renderDetail(detail, index) {
    document.title = `${detail.name} · 主题 · AI News Radar`;
    if (titleEl) titleEl.textContent = detail.name;
    if (leadEl) leadEl.textContent = detail.description || "";
    const wrap = document.createElement("section");
    wrap.className = "list-wrap topics-detail-wrap";
    const head = document.createElement("div");
    head.className = "list-head";
    const heading = document.createElement("h2");
    heading.textContent = "匹配条目";
    const meta = document.createElement("span");
    meta.id = "resultCount";
    const listed = detail.listed_count || (detail.items || []).length;
    const total = detail.item_count || listed;
    meta.textContent = listed < total
      ? `${fmtNumber(listed)} / ${fmtNumber(total)} 条 · 按时间倒序`
      : `${fmtNumber(total)} 条 · 按时间倒序`;
    head.append(heading, meta);
    const list = document.createElement("div");
    list.className = "news-list";
    list.id = "newsList";
    const items = Array.isArray(detail.items) ? detail.items : [];
    if (!items.length) {
      list.appendChild(renderEmpty("这个主题暂时没有匹配条目", "关键词启发式匹配依赖标题和摘要；下一次雷达更新后可能会出现新内容。"));
    } else {
      const dateGroupCounts = new Map();
      items.forEach((item) => {
        const key = dateGroupKey(Date.parse(item.published_at) || 0);
        dateGroupCounts.set(key, (dateGroupCounts.get(key) || 0) + 1);
      });
      let lastKey = null;
      items.forEach((item) => {
        const timeMs = Date.parse(item.published_at) || 0;
        const key = dateGroupKey(timeMs);
        if (key !== lastKey) {
          const header = document.createElement("div");
          header.className = "date-group-header";
          const dateLabel = document.createElement("span");
          dateLabel.textContent = dateGroupLabel(timeMs);
          const weekday = dateGroupWeekday(timeMs);
          const count = dateGroupCounts.get(key) || 0;
          const groupMeta = document.createElement("span");
          groupMeta.className = "date-group-meta";
          groupMeta.textContent = weekday ? `· ${weekday} · ${fmtNumber(count)} 条` : `· ${fmtNumber(count)} 条`;
          header.append(dateLabel, groupMeta);
          list.appendChild(header);
          lastKey = key;
        }
        const timelineItem = document.createElement("div");
        timelineItem.className = "timeline-item";
        const rail = document.createElement("div");
        rail.className = "timeline-rail";
        const timeLabel = document.createElement("span");
        timeLabel.className = "timeline-time";
        timeLabel.textContent = fmtHHMM(timeMs);
        const dot = document.createElement("span");
        dot.className = "timeline-dot";
        rail.append(timeLabel, dot);
        timelineItem.append(rail, renderItemCard(item));
        list.appendChild(timelineItem);
      });
    }
    wrap.append(head, list);

    const back = document.createElement("p");
    back.className = "topics-footnote";
    const hubLink = document.createElement("a");
    hubLink.href = topicIdFromLocation() ? "../" : "./";
    hubLink.textContent = "← 全部主题";
    back.append(hubLink);
    if (index && index.matching && index.matching.limitations) {
      back.append(document.createTextNode(" · " + index.matching.limitations));
    }

    hideHubFilter();
    mainEl.innerHTML = "";
    mainEl.append(wrap, back);
  }

  async function loadJson(path) {
    const response = await fetch(dataUrl(path), { cache: "no-cache" });
    if (!response.ok) throw new Error(`${path} ${response.status}`);
    return response.json();
  }

  async function init() {
    const topicId = topicIdFromLocation();
    try {
      const index = await loadJson("data/topics.json");
      if (updatedAtEl) updatedAtEl.textContent = fmtTime(index.generated_at);
      if (!topicId) {
        setStatus("");
        renderHub(index);
        return;
      }
      const summary = (index.topics || []).find((topic) => topic.id === topicId);
      if (!summary) {
        setStatus("");
        hideHubFilter();
        mainEl.innerHTML = "";
        mainEl.appendChild(renderEmpty("没有这个主题", "请回到主题列表，或检查 config/topics.json 里的 id。"));
        return;
      }
      const detail = await loadJson(summary.items_url || `data/topics/${topicId}.json`);
      setStatus("");
      renderDetail(detail, index);
    } catch (error) {
      setStatus("");
      hideHubFilter();
      mainEl.innerHTML = "";
      mainEl.appendChild(renderEmpty("主题数据加载失败", "确认 data/topics.json 已生成，或用 python scripts/build_topics.py --data-dir data 重建。"));
      console.error(error);
    }
  }

  window.AINewsRadarTopics = {
    topicIdFromLocation,
    dataUrl,
    homeUrl,
    topicsForGroup,
    hubFilterOptions,
    applyHubFilter,
    hubFilterFromLocation,
  };
  init();
})();
