(function (global) {
  'use strict';
  const ids=['doubao','qwen','hunyuan','openai','anthropic','xai','google-gemini','meta-llama'];
  const names={doubao:'豆包',qwen:'千问',hunyuan:'元宝',openai:'ChatGPT',anthropic:'Claude',xai:'Grok','google-gemini':'Gemini','meta-llama':'Meta / Muse'};
  let index=null;
  const cache=new Map(),validId=id=>typeof id==='string'&&/^[a-f0-9]{64}$/.test(id);
  const node=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!=null)n.textContent=String(text);return n;};
  function day(value){if(!value)return '日期未知';if(/^\d{4}-\d{2}-\d{2}$/.test(value))return value;const d=new Date(value);return Number.isFinite(d.getTime())?d.toLocaleDateString('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}):'日期未知';}
  function label(type){return index?.types?.[type]||'未标注';}
  function badge(type){return node('span','trend-evolution-badge trend-evolution-'+(Object.hasOwn(index.types,type)?type:'unclassified'),label(type));}
  function publicLink(value){try{const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password?u.href:null;}catch{return null;}}
  function evidence(parent,rows){
    const list=node('ul','trend-history-sources');
    for(const e of rows||[]){const href=publicLink(e.url);if(!href)continue;const li=node('li'),a=node('a',null,e.source||e.title||'来源');a.href=href;a.target='_blank';a.rel='noopener noreferrer';a.title=e.title||'';li.append(a,node('span',null,` · 发表 ${day(e.published_at)} · 事件 ${day(e.event_at)}`));list.append(li);}
    if(list.childNodes.length)parent.append(list);
  }
  function refs(parent,signal,rows){evidence(parent,(rows||[]).filter(e=>(signal.evidence_ids||[]).includes(e.id)));}
  async function snapshot(id){
    if(!validId(id))throw new Error('invalid_history_id');
    if(!cache.has(id))cache.set(id,fetch(new URL(`data/trends/history/${id}.json`,document.baseURI)).then(async r=>{if(!r.ok)throw new Error('history_unavailable');const x=await r.json();if(x.schema!=='radar_trend_history_snapshot_v1'||x.report_id!==id)throw new Error('history_mismatch');return x;}).catch(e=>{cache.delete(id);throw e;}));
    return cache.get(id);
  }
  function correctionNotes(parent,row){for(const correction of row.label_corrections||[])parent.append(node('p','brief-meta trend-label-correction',`复核更正 ${day(correction.at)} · ${label(correction.from_type)} → ${label(correction.to_type)}。${correction.reason} 原始报告保留。`));}
  function judgment(parent,title,value){
    const box=node('section','trend-history-judgment');box.append(node('h4',null,title));
    if(value?.content){box.append(node('strong',null,value.content.headline),node('p',null,value.content.summary));box.append(node('p','brief-meta',value.generated_at?`判断原更新日 ${day(value.generated_at)}`:`基线截至 ${day(value.as_of)} · AI分析草稿`));
      if(value.evidence?.length)evidence(box,value.evidence);else if(value.sources?.length)evidence(box,value.sources.map(url=>({url,source:'基线来源',published_at:null,event_at:null})));}
    else box.append(node('p',null,'暂无此前结构化判断。'));
    parent.append(box);
  }
  function disclosure(parent,title,cls='trend-history-details') {
    const details=node('details',cls);details.append(node('summary',null,title));parent.append(details);return details;
  }
  function legend(parent){
    const details=disclosure(parent,'判断标记与归档说明','trend-history-guide');
    details.append(node('p','trend-history-note','延续：方向不变；加强：核心执行、部署范围或持续使用出现实质进展；转向：主要路径或重心改变；纠偏：纠正原判断。补齐信息和普通功能更新归延续。'));
    details.append(node('p','trend-history-note','判断变化与新闻新增分开记录。只列已有存档；缺期、缺线索不等于没有动作。机构线索按各自最新记录展示，不表示同步发布、效果相同或采用程度排名。'));
  }
  function signalCard(parent,signal,rows){const p=node('p','trend-history-signal',`${index.directions[signal.direction_id]} · ${index.stages[signal.stage]||'阶段未核验'}：${signal.summary}`);parent.append(p);refs(parent,signal,rows);}
  function section(parent,title,id){const box=node('section','history-section');box.id=id;box.append(node('h2',null,title));parent.append(box);return box;}
  async function companyBody(body,id){
    body.replaceChildren();const list=node('div','trend-history-list');body.append(list);const metas=[...index.reports].reverse();let shown=0,found=0;
    const more=node('button','trend-history-button','显示更早记录');more.type='button';
    async function batch(){more.disabled=true;const selected=metas.slice(shown,shown+12);const loaded=await Promise.all(selected.map(m=>snapshot(m.report_id)));
      for(let i=0;i<selected.length;i++){const meta=selected[i],row=loaded[i].companies?.[id];if(!row)continue;
        const article=node('details','trend-history-record');article.open=found++===0;
        const heading=node('summary','history-record-heading');heading.append(node('span',null,`${day(meta.generated_at)} · ${meta.kind==='weekly'?'周报':'日报'}`),badge(row.type));article.append(heading);
        const content=node('div','history-record-content');
        if(row.provenance==='retrospective')content.append(node('p','brief-meta',`回顾标记于 ${day(row.classified_at)}；原始报告未改写。`));
        if(row.provenance==='unclassified')content.append(node('p','brief-meta','当时未标注变化类型，保留未标注。'));correctionNotes(content,row);
        if(!row.label_corrections?.some(c=>c.reason===row.reason))content.append(node('p','trend-history-reason',row.reason));
        const pair=node('div','trend-history-pair');judgment(pair,'此前判断',row.before);judgment(pair,'当期判断',row.after);content.append(pair);
        for(const signal of row.signals||[])signalCard(content,signal,row.evidence);article.append(content);list.append(article);}
      shown+=selected.length;more.disabled=false;more.hidden=shown>=metas.length;
      if(!found)list.textContent='暂无已归档判断。';}
    more.addEventListener('click',()=>batch().catch(()=>{more.disabled=false;more.textContent='读取失败，点击重试';}));body.append(more);legend(body);await batch();
  }
  async function comparison(parent,direction){
    const box=node('div','trend-comparison'),missing=[],unavailable=[];
    const map=index.latest_signals?.[direction]||{},latest=index.reports.at(-1);
    const loaded=await Promise.all(ids.map(async id=>map[id]?snapshot(map[id]).catch(()=>null):null));
    ids.forEach((id,i)=>{
      const snap=loaded[i],row=snap?.companies?.[id],signal=row?.signals?.find(s=>s.direction_id===direction);
      if(!signal){(map[id]?unavailable:missing).push(names[id]);return;}
      const article=node('article','trend-comparison-card'),a=node('a',null,names[id]);const u=new URL('./',document.baseURI);u.search='';u.searchParams.set('space','research');u.searchParams.set('kind','org');u.searchParams.set('id',id);a.href=u.href;article.append(a);
      const meta=node('p','brief-meta',`判断记录 ${day(snap.generated_at)} · ${index.stages[signal.stage]||'阶段未核验'}`);article.append(meta,badge(signal.type),node('p','history-company-summary',signal.summary));
      const details=disclosure(article,'来源与记录');refs(details,signal,row.evidence);
      if(row.provenance==='retrospective')details.append(node('p','brief-meta',`回顾标记 ${day(row.classified_at)}`));correctionNotes(details,row);
      if(latest?.companies?.[id]?.type==='insufficient')article.append(node('p','brief-meta','最近一期证据不足，以上为此前留存线索。'));
      box.append(article);
    });
    if(!box.childNodes.length)box.append(node('p','brief-meta','该方向暂无可展示的机构进展。'));
    if(missing.length)box.append(node('p','history-comparison-empty',`暂无该方向归档线索：${missing.join('、')}`));
    if(unavailable.length)box.append(node('p','history-comparison-empty',`线索暂时无法读取：${unavailable.join('、')}`));
    parent.replaceChildren(box);
  }
  function overviewRecord(parent,meta,record){
    const article=disclosure(parent,`${day(meta.generated_at)} · ${meta.kind==='weekly'?'周报':'日报'}`,'trend-overview-history');
    const content=node('div','history-record-content');article.append(content);
    content.append(node('p','history-period-lead',record.after.lead));
    if(record.provenance==='retrospective')content.append(node('p','brief-meta',`回顾标记 ${day(record.classified_at)}；原始报告未改写。`));
    for(const theme of record.after.themes){
      const box=node('section','trend-history-theme');box.append(badge(theme.type),node('h3',null,theme.content.headline));
      const old=record.before?.themes?.find(x=>theme.direction_id&&x.direction_id===theme.direction_id),pair=node('div','trend-history-pair');
      if(old){const before=node('div','trend-history-judgment');before.append(node('h4',null,'此前判断'),node('strong',null,old.content.headline),node('p',null,old.content.summary));pair.append(before);}
      const after=node('div','trend-history-judgment');after.append(node('h4',null,'当期判断'),node('strong',null,theme.content.headline),node('p',null,theme.content.summary));pair.append(after);box.append(pair);
      box.append(node('p','trend-history-reason',`调整原因：${theme.reason}`));
      const sources=disclosure(box,'查看来源');refs(sources,theme.content,record.after.evidence);content.append(box);
    }
    if(record.before?.baseline_text){const baseline=disclosure(content,`此前首页基线 · 截至 ${day(record.before.as_of)}`);baseline.append(node('p','brief-meta','AI分析草稿'),node('p','trend-history-baseline',record.before.baseline_text));}
  }
  async function homeBody(body){
    body.replaceChildren();
    const metas=[...index.reports].reverse().filter(m=>m.overview?.length);
    const overview=section(body,'趋势总览','historyOverview');
    const summary=node('div','history-latest-summary');overview.append(summary);
    const compareSection=section(body,'各趋势下的机构进展','historyCompanies');
    const controls=node('label','trend-direction-label','趋势方向'),select=node('select','trend-direction-select');
    for(const [id,name]of Object.entries(index.directions)){const option=node('option',null,name);option.value=id;select.append(option);}controls.append(select);compareSection.append(controls);
    const compare=node('div','trend-comparison-slot');compareSection.append(compare);let revision=0;
    async function update(){const version=++revision,tmp=node('div');compare.setAttribute('aria-busy','true');compare.textContent='正在读取同方向线索…';
      try{await comparison(tmp,select.value);if(version===revision)compare.replaceChildren(...tmp.childNodes);}catch{if(version===revision)compare.textContent='机构对照暂时无法读取。';}finally{if(version===revision)compare.setAttribute('aria-busy','false');}}
    select.addEventListener('change',update);
    const history=section(body,'历期判断变化','historyArchive'),list=node('div','history-archive-list');history.append(list);
    const more=node('button','trend-history-button','显示更早首页判断');more.type='button';history.append(more);let shown=0;
    async function batch(){more.disabled=true;const rows=metas.slice(shown,shown+8);const loaded=await Promise.allSettled(rows.map(m=>snapshot(m.report_id)));
      rows.forEach((meta,i)=>{const result=loaded[i];if(result.status==='fulfilled'&&result.value.overview)overviewRecord(list,meta,result.value.overview);
        else list.append(node('p','brief-meta',`${day(meta.generated_at)} · 该期历史暂时无法读取。`));});shown+=rows.length;more.hidden=shown>=metas.length;more.disabled=false;}
    more.addEventListener('click',()=>batch().catch(()=>{more.disabled=false;more.textContent='读取失败，点击重试';}));
    legend(body);
    if(metas.length){
      try{const latest=await snapshot(metas[0].report_id),record=latest.overview;
        summary.append(node('p','brief-meta',`总判断更新于 ${day(metas[0].generated_at)} · ${metas[0].kind==='weekly'?'周报':'日报'}`),node('p','history-overview-lead',record.after.lead));
        const themes=node('div','history-theme-grid');summary.append(themes);
        record.after.themes.forEach((theme,i)=>{const card=node('article','history-theme-card'),top=node('div','history-theme-meta');top.append(node('span','history-theme-number',String(i+1).padStart(2,'0')),badge(theme.type));card.append(top,node('h3',null,theme.content.headline));
          if(index.directions[theme.direction_id]){const button=node('button','history-theme-link','查看机构进展');button.type='button';button.addEventListener('click',()=>{select.value=theme.direction_id;update();compareSection.scrollIntoView({block:'start'});select.focus({preventScroll:true});});card.append(button);}themes.append(card);});
      }catch{summary.append(node('p','brief-meta','最新总判断暂时无法读取，下方可查看机构进展与历期记录。'));}
    }else{summary.append(node('p','brief-meta','暂无已归档总判断。'));list.append(node('p','brief-meta','暂无历期判断记录。'));}
    await Promise.all([update(),batch()]);
  }
  global.radarTrendHistory={
    set(value,expected){cache.clear();index=value?.schema==='radar_trend_history_v1'&&validId(value.latest_report_id)&&(!expected||value.latest_report_id===expected)&&value.directions&&typeof value.directions==='object'&&value.types&&typeof value.types==='object'&&value.stages&&typeof value.stages==='object'&&Array.isArray(value.reports)&&value.reports.every(r=>r&&validId(r.report_id))?value:null;},
    async page(slot,id){if(!index)throw new Error('history_unavailable');return ids.includes(id)?companyBody(slot,id):homeBody(slot);},
  };
  if(document.getElementById?.('historyContent')) {
    const themeKey='aiNewsRadarTheme';
    function theme(value){const choice=['dark','light','system'].includes(value)?value:'system';document.documentElement.dataset.theme=choice;document.documentElement.style.colorScheme=choice==='system'?(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'):choice;document.querySelectorAll('[data-radar-theme]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.radarTheme===choice)));try{localStorage.setItem(themeKey,choice);}catch{}}
    let preferred='system';try{preferred=localStorage.getItem(themeKey)||'system';}catch{}theme(preferred);
    document.querySelectorAll('[data-radar-theme]').forEach(b=>b.addEventListener('click',()=>theme(b.dataset.radarTheme)));
    const nav=document.getElementById('navToggle'),sidebar=document.getElementById('sidebar'),scrim=document.getElementById('scrim');
    function navOpen(open){sidebar.classList.toggle('is-open',open);nav.setAttribute('aria-expanded',String(open));scrim.hidden=!open;}
    nav.addEventListener('click',()=>navOpen(nav.getAttribute('aria-expanded')!=='true'));scrim.addEventListener('click',()=>navOpen(false));
    const slot=document.getElementById('historyContent'),select=document.getElementById('historyView'),title=document.getElementById('historyTitle');
    for(const id of ids){const option=node('option',null,names[id]);option.value=id;select.append(option);}
    const requested=new URL(location.href).searchParams.get('company');if(ids.includes(requested))select.value=requested;
    async function render(){const id=select.value,body=node('div','trend-history-body history-page-content');slot.replaceChildren(body);title.hidden=!ids.includes(id);title.textContent=ids.includes(id)?`${names[id]} · 判断演变`:'趋势总览';
      const url=new URL(location.href);if(ids.includes(id))url.searchParams.set('company',id);else url.searchParams.delete('company');window.history.replaceState(null,'',url);
      try{await global.radarTrendHistory.page(body,id);}catch{body.textContent='历史暂时无法读取，请稍后重试。';}}
    select.addEventListener('change',render);
    Promise.all(['data/trends/history.json','data/trends/latest.json'].map(async path=>{const r=await fetch(new URL(path,document.baseURI),{signal:AbortSignal.timeout(10000)});if(!r.ok)throw new Error('history_unavailable');return r.json();})).then(async([value,latest])=>{global.radarTrendHistory.set(value,latest.report_id);await render();}).catch(()=>{slot.textContent='历史暂时无法读取，请稍后重试。当前判断可返回竞争概览查看。';});
  }
})(globalThis);
