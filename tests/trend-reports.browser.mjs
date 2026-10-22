import assert from "node:assert/strict";
const { chromium } = await import(process.env.RADAR_PLAYWRIGHT_MODULE || "@playwright/test");
const base = process.env.RADAR_TEST_BASE_URL || "http://127.0.0.1:8093/";
const browser = await chromium.launch({ headless: true, channel: "chrome" });
try {
  const live = await fetch(new URL("data/trends/latest.json", base)).then(r => r.json());
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(base);
  await page.locator("#judgmentGrid .overview-theme").first().waitFor();
  assert.ok(await page.locator("#judgmentGrid").innerText().then(s => s.includes(live.overview.content.lead)));
  assert.equal(await page.locator("#judgmentGrid .overview-theme").count(), live.overview.content.themes.length);
  await page.screenshot({ path: "/tmp/radar-trends-home.png", fullPage: true });
  const judgments = {};
  for (const id of ["doubao", "qwen", "hunyuan", "openai", "anthropic", "xai", "google-gemini", "meta-llama"]) {
    console.log(`Checking ${id}`);
    await page.goto(`${base}?space=research&kind=org&id=${id}`);
    await page.locator("#packJudgment .research-brief").waitFor();
    judgments[id] = await page.locator("#packJudgment").innerText();
    assert.ok(judgments[id].length > 80, id);
    const expected = ["daily", "weekly"].filter(k => live.companies[id][k]?.content).length;
    assert.equal(await page.locator("#packDelta .trend-digest").count(), expected, id);
    if (expected) assert.ok(await page.locator("#packDelta .trend-digest a[href^='https://']").count() > 0, id);
    if (live.companies[id].judgment) assert.ok(judgments[id].includes(live.companies[id].judgment.content.headline), id);
    if (id === "meta-llama") assert.match(await page.locator("#packTitle").innerText(), /Muse/);
  }
  assert.equal(await page.evaluate(async () => {
    const latest = await fetch(new URL("data/trends/latest.json", location.href)).then(r => r.json());
    globalThis.radarTrendUI.set(latest);
    const slot = document.createElement("div");
    const current = globalThis.radarTrendUI.overview(slot, "2026-11", "2026-11");
    const historical = globalThis.radarTrendUI.overview(document.createElement("div"), "2026-09", "2026-11");
    return current && !historical && slot.textContent.includes(latest.overview.content.lead);
  }), true, "month rollover must retain the original editorial date");
  // Same renderer, a real-shaped weekly issue, and adversarial prose remain text.
  await page.evaluate(() => {
    const slot = document.getElementById("packDelta");
    slot.replaceChildren();
    const card = { headline: "<img src=x onerror=alert(1)>", summary: "周报研判", evidence_ids: ["e"] };
    const companies = Object.fromEntries(["doubao", "qwen", "hunyuan", "openai", "anthropic", "xai", "google-gemini", "meta-llama"].map(id => [id, {}]));
    companies.doubao.weekly = { period_start: "2026-10-18T16:00:00Z", period_end: "2026-10-25T16:00:00Z", content: card, evidence: [{ id: "e", title: "原文", url: "https://example.com/article" }] };
    globalThis.radarTrendUI.set({ schema: "radar_trends_v1", companies });
    globalThis.radarTrendUI.appendDigests(slot, "doubao");
  });
  assert.equal(await page.locator("#packDelta img").count(), 0);
  assert.match(await page.locator("#packDelta").innerText(), /周报.*2026\/10\/19.*2026\/10\/25/);
  assert.match(await page.locator("#packDelta").innerText(), /<img/);
  await page.setViewportSize({width:390,height:844});
  await page.goto(base);
  await page.locator("#judgmentGrid .overview-theme").first().waitFor();
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "mobile page overflow");
  await page.screenshot({path:"/tmp/radar-trends-mobile.png",fullPage:true});
  assert.deepEqual(errors, []);
  console.log("Homepage, eight company pages, weekly dates, citations and text-only rendering passed.");
} finally {
  await browser.close();
}
