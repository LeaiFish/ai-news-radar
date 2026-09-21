(function () {
  "use strict";

  const THEME_KEY = "aiNewsRadarTheme";
  const FAV_KEY = "aiNewsRadarFavorites";
  const THEMES = ["dark", "system", "light"];
  const PAGE_NAVS = new Set(["selected", "all", "hot", "brief", "favorites"]);
  const ICONS = {
    spark: '<path d="M12 3v4M12 17v4M4.9 7.5l3.1 2.2M16 14.3l3.1 2.2M4.9 16.5 8 14.3M16 9.7l3.1-2.2"/><path d="m12 8 1.4 2.8L16.5 12 13.4 13.2 12 16l-1.4-2.8L7.5 12l3.1-1.2Z"/>',
    list: '<path d="M8 7h12M8 12h12M8 17h12"/><path d="M4 7h.01M4 12h.01M4 17h.01"/>',
    flame: '<path d="M12 21c4 0 6-2.6 6-6.2 0-3.4-2.1-5.5-3.4-7.3-.3-.4-.9-.2-.9.3 0 1.2-.4 2.2-1.3 2.7-.7-2.8-2.4-4.8-4.5-6.5-.4-.3-.9.1-.8.6 1.1 4-1.3 6.2-1.3 9.2C5.8 17.8 8.1 21 12 21Z"/>',
    calendar: '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4M16 3v4M4 10h16"/>',
    grid: '<rect x="4" y="4" width="7" height="7" rx="1.2"/><rect x="13" y="4" width="7" height="7" rx="1.2"/><rect x="4" y="13" width="7" height="7" rx="1.2"/><rect x="13" y="13" width="7" height="7" rx="1.2"/>',
    heart: '<path d="M12 19s-7-4.4-7-9.2C5 7 6.8 5.5 9 5.5c1.3 0 2.4.6 3 1.6.6-1 1.7-1.6 3-1.6 2.2 0 4 1.5 4 4.3C19 14.6 12 19 12 19Z"/>',
    puzzle: '<path d="M8 4h4a2 2 0 0 1 4 0h2a2 2 0 0 1 2 2v2a2 2 0 0 1 0 4v2a2 2 0 0 1-2 2h-2a2 2 0 0 0-4 0H8a2 2 0 0 1-2-2v-2a2 2 0 1 1 0-4V6a2 2 0 0 1 2-2Z"/>',
    info: '<circle cx="12" cy="12" r="8"/><path d="M12 11v5M12 8h.01"/>',
    clock: '<circle cx="12" cy="12" r="8"/><path d="M12 8v5l3 2"/>',
    chat: '<path d="M5 16.5A7.5 7.5 0 1 1 8 19l-3.2 1.2c-.6.2-1.2-.4-1-1L5 16.5Z"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    close: '<path d="M6 6l12 12M18 6 6 18"/>',
    moon: '<path d="M18 13.5A7 7 0 1 1 10.5 6 5.5 5.5 0 0 0 18 13.5Z"/>',
    desktop: '<rect x="3.5" y="5" width="17" height="12" rx="1.5"/><path d="M8 21h8M12 17v4"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M5 12H3M21 12h-2M6.2 6.2 4.8 4.8M19.2 19.2l-1.4-1.4M17.8 6.2l1.4-1.4M4.8 19.2l1.4-1.4"/>',
    star: '<path d="m12 4.5 2.1 4.4 4.8.7-3.4 3.4.8 4.8L12 15.8 7.7 17.8l.8-4.8-3.4-3.4 4.8-.7Z"/>',
  };

  const scriptEl = document.currentScript;
  const rootHint = scriptEl?.dataset.root || document.documentElement.dataset.root || "./";
  const ROOT = new URL(rootHint.endsWith("/") ? rootHint : `${rootHint}/`, window.location.href);

  function svg(name) {
    return `<svg class="radar-nav-icon" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`;
  }

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

  function siteHref(path, search, hash) {
    const url = new URL(path || "./", ROOT);
    if (search) url.search = search.startsWith("?") ? search : `?${search}`;
    if (hash) url.hash = hash.startsWith("#") ? hash : `#${hash}`;
    return url.href;
  }

  function currentSearch() {
    const params = new URLSearchParams(window.location.search);
    params.delete("view");
    return params;
  }

  function githubRepo() {
    const explicit = document.documentElement.dataset.githubRepo;
    if (explicit) return explicit;
    const host = window.location.hostname;
    const pages = host.match(/^([a-z0-9-]+)\.github\.io$/i);
    if (pages) {
      const segs = window.location.pathname.split("/").filter(Boolean);
      const repo = segs[0] && !segs[0].includes(".") ? segs[0] : "ai-news-radar";
      return `${pages[1]}/${repo}`;
    }
    if (/learnprompt/i.test(host)) return "LearnPrompt/ai-news-radar";
    return "LearnPrompt/ai-news-radar";
  }

  function githubUrl(suffix) {
    return `https://github.com/${githubRepo()}${suffix || ""}`;
  }

  function currentSurface() {
    const html = document.documentElement;
    if (html.dataset.radarSurface === "topics") return "topics";
    if (html.dataset.radarView === "classic") return "classic";
    if (html.dataset.radarView === "mobile") return "home";
    if (/\/topics(\/|$)/.test(window.location.pathname)) return "topics";
    if (/\/classic(\/|$)/.test(window.location.pathname)) return "classic";
    return "home";
  }

  function isRadarHome() {
    const surface = currentSurface();
    return surface === "home" || surface === "classic";
  }

  function readNavParam() {
    try {
      const nav = new URLSearchParams(window.location.search).get("nav") || "";
      if (PAGE_NAVS.has(nav)) return nav;
    } catch {
      // Ignore malformed search strings.
    }
    const hash = (window.location.hash || "").replace(/^#/, "");
    if (hash === "hotBoardWrap" || hash === "hot") return "hot";
    return "";
  }

  function radarHomePath() {
    if (currentSurface() === "classic") return "classic/";
    try {
      if (window.localStorage.getItem("aiNewsRadarViewV2") === "classic") return "classic/";
    } catch {
      // Storage can be unavailable in private or hardened browser contexts.
    }
    return "./";
  }

  function homeHref(nav) {
    const params = currentSearch();
    if (!nav || nav === "selected") params.delete("nav");
    else params.set("nav", nav);
    const hash = nav === "hot" ? "hotBoardWrap" : "";
    return siteHref(radarHomePath(), params.toString(), hash);
  }

  function readFavorites() {
    try {
      const parsed = JSON.parse(window.localStorage.getItem(FAV_KEY) || "[]");
      return Array.isArray(parsed) ? parsed.filter((item) => item && item.url) : [];
    } catch {
      return [];
    }
  }

  function writeFavorites(items) {
    try {
      window.localStorage.setItem(FAV_KEY, JSON.stringify(items.slice(0, 80)));
    } catch {
      // Storage can be unavailable in private or hardened browser contexts.
    }
  }

  function favoriteId(record) {
    return String(record?.id || record?.url || "").trim();
  }

  function isSaved(record) {
    const id = favoriteId(record);
    if (!id) return false;
    return readFavorites().some((item) => favoriteId(item) === id);
  }

  function toggleFavorite(record) {
    const id = favoriteId(record);
    if (!id || !record?.url) return;
    const items = readFavorites();
    const exists = items.some((item) => favoriteId(item) === id);
    const next = exists
      ? items.filter((item) => favoriteId(item) !== id)
      : [{
          id,
          title: record.title || record.url,
          url: record.url,
          source: record.source || "",
          savedAt: Date.now(),
        }, ...items];
    writeFavorites(next);
    renderFavorites();
    decorateFavoriteButtons();
    return !exists;
  }

  let sidebarEl;
  let favPanelEl;
  let favListEl;
  let toggleBtn;
  let activeNav = "";

  function setDrawerOpen(open) {
    document.body.classList.toggle("radar-nav-open", Boolean(open));
    if (toggleBtn) {
      toggleBtn.setAttribute("aria-expanded", open ? "true" : "false");
      toggleBtn.setAttribute("aria-label", open ? "关闭导航" : "打开导航");
      toggleBtn.innerHTML = svg(open ? "close" : "menu");
    }
  }

  function closeDrawer() {
    setDrawerOpen(false);
  }

  function currentActiveNav() {
    if (!favPanelEl?.hidden) return "favorites";
    if (currentSurface() === "topics") return "topics";
    return readNavParam() || activeNav || "selected";
  }

  function markActive(nav) {
    activeNav = nav || currentActiveNav();
    document.body.dataset.radarNav = activeNav;
    document.querySelectorAll("[data-radar-nav]").forEach((el) => {
      const isActive = el.dataset.radarNav === activeNav;
      el.classList.toggle("is-active", isActive);
      if (el.tagName === "A") {
        if (isActive) el.setAttribute("aria-current", el.dataset.radarNav === "topics" ? "page" : "true");
        else el.removeAttribute("aria-current");
      }
    });
  }

  function setFavoritesOpen(open) {
    if (!favPanelEl) return;
    favPanelEl.hidden = !open;
    if (open) {
      renderFavorites();
      closeDrawer();
      if (isRadarHome()) {
        const params = currentSearch();
        params.set("nav", "favorites");
        const next = `${window.location.pathname}?${params.toString()}`;
        const current = `${window.location.pathname}${window.location.search}`;
        if (current !== next) window.history.replaceState(null, "", next);
        document.dispatchEvent(new CustomEvent("aiRadar:navigate", { detail: { nav: "favorites" } }));
      }
      markActive("favorites");
    } else {
      if (isRadarHome() && (readNavParam() === "favorites" || activeNav === "favorites")) {
        document.dispatchEvent(new CustomEvent("aiRadar:navigate", { detail: { nav: "selected" } }));
      }
      markActive(currentSurface() === "topics" ? "topics" : (readNavParam() || "selected"));
    }
  }

  function renderFavorites() {
    if (!favListEl) return;
    const items = readFavorites();
    favListEl.innerHTML = "";
    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "radar-fav-empty";
      empty.textContent = "还没有收藏。点卡片或热点行右侧的星标，即可保存在这台浏览器。";
      favListEl.appendChild(empty);
      return;
    }
    items.forEach((item) => {
      const row = document.createElement("article");
      row.className = "radar-fav-item";
      const link = document.createElement("a");
      link.href = item.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = item.title || item.url;
      if (item.source) {
        const source = document.createElement("small");
        source.textContent = item.source;
        link.appendChild(source);
      }
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "radar-fav-remove";
      remove.textContent = "取消";
      remove.addEventListener("click", () => toggleFavorite(item));
      row.append(link, remove);
      favListEl.appendChild(row);
    });
  }

  function recordFromCard(card) {
    const titleEl = card.matches?.("a[href]")
      ? card
      : (card.querySelector("a.title, a.hot-row-title, a.hot-card-title, a.brief-item-title") || card.querySelector("a[href]"));
    if (!titleEl || !titleEl.href || titleEl.getAttribute("href") === "#") return null;
    const nestedTitle = card.querySelector(".hot-strip-title, .hot-card-title, .brief-item-title, a.title");
    const title = (titleEl.getAttribute("title") || nestedTitle?.textContent || titleEl.textContent || "").replace(/\s+/g, " ").trim();
    const source = (card.querySelector(".site, .hot-card-meta, .brief-item-meta")?.textContent || "").replace(/\s+/g, " ").trim();
    return { id: titleEl.href, url: titleEl.href, title, source };
  }

  function decorateFavoriteButtons(root) {
    const scope = root || document;
    scope.querySelectorAll(".news-card, .hot-row, .hot-card, .hot-strip-item, .brief-item").forEach((card) => {
      const record = recordFromCard(card);
      if (!record) return;
      let btn = card.querySelector(":scope > .radar-fav-btn, .meta-row > .radar-fav-btn, .hot-card-body > .radar-fav-btn, .brief-item-body > .radar-fav-btn, .radar-fav-btn");
      if (!btn) {
        btn = document.createElement("button");
        btn.type = "button";
        btn.className = "radar-fav-btn";
        btn.innerHTML = svg("star");
        const meta = card.querySelector(".meta-row, .hot-card-body, .brief-item-body") || card;
        meta.appendChild(btn);
      }
      btn.dataset.favId = record.id;
      btn.dataset.favUrl = record.url;
      btn.dataset.favTitle = record.title || "";
      btn.dataset.favSource = record.source || "";
      const saved = isSaved(record);
      btn.classList.toggle("is-saved", saved);
      btn.setAttribute("aria-pressed", saved ? "true" : "false");
      btn.setAttribute("aria-label", saved ? "取消收藏" : "收藏");
      btn.title = saved ? "取消收藏" : "收藏到本机";
    });
  }

  async function requestNav(nav) {
    closeDrawer();
    if (nav === "favorites") {
      setFavoritesOpen(true);
      return;
    }
    setFavoritesOpen(false);
    if (nav === "topics") return;
    if (!isRadarHome()) {
      window.location.assign(homeHref(nav));
      return;
    }
    if (window.AINewsRadarNav && typeof window.AINewsRadarNav.apply === "function") {
      await window.AINewsRadarNav.apply(nav, { scroll: true });
      markActive(nav);
      return;
    }
    document.dispatchEvent(new CustomEvent("aiRadar:navigate", { detail: { nav } }));
    markActive(nav);
  }

  function handleNavClick(event) {
    const target = event.currentTarget;
    const nav = target.dataset.radarNav || "";
    if (target.target === "_blank") return;
    if (nav === "topics") {
      closeDrawer();
      setFavoritesOpen(false);
      return;
    }
    event.preventDefault();
    requestNav(nav);
  }

  function mount() {
    if (document.querySelector(".radar-sidebar")) return;
    document.body.classList.add("has-radar-sidebar");

    const repo = githubRepo();
    const topicsHref = siteHref("topics/");
    const homeSelected = homeHref("selected");

    const aside = document.createElement("aside");
    aside.className = "radar-sidebar";
    aside.id = "radarSidebar";
    aside.setAttribute("aria-label", "站点导航");
    aside.innerHTML = `
      <a class="radar-sidebar-brand" href="${homeSelected}">
        <img src="${siteHref("assets/logo.svg")}" alt="" />
        <span class="radar-sidebar-brand-text">
          <strong>雷达</strong>
          <span>AI News Radar</span>
        </span>
      </a>
      <nav class="radar-sidebar-nav">
        <div class="radar-nav-group" aria-label="内容">
          <div class="radar-nav-label">内容</div>
          <a class="radar-nav-link" data-radar-nav="selected" href="${homeHref("selected")}">${svg("spark")}精选</a>
          <a class="radar-nav-link" data-radar-nav="all" href="${homeHref("all")}">${svg("list")}全部 AI 动态</a>
          <a class="radar-nav-link" data-radar-nav="hot" href="${homeHref("hot")}">${svg("flame")}热点榜</a>
          <a class="radar-nav-link" data-radar-nav="brief" href="${homeHref("brief")}">${svg("calendar")}AI 日报</a>
          <a class="radar-nav-link" data-radar-nav="topics" href="${topicsHref}">${svg("grid")}主题</a>
          <button class="radar-nav-link" type="button" data-radar-nav="favorites">${svg("heart")}收藏</button>
        </div>
        <div class="radar-nav-divider" role="presentation"></div>
        <div class="radar-nav-group" aria-label="更多">
          <div class="radar-nav-label">更多</div>
          <a class="radar-nav-link" href="${githubUrl("/blob/master/skills/radar/README.md")}" target="_blank" rel="noopener noreferrer">${svg("puzzle")}Agent 接入</a>
          <a class="radar-nav-link" href="${githubUrl("/blob/master/README.md")}" target="_blank" rel="noopener noreferrer">${svg("info")}关于</a>
          <a class="radar-nav-link" href="${githubUrl("/releases")}" target="_blank" rel="noopener noreferrer">${svg("clock")}更新日志</a>
          <a class="radar-nav-link" href="${githubUrl("/issues")}" target="_blank" rel="noopener noreferrer">${svg("chat")}反馈</a>
        </div>
      </nav>
      <div class="radar-sidebar-footer">
        <div class="radar-theme" role="group" aria-label="颜色主题">
          <button class="radar-theme-btn" type="button" data-radar-theme="dark" title="深色" aria-label="深色">${svg("moon")}</button>
          <button class="radar-theme-btn" type="button" data-radar-theme="system" title="跟随系统" aria-label="跟随系统">${svg("desktop")}</button>
          <button class="radar-theme-btn" type="button" data-radar-theme="light" title="浅色" aria-label="浅色">${svg("sun")}</button>
        </div>
      </div>
    `;
    document.body.prepend(aside);
    sidebarEl = aside;
    aside.dataset.githubRepo = repo;

    const backdrop = document.createElement("div");
    backdrop.className = "radar-nav-backdrop";
    backdrop.addEventListener("click", closeDrawer);
    document.body.appendChild(backdrop);

    toggleBtn = document.createElement("button");
    toggleBtn.type = "button";
    toggleBtn.className = "radar-nav-toggle";
    toggleBtn.setAttribute("aria-controls", "radarSidebar");
    toggleBtn.setAttribute("aria-expanded", "false");
    toggleBtn.setAttribute("aria-label", "打开导航");
    toggleBtn.innerHTML = svg("menu");
    toggleBtn.addEventListener("click", () => {
      setDrawerOpen(!document.body.classList.contains("radar-nav-open"));
    });
    const headline = document.querySelector(".hero-headline");
    if (headline) headline.insertBefore(toggleBtn, headline.firstChild);
    else document.body.insertBefore(toggleBtn, aside.nextSibling);

    favPanelEl = document.createElement("section");
    favPanelEl.className = "radar-fav-panel";
    favPanelEl.hidden = true;
    favPanelEl.setAttribute("aria-label", "收藏");
    favPanelEl.innerHTML = `
      <div class="radar-fav-inner">
        <p class="pane-kicker">收藏</p>
        <h2>本机收藏</h2>
        <p class="radar-fav-note">保存在这台浏览器的 localStorage，不会上传或跨设备同步。点卡片或热点右侧的星标即可加入。</p>
        <div class="radar-fav-list"></div>
      </div>
    `;
    favListEl = favPanelEl.querySelector(".radar-fav-list");
    document.body.appendChild(favPanelEl);

    aside.querySelectorAll("[data-radar-nav]").forEach((el) => {
      el.addEventListener("click", handleNavClick);
    });
    aside.querySelectorAll("[data-radar-theme]").forEach((button) => {
      button.addEventListener("click", () => applyTheme(button.dataset.radarTheme));
    });
    applyTheme(readTheme());

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        if (!favPanelEl.hidden) setFavoritesOpen(false);
        closeDrawer();
      }
    });

    const requested = readNavParam();
    if (requested === "favorites") setFavoritesOpen(true);
    else markActive(currentActiveNav());
    decorateFavoriteButtons();
  }

  document.addEventListener("aiRadar:navchange", (event) => {
    const nav = event.detail?.nav;
    if (nav === "favorites") setFavoritesOpen(true);
    else {
      if (favPanelEl && !favPanelEl.hidden && nav && nav !== "favorites") favPanelEl.hidden = true;
      markActive(nav || currentActiveNav());
    }
  });
  document.addEventListener("aiRadar:listRendered", () => decorateFavoriteButtons());
  document.addEventListener("aiRadar:ready", () => decorateFavoriteButtons());
  document.addEventListener("aiRadar:topicsRendered", () => decorateFavoriteButtons());

  try {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
      if (readTheme() === "system") applyTheme("system");
    });
  } catch {
    // matchMedia can be missing in very old environments.
  }

  document.addEventListener("click", (event) => {
    const btn = event.target.closest(".radar-fav-btn");
    if (!btn) return;
    event.preventDefault();
    event.stopPropagation();
    const card = btn.closest(".news-card, .hot-row, .hot-card, .hot-strip-item, .brief-item");
    const record = {
      id: btn.dataset.favId || btn.dataset.favUrl,
      url: btn.dataset.favUrl,
      title: btn.dataset.favTitle,
      source: btn.dataset.favSource,
    };
    if (!record.url && card) {
      const parsed = recordFromCard(card);
      if (parsed) Object.assign(record, parsed);
    }
    toggleFavorite(record);
  });

  window.AINewsRadarSidebar = {
    applyTheme,
    toggleFavorite,
    readFavorites,
    requestNav,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount, { once: true });
  } else {
    mount();
  }
})();
