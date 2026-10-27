import { copyFile, mkdir, writeFile, access, rm, readdir } from 'node:fs/promises';
const out='.public-export/site';
await rm(`${out}/assets`,{recursive:true,force:true});
await mkdir(`${out}/assets`,{recursive:true});
await mkdir(`${out}/config`,{recursive:true});
await copyFile('legacy-radar.html',`${out}/index.html`);
await copyFile('history.html',`${out}/history.html`);
for (const name of ['logo.svg','styles.css','sidebar.css','topics.css','perspective.css','perspective.js','public-projection.js','aihot-skin.css','research-analysis.js','trend-reports.js','trend-history.js','history.css']) await copyFile(`assets/${name}`,`${out}/assets/${name}`);
await copyFile('config/topics.json',`${out}/config/topics.json`);
if (await access('.public-export/public-news.json').then(()=>true,()=>false)) await copyFile('.public-export/public-news.json',`${out}/public-news.json`);
await writeFile(`${out}/.nojekyll`,'');
console.log('Previous Radar layout packaged with public-only news.');

if (await access('data/trends/latest.json').then(()=>true,()=>false)) {
  await rm(`${out}/data/trends`, {recursive:true, force:true});
  await mkdir(`${out}/data/trends`, {recursive:true});
  for (const name of ['latest.json','history.json','corrections.json']) {
    if (await access(`data/trends/${name}`).then(()=>true,()=>false)) await copyFile(`data/trends/${name}`, `${out}/data/trends/${name}`);
  }
  for (const [folder, pattern] of [['daily',/^\d{4}-\d{2}-\d{2}\.json$/],['weekly',/^\d{4}-W\d{2}\.json$/],['history',/^[a-f0-9]{64}\.json$/]]) {
    await mkdir(`${out}/data/trends/${folder}`, {recursive:true});
    for (const name of await readdir(`data/trends/${folder}`).catch(()=>[])) if(pattern.test(name)) await copyFile(`data/trends/${folder}/${name}`, `${out}/data/trends/${folder}/${name}`);
  }
}
