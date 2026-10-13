// Only consumes the public projection made by export-public-news.py; never a DB backup.
import { readFile } from 'node:fs/promises';
import { isIP } from 'node:net';
import { isBlockedAddress } from '../packages/backend/src/lib/url.ts';
import { createHash } from 'node:crypto';
import { sql, closeDb } from '../packages/backend/src/db.ts';
import { upsertMaterial } from '../packages/backend/src/content/materials.ts';
import { publishArticle } from '../packages/backend/src/publication/publish.ts';
const input = JSON.parse(await readFile(process.env.RADAR_PUBLIC_INPUT || '.public-export/public-news.json', 'utf8'));
if (input.version !== 1 || !Array.isArray(input.items) || !Array.isArray(input.topics)) throw new Error('Not a public-news projection');
const allowed = new Set(['id','title','originalTitle','summary','source','links','publishedAt','discoveredAt','timelineAt','category','tags','reason','score','selected','channel','x','story']);
let count=0;
const facts=new Map<string,number>();
const storyIds=new Map<string,number>();
try {
 for (const story of input.stories || []) {
  if (!/^[0-9a-f-]{36}$/.test(story.publicId) || typeof story.title!=='string' || !Array.isArray(story.itemIds)) throw new Error('Invalid public story');
  const times=input.items.filter((i:{id:string})=>story.itemIds.includes(i.id)).map((i:{timelineAt:string})=>new Date(i.timelineAt).getTime());
  if(!times.length)continue;
  const [saved]=await sql<{id:number}[]>`INSERT INTO stories (public_id,title,origin,frame,first_report_at,latest_at) VALUES (${story.publicId},${story.title},'manual',${sql.json({provenance:'radar-rule-import'})},${new Date(Math.min(...times))},${new Date(Math.max(...times))}) ON CONFLICT (public_id) DO UPDATE SET title=excluded.title, first_report_at=excluded.first_report_at, latest_at=excluded.latest_at RETURNING id`;
  const [fact]=await sql<{id:number}[]>`INSERT INTO facts (public_id,story_id,title) VALUES (${'radar-'+story.publicId},${saved!.id},${story.title}) ON CONFLICT (public_id) DO UPDATE SET title=excluded.title RETURNING id`;
  for(const id of story.itemIds) {facts.set(id,fact!.id);storyIds.set(id,saved!.id);}
 }
 for (const item of input.items) {
  if (Object.keys(item).some(k=>!allowed.has(k)) || !/^[a-zA-Z0-9_-]{1,80}$/.test(item.id)) throw new Error('Unexpected public item fields');
  const url=new URL(item.links.original);
  if (!['https:','http:'].includes(url.protocol) || url.username || url.password || !url.hostname.includes('.') || /(?:localhost|\.local|\.internal)$/.test(url.hostname)) throw new Error('Invalid original URL');
  if (isIP(url.hostname) && isBlockedAddress(url.hostname)) throw new Error('Private original URL');
  const sourceName=String(item.source.name);
  const sourceId='radar-'+createHash('sha256').update(sourceName).digest('hex').slice(0,24);
  await sql`INSERT INTO sources (id,name,kind,enabled,site_fulltext,syndicate_fulltext,participation_mode) VALUES (${sourceId},${sourceName},'external',false,false,false,'editorial') ON CONFLICT (id) DO NOTHING`;
  const result=await upsertMaterial({id:item.id,sourceId,url:url.href,title:item.originalTitle||item.title,publishedAt:new Date(item.publishedAt),discoveredAt:new Date(item.discoveredAt),excerpt:item.summary,bodyStatus:'none',raw:{public_import:true,public_snapshot_at:input.generatedAt,public_daily:(input.dailyIds||[]).includes(item.id)},via:'import',backfill:'radar-public-history'});
  const subjects=input.topics.filter((t:{itemIds:string[]})=>t.itemIds.includes(item.id)).map((t:{id:string})=>t.id);
  const [article]=await sql<{revision:number}[]>`SELECT revision FROM articles WHERE id=${result.articleId}`;
  const output={provenance:'radar-free-pipeline',scope:'single',public_import:true};
  // Rule provenance and null score: no model was called and no AI judgement is invented.
  await sql`DELETE FROM analyses WHERE article_id=${result.articleId} AND origin='rule' AND model='radar-free-import'`;
  await sql`INSERT INTO analyses (article_id,input_revision,origin,model,prompt_version,relevance,tags,subjects,title_zh,summary_zh,score,selected,output) VALUES (${result.articleId},${article!.revision},'rule','radar-free-import','1','pass',${subjects.map((s:string)=>'entity:'+s)},${subjects},${item.title},${item.summary},NULL,${item.selected===true},${sql.json(output)})`;
  await sql`UPDATE articles SET processing_state='analyzed' WHERE id=${result.articleId}`;
  if(facts.has(item.id)) {
   await sql`INSERT INTO fact_articles (fact_id,article_id,role,evidence) VALUES (${facts.get(item.id)!},${result.articleId},'report','Imported legacy keyword/URL grouping; no model judgement') ON CONFLICT (fact_id,article_id) DO NOTHING`;
   await sql`INSERT INTO story_signals (story_id,article_id,participant_key,source_id,kind,observed_at) VALUES (${storyIds.get(item.id)!},${result.articleId},${sourceId},${sourceId},'editorial',${new Date(item.timelineAt)}) ON CONFLICT (story_id,article_id) DO UPDATE SET observed_at=excluded.observed_at`;
  }
  await publishArticle(result.articleId,{releasedAt:new Date(item.timelineAt)});
  count++;
 }
 console.log(`Imported ${count} public news items through native publication layer`);
} finally { await closeDb(); }
