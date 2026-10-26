import assert from 'node:assert/strict';
const {chromium}=await import(process.env.RADAR_PLAYWRIGHT_MODULE || '@playwright/test');
const base=process.env.RADAR_TEST_BASE_URL || 'http://127.0.0.1:8097/';
const browser=await chromium.launch({headless:true,...(process.env.RADAR_BROWSER_CHANNEL?{channel:process.env.RADAR_BROWSER_CHANNEL}:{})});
try {
 const page=await browser.newPage({viewport:{width:1440,height:1000}}), errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.locator('.trend-history-home').waitFor({timeout:8000});
 await page.locator('.trend-history-home > summary').click();
 await page.locator('.trend-direction-select').selectOption('merchant-operations');
 await page.locator('.trend-comparison-card').first().waitFor();
 const comparison=await page.locator('.trend-comparison').innerText();
 assert.match(comparison,/ChatGPT/);assert.match(comparison,/Gemini/);assert.match(comparison,/千问/);assert.match(comparison,/Muse/);
 assert.match(comparison,/邀测|测试/);assert.match(comparison,/使用案例/);assert.match(comparison,/判断记录/);
 await page.locator('.trend-overview-history').first().waitFor();
 await page.screenshot({path:'/tmp/radar-history-home.png',fullPage:true});
 for(const id of ['doubao','qwen','hunyuan','openai','anthropic','xai','google-gemini','meta-llama']) {
  await page.goto(`${base}?space=research&kind=org&id=${id}`);
  await page.locator('.trend-history-company').waitFor();
  await page.locator('.trend-history-company > summary').click();
  await page.locator('.trend-history-record').first().waitFor();
  const text=await page.locator('.trend-history-company').innerText();
  assert.match(text,/回顾标记/);assert.match(text,/此前判断/);assert.match(text,/当期判断/);
  if(id==='openai') {assert.match(text,/广告/);assert.match(text,/加强/);await page.screenshot({path:'/tmp/radar-history-company.png',fullPage:true});}
 }
 await page.setViewportSize({width:390,height:844});await page.goto(base);
 await page.locator('.trend-history-home').waitFor();await page.locator('.trend-history-home > summary').click();
 await page.locator('.trend-comparison-card').first().waitFor();
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile overflow');
 await page.screenshot({path:'/tmp/radar-history-mobile.png',fullPage:true});
 // Adversarial text is text, including history reasons and signals.
 await page.evaluate(async()=>{
  const data=await fetch('data/trends/history.json').then(r=>r.json());
  const id=data.reports.at(-1).report_id;
  const snap=await fetch(`data/trends/history/${id}.json`).then(r=>r.json());
  snap.companies.openai.reason='<img src=x onerror=alert(1)>';
  const original=globalThis.fetch;
  globalThis.fetch=async (...args)=>String(args[0]).includes(`/history/${id}.json`)?new Response(JSON.stringify(snap)):original(...args);
  globalThis.radarTrendHistory.set(data);const slot=document.createElement('div');slot.id='history-xss';document.body.append(slot);
  globalThis.radarTrendHistory.company(slot,'openai');slot.querySelector('details').open=true;
 });
 await page.locator('#history-xss .trend-history-record').first().waitFor();
 assert.equal(await page.locator('#history-xss img').count(),0);
 assert.match(await page.locator('#history-xss').innerText(),/<img/);
 // No history must leave current judgments intact.
 await page.route('**/data/trends/history.json',route=>route.fulfill({status:404,body:'missing'}));
 await page.goto(base);await page.locator('#judgmentGrid .overview-theme').first().waitFor();
 assert.equal(await page.locator('.trend-history-home').count(),0);
 assert.deepEqual(errors,[]);console.log('History before/after, eight companies, cross-company directions, missing data, XSS and mobile passed.');
}finally{await browser.close();}
