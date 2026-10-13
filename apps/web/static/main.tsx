import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { createHashRouter, RouterProvider, Outlet, Link, useLoaderData, useSearchParams, useParams, useLocation } from 'react-router';
import type { ItemSummary, FeedItemSummary } from '@aihot/contracts/site';
import { Sidebar } from '../app/components/shell/Sidebar';
import { TabBar } from '../app/components/shell/TabBar';
import { DayList, Pagination } from '../app/features/feed/DayList';
import { ThemeSwitch } from '../app/components/shell/ThemeSwitch';
import { SourceDirectory } from '../app/features/sources/SourceDirectory';
import { SITE } from '@aihot/site';
import { useStarred, useAppearanceSync } from '../app/lib/local-state';
import { useHydratedFlag } from '../app/lib/hydration';
import '../app/app.css';
type Topic = { id: string; name: string; description: string; group: string; region?: string; itemIds: string[] };
type Snapshot = { generatedAt: string; items: (ItemSummary & FeedItemSummary)[]; topics: Topic[]; stories: {publicId:string;title:string;itemIds:string[];selected:boolean}[]; dailyIds:string[]; groups: {id:string;name:string}[] };
let snapshot: Promise<Snapshot>;
function load() { return snapshot ||= fetch(`${import.meta.env.BASE_URL}public-news.json`).then(r => { if (!r.ok) throw new Error('公开新闻加载失败'); return r.json(); }).then(data=>({...data,items:data.items.map((i:ItemSummary)=>({...i,originalUrl:i.links.original}))})); }
function Shell() {
 useHydratedFlag();
 const {pathname,search}=useLocation();
 useAppearanceSync();
 useEffect(()=>{window.scrollTo(0,0);},[pathname,search]);
 return <div className="flex min-h-dvh"><Sidebar changelogVersion={null}/><main className="min-w-0 flex-1 px-4 pb-24 pt-6 lg:px-8 lg:pb-10 lg:pt-8"><div className="mx-auto max-w-[1120px]"><div className="mb-6 flex items-center justify-between lg:hidden"><Link to="/" className="text-xl font-bold">{SITE.name}</Link><Link to="/topics" className="text-accent">主题</Link></div><Outlet/></div></main><TabBar changelogVersion={null}/></div>;
}
function Feed() {
 const starred=useStarred();
 const data=useLoaderData() as Snapshot; const [params,setParams]=useSearchParams();const location=useLocation();const {slug}=useParams();
 const topic=slug?data.topics.find(t=>t.id===slug):null;
 const q=params.get('q')||'';const tagged=params.get('tag'); const page=Math.max(1,Number(params.get('page'))||1);
 const ids=topic?new Set(topic.itemIds):null;
 const saved=new Set(starred.map(i=>i.id));
 const rows=data.items.filter(i=>(location.pathname!=='/'||i.selected)&&(location.pathname!=='/starred'||saved.has(i.id))&&(location.pathname!=='/daily'||data.dailyIds?.includes(i.id))&&(!ids||ids.has(i.id))&&(!q||`${i.title} ${i.originalTitle||''} ${i.summary||''} ${i.source.name}`.toLowerCase().includes(q.toLowerCase()))&&(!tagged||i.tags.includes(tagged)));
 const pages=Math.max(1,Math.ceil(rows.length/20));const current=Math.min(page,pages);
 const title=topic?.name || (location.pathname==='/daily'?'AI 日报':location.pathname==='/starred'?'收藏':location.pathname==='/'?'精选动态':'全部 AI 动态');
 return <><h1 className="mb-3 text-[28px] font-bold tracking-tight lg:text-[32px]">{title}</h1>{topic&&<p className="mb-6 text-ink-3">{topic.description}</p>}<form className="mb-6 flex gap-3" onSubmit={e=>e.preventDefault()}><input className="h-11 w-full rounded-control border border-line bg-surface px-4 text-ink" placeholder="搜索消息、公司或来源" value={q} onChange={e=>setParams({q:e.target.value})}/></form><DayList items={rows.slice((current-1)*20,current*20)}/>{rows.length===0&&<p className="py-10 text-ink-4">暂无相关消息</p>}<Pagination page={current} pageCount={pages} href={p=>`${location.pathname}?${new URLSearchParams({...Object.fromEntries(params),page:String(p)})}`}/></>;
}
const domestic=new Set(['doubao','qwen','hunyuan','quark','kimi','deepseek','minimax','zhipu','baidu','mimo','stepfun']);
function Topics() {
 const data=useLoaderData() as Snapshot;const [query,setQuery]=useState('');
 function cards(rows:Topic[]) {return <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{rows.filter(t=>`${t.name} ${t.description}`.toLowerCase().includes(query.toLowerCase())).map(t=><Link key={t.id} to={`/topics/${t.id}`} className="card card-hover flex flex-col p-5"><h3 className="text-[18px] font-semibold text-ink">{t.name}</h3><p className="mb-5 mt-2 flex-1 text-[14px] leading-6 text-ink-3">{t.description}</p><span className="text-[13px] font-medium text-accent">{t.itemIds.length?`近30天 ${t.itemIds.length} 条`:'近30天无消息'}</span></Link>)}</div>;}
 return <><h1 className="mb-6 text-[32px] font-bold">主题研究</h1><input className="mb-8 h-11 w-full rounded-control border border-line bg-surface px-4" placeholder="搜索名称或说明" value={query} onChange={e=>setQuery(e.target.value)}/>{data.groups.map(g=><section key={g.id} className="mb-10"><h2 className="mb-5 border-b border-line pb-3 text-[23px] font-bold">{g.name}</h2>{g.id==='company'?['国内','海外'].map(region=><div key={region} className="mb-7"><h3 className="mb-4 text-[16px] font-semibold text-ink-3">{region}</h3>{cards(data.topics.filter(t=>t.group===g.id && (t.region?t.region===region:domestic.has(t.id)===(region==='国内'))))}</div>):cards(data.topics.filter(t=>t.group===g.id))}</section>)}</>;
}
function Item() {
 const data=useLoaderData() as Snapshot;const {id}=useParams();const item=data.items.find(i=>i.id===id);
 if(!item)return <p>消息不存在或已超出公开窗口。</p>;
 return <article className="mx-auto max-w-[780px]"><Link to="/all" className="text-accent">← 全部动态</Link><p className="mb-3 mt-7 text-[13px] text-ink-4">{item.source.name} · {new Date(item.timelineAt).toLocaleString('zh-CN')}</p><h1 className="text-[28px] font-bold leading-relaxed"><a href={item.links.original} target="_blank" rel="noopener noreferrer">{item.title}</a></h1>{item.originalTitle&&<details className="mt-4 text-ink-4"><summary>英文原标题</summary><p className="mt-2">{item.originalTitle}</p></details>}{item.summary&&<p className="mt-7 whitespace-pre-line text-[17px] leading-loose text-ink-2">{item.summary}</p>}</article>;
}
function Hot(){
 const data=useLoaderData() as Snapshot;
 const rows=(data.stories||[]).map(s=>({...s,items:data.items.filter(i=>s.itemIds.includes(i.id))})).filter(s=>s.items.length>1).sort((a,b)=>new Set(b.items.map(i=>i.source.name)).size-new Set(a.items.map(i=>i.source.name)).size);
 return <><h1 className="mb-6 text-[28px] font-bold">热点榜</h1><p className="mb-6 text-ink-4">按公开报道的独立来源数量排列</p><div className="space-y-4">{rows.slice(0,30).map((s,index)=><article key={s.publicId} className="card p-5"><div className="flex items-start gap-4"><span className="num text-2xl font-bold text-accent">{index+1}</span><div><h2 className="text-[18px] font-semibold"><a href={s.items[0]!.links.original}>{s.title}</a></h2><details className="mt-3 text-sm text-ink-3"><summary>{new Set(s.items.map(i=>i.source.name)).size} 个公开来源</summary><ul className="mt-3 space-y-2">{s.items.map(i=><li key={i.id}><a className="text-accent" href={i.links.original}>{i.source.name} · {i.title}</a></li>)}</ul></details></div></div></article>)}</div></>;
}
function More(){return <><h1 className="mb-6 text-[28px] font-bold">我的</h1><div className="card divide-y divide-line">{[['/all','全部动态'],['/topics','主题研究'],['/starred','收藏'],['/sources','关注信源'],['/about','关于']].map(([to,label])=><Link key={to} to={to!} className="block p-4 font-medium">{label}</Link>)}<div className="p-4"><p className="mb-3 text-sm text-ink-4">外观</p><ThemeSwitch/></div></div></>;}
function Info(){return <div><h1 className="mb-5 text-2xl font-bold">AI Perspective</h1><p className="leading-8 text-ink-3">本页展示免费流程整理的公开新闻。原文版权归各来源所有。后台、数据库和内部业务数据仅保留在本机。此静态站不提供后台登录或模型调用。</p></div>;}
const legacy=new URLSearchParams(window.location.search);
if(!window.location.hash&&legacy.get('q'))window.location.hash='/all?q='+encodeURIComponent(legacy.get('q')!);
if(!window.location.hash&&legacy.get('space')==='research')window.location.hash=legacy.get('id')?`/topics/${legacy.get('id')}`:'/topics';
const router=createHashRouter([{path:'/',Component:Shell,children:[{index:true,loader:load,Component:Feed,handle:{tab:'featured',name:'精选'}},{path:'all',loader:load,Component:Feed},{path:'sources',Component:SourceDirectory,handle:{home:'me',name:'关注信源'}},{path:'topics',loader:load,Component:Topics,handle:{home:'me',name:'主题'}},{path:'topics/:slug',loader:load,Component:Feed},{path:'items/:id',loader:load,Component:Item},{path:'starred',loader:load,Component:Feed},{path:'hot',loader:load,Component:Hot,handle:{tab:'hot',name:'热点'}},{path:'daily',loader:load,Component:Feed,handle:{tab:'daily',name:'日报'}},{path:'more',Component:More,handle:{tab:'me',name:'我的'}},{path:'*',Component:Info}]}]);
createRoot(document.getElementById('root')!).render(<RouterProvider router={router}/>);
