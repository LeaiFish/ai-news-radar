import { copyFile, writeFile } from 'node:fs/promises';
await copyFile('.public-export/public-news.json','.public-export/site/public-news.json');
await writeFile('.public-export/site/.nojekyll','');
console.log('Public static package ready: .public-export/site (no backend, credentials or database)');
