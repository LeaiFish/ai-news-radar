(function (global) {
  "use strict";
  let snapshot = null;
  const ids = new Set(["doubao", "qwen", "hunyuan", "openai", "anthropic", "xai", "google-gemini", "meta-llama"]);
  const node = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  };
  const day = value => {
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? date.toLocaleDateString("zh-CN", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit" }) : "日期待核验";
  };
  function refs(parent, card, evidence) {
    const p = node("p", "brief-citations");
    for (const id of card.evidence_ids || []) {
      const e = (evidence || []).find(row => row.id === id);
      if (!e) continue;
      let url;
      try { url = new URL(e.url); } catch { continue; }
      if (url.protocol !== "https:" || url.username || url.password) continue;
      const a = node("a", null, e.source || e.title);
      a.title = e.title || ""; a.href = url.href; a.target = "_blank"; a.rel = "noopener noreferrer";
      if (p.childNodes.length) p.append(document.createTextNode(" · "));
      p.append(a);
    }
    if (p.childNodes.length) parent.append(p);
  }
  function prose(parent, card, evidence) {
    if (!card || typeof card.headline !== "string" || typeof card.summary !== "string") return;
    const section = node("section", "brief-change");
    section.append(node("h3", null, card.headline), node("p", null, card.summary));
    refs(section, card, evidence);
    parent.append(section);
  }
  function period(value, label) {
    // Weekly bounds are half-open; show the last covered Shanghai calendar day.
    const end = label === "周报" ? new Date(Date.parse(value.period_end) - 1).toISOString() : value.period_end;
    return `${label} · ${day(value.period_start)}—${day(end)}`;
  }
  function historyLink(slot, id) {
    if (slot.querySelector('.trend-history-entry')) return;
    const a = node('a', 'trend-history-entry', id ? '查看判断演变 →' : '查看趋势历史与机构对照 →');
    const url = new URL('history.html', document.baseURI);
    if (id) url.searchParams.set('company', id);
    a.href = url.href;
    slot.append(a);
  }
  function appendDigests(slot, id) {
    const row = snapshot?.companies?.[id];
    if (!row) return;
    for (const [key, label] of [["daily", "日报"], ["weekly", "周报"]]) {
      const report = row[key];
      if (!report?.content) continue;
      const container = node("article", "research-brief trend-digest");
      container.append(node("p", "brief-meta", period(report, label)));
      prose(container, report.content, report.evidence);
      slot.append(container);
    }
    historyLink(slot, id);
    if (row.state === "insufficient") slot.append(node("p", "brief-meta trend-gap", `最近核验 ${day(row.last_checked_at)}：${row.reason}`));
  }
  global.radarTrendUI = {
    set(value) {
      snapshot = value?.schema === "radar_trends_v1" && value.companies && Object.keys(value.companies).length === 8 && Object.keys(value.companies).every(id => ids.has(id)) ? value : null;
    },
    overview(slot, month, currentMonth = month) {
      const report = snapshot?.overview;
      if (!report?.content?.themes?.length) return false;
      const date = new Date(report.source_snapshot_at);
      // Use numeric parts rather than browser-specific locale ordering.
      const parts = new Intl.DateTimeFormat("en", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit" }).formatToParts(date);
      const key = `${parts.find(p => p.type === "year").value}-${parts.find(p => p.type === "month").value}`;
      // A collector-only month rollover must not erase the last editorial view.
      // Keep its original date visible in the current view until a new report exists.
      if (key !== month && month !== currentMonth) return false;
      const article = node("article", "research-brief overview-brief");
      article.append(node("p", "brief-meta", `AI趋势研判 · ${report.kind === "weekly" ? period(report, "周报") : `更新于 ${day(report.generated_at)}`}`));
      const header = node("header", "overview-summary");
      header.append(node("p", "overview-lead", report.content.lead)); article.append(header);
      const themes = node("div", "overview-themes");
      report.content.themes.forEach((theme, i) => {
        const section = node("section", "overview-theme");
        section.append(node("span", "overview-index", String(i + 1).padStart(2, "0")));
        const body = node("div", "overview-theme-content");
        body.append(node("h3", null, theme.headline), node("p", null, theme.summary));
        refs(body, theme, report.evidence); section.append(body); themes.append(section);
      });
      article.append(themes); slot.append(article); historyLink(slot); return true;
    },
    section(slot, id, section) {
      const report = snapshot?.companies?.[id]?.[section === "Judgment" ? "judgment" : "changes"];
      if (!report?.content) return false;
      const article = node("article", "research-brief");
      article.append(node("p", "brief-meta", `AI研判 · 依据截至 ${day(report.source_snapshot_at)} 的核验材料 · 判断更新于 ${day(report.generated_at)}`));
      for (const card of Array.isArray(report.content) ? report.content : [report.content]) prose(article, card, report.evidence);
      slot.append(article);
      if (section === "Changes") appendDigests(slot, id);
      return true;
    },
    appendDigests,
  };
})(globalThis);
