import assert from 'node:assert/strict';
const {chromium}=await import(process.env.RADAR_PLAYWRIGHT_MODULE || '@playwright/test');
const base=process.env.RADAR_TEST_BASE_URL || 'http://127.0.0.1:8097/';
const browser=await chromium.launch({headless:true,...(process.env.RADAR_BROWSER_CHANNEL?{channel:process.env.RADAR_BROWSER_CHANNEL}:{})});
try {
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 // The normal homepage must never fetch or wait for history.
 let historyRequests=0;
 await page.route('**/data/trends/history.json*',route=>{historyRequests++;return route.fulfill({status:404,body:'missing'});});
 await page.goto(base);await page.locator('#judgmentGrid .overview-theme').first().waitFor();
 assert.equal(historyRequests,0);assert.equal(await page.locator('.trend-history-panel').count(),0);
 const entry=page.locator('#judgmentGrid .trend-history-entry');assert.match(await entry.getAttribute('href'),/history\.html/);
 await page.unroute('**/data/trends/history.json*');await entry.click();
 await page.locator('.trend-direction-select').waitFor();
 await page.locator('.trend-direction-select').selectOption('merchant-operations');
 await page.locator('.trend-comparison-card').first().waitFor();
 const comparison=await page.locator('.trend-comparison').innerText();
 for(const text of ['ChatGPT','Gemini','千问','Muse','测试或邀测','使用案例','判断记录'])assert.ok(comparison.includes(text),text);
 await page.locator('.trend-overview-history').first().waitFor();
 assert.match(await page.locator('#historyContent').innerText(),/此前首页基线/);
 await page.screenshot({path:'/tmp/radar-history-home.png',fullPage:true});
 for(const id of ['doubao','qwen','hunyuan','openai','anthropic','xai','google-gemini','meta-llama']) {
  await page.goto(`${base}?space=research&kind=org&id=${id}`);
  const link=page.locator('#packDelta .trend-history-entry');await link.waitFor();
  assert.equal(await page.locator('.trend-history-record').count(),0);
  await link.click();await page.locator('.trend-history-record').first().waitFor();
  assert.equal(await page.locator('#historyView').inputValue(),id);
  const text=await page.locator('#historyContent').innerText();
  for(const term of ['回顾标记','此前判断','当期判断'])assert.ok(text.includes(term),`${id} ${term}`);
  if(id==='openai'){assert.match(text,/广告/);assert.match(text,/加强/);await page.screenshot({path:'/tmp/radar-history-company.png',fullPage:true});}
 }
 await page.setViewportSize({width:390,height:844});await page.goto(new URL('history.html',base).href);
 await page.locator('.trend-comparison-card').first().waitFor();
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile overflow');
 await page.screenshot({path:'/tmp/radar-history-mobile.png',fullPage:true});
 // Untrusted history prose remains text on the actual independent interface.
 const index=await fetch(new URL('data/trends/history.json',base)).then(r=>r.json());
 await page.route(`**/data/trends/history/${index.latest_report_id}.json`,async route=>{
  const response=await route.fetch();const x=await response.json();x.companies.openai.reason='<img src=x onerror=alert(1)>';
  await route.fulfill({json:x});
 });
 await page.goto(new URL('history.html?company=openai',base).href);await page.locator('.trend-history-record').first().waitFor();
 assert.equal(await page.locator('#historyContent img').count(),0);assert.match(await page.locator('#historyContent').innerText(),/<img/);
 await page.locator('[data-radar-theme="dark"]').click();
 const colors=await page.locator('.trend-history-judgment').first().evaluate(el=>({bg:getComputedStyle(el).backgroundColor,fg:getComputedStyle(el).color}));
 const lum=value=>value.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);
 const a=lum(colors.bg),b=lum(colors.fg);assert.ok((Math.max(a,b)+.05)/(Math.min(a,b)+.05)>=4.5,'dark history text contrast');
 await page.locator('[data-radar-theme="system"]').click();

 // Correctly match query parameters too; a history failure stays on its own page.
 await page.route('**/data/trends/history.json*',route=>route.fulfill({status:404,body:'missing'}));
 await page.goto(new URL('history.html',base).href);await page.getByText('历史暂时无法读取，请稍后重试。当前判断可返回竞争概览查看。',{exact:true}).waitFor();
 await page.goto(base);await page.locator('#judgmentGrid .overview-theme').first().waitFor();
 assert.deepEqual(errors,[]);console.log('Dedicated history page, before/after for eight companies, cross-company directions, baseline, missing data, XSS and mobile passed.');
}finally{await browser.close();}
