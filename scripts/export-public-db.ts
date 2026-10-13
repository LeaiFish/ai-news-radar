// A narrow reader projection, not a database dump. Only marked public-news imports qualify.
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { sql, closeDb } from '../packages/backend/src/db.ts';
import { ITEM_COLUMNS, ITEM_FROM, toItemSummary, type ItemRow } from '../packages/backend/src/publication/items.ts';
import { listedCondition } from '../packages/backend/src/publication/scope.ts';
import { TOPICS, TOPIC_GROUPS, topicMembership } from '../packages/backend/src/publication/topics.ts';
const now=new Date();
try {
 const rows=await sql<(ItemRow & {topic_slugs:string[];public_daily:boolean;snapshot_at:string|null})[]>`SELECT ${ITEM_COLUMNS}, ${topicMembership()} AS topic_slugs, (radar_an.output->>'public_daily')='true' AS public_daily, radar_an.output->>'public_snapshot_at' AS snapshot_at ${ITEM_FROM} LEFT JOIN analyses radar_an ON radar_an.id=p.analysis_id
 WHERE ${listedCondition(now)} AND a.raw->>'public_import'='true' AND p.timeline_at >= ${new Date(now.getTime()-30*86400000)} AND p.timeline_at <= ${now}
 ORDER BY p.timeline_at DESC,p.article_id DESC`;
 const [clock]=await sql<{at:string|null}[]>`SELECT max(an.output->>'public_snapshot_at') AS at FROM analyses an JOIN articles a ON a.id=an.article_id WHERE a.raw->>'public_import'='true' AND an.origin='rule' AND an.model='radar-free-import'`;
 const generatedAt=clock?.at || now.toISOString();
 const items=rows.map(row=>({...toItemSummary(row),channel:'news',x:null}));
 const byStory=new Map<string,{publicId:string;title:string;itemIds:string[];selected:boolean}>();
 for(const row of rows)if(row.story_public_id){
  const story=byStory.get(row.story_public_id)||{publicId:row.story_public_id,title:row.story_title||row.title,itemIds:[],selected:false};
  story.itemIds.push(row.id);story.selected ||= row.selected;byStory.set(story.publicId,story);
 }
 const stories=[...byStory.values()];const dailyIds=rows.filter(r=>r.public_daily && r.snapshot_at===generatedAt).map(r=>r.id);
 const topics=TOPICS.map(t=>({id:t.slug,name:t.name,description:t.definition,group:t.group,itemIds:rows.filter(r=>r.topic_slugs.includes(t.slug)).map(r=>r.id)}));
 const out=process.env.RADAR_PUBLIC_OUTPUT||'.public-export/public-news.json';
 await mkdir(path.dirname(out),{recursive:true});
 await writeFile(out,JSON.stringify({version:1,generatedAt,windowDays:30,groups:TOPIC_GROUPS.map(g=>({id:g.key,name:g.name})),topics,items,stories,dailyIds}));
 console.log(`Exported ${items.length} public-news projections; no raw records or administrative fields`);
} finally {await closeDb();}
