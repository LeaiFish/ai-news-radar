import assert from "node:assert/strict";
const { chromium } = await import(process.env.RADAR_PLAYWRIGHT_MODULE || "@playwright/test");
const base = process.env.RADAR_TEST_BASE_URL || "http://127.0.0.1:8093/";
const browser = await chromium.launch({ headless: true, channel: "chrome" });
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(base);
  await page.locator("#judgmentGrid .overview-theme").first().waitFor();
  assert.ok(await page.locator("#judgmentGrid").innerText().then(s => s.includes("共同使用")));
  assert.equal(await page.locator("#judgmentGrid .overview-theme").count(), 3);
  await page.screenshot({ path: "/tmp/radar-trends-home.png", fullPage: true });
  const judgments = {};
  for (const id of ["doubao", "qwen", "hunyuan", "openai", "anthropic", "xai", "google-gemini", "meta-llama"]) {
    console.log(`Checking ${id}`);
    await page.goto(`${base}?space=research&kind=org&id=${id}`);
    await page.locator("#packDelta .trend-digest").waitFor();
    judgments[id] = await page.locator("#packJudgment").innerText();
    assert.ok(judgments[id].length > 80, id);
    assert.equal(await page.locator("#packDelta .trend-digest").count(), 1, id);
    assert.ok((await page.locator("#packDelta .trend-digest").innerText()).includes("日报"));
    assert.equal(await page.locator("#packDelta .trend-digest a[href^='https://']").count() > 0, true, id);
    if (id === "meta-llama") assert.match(await page.locator("#packTitle").innerText(), /Muse/);
  }
  assert.match(judgments.doubao, /在线分享/);
  assert.match(judgments.openai, /共同改稿/);
  assert.match(judgments.anthropic, /研究预览/);
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
