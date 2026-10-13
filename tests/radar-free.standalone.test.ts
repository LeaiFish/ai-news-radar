import assert from 'node:assert/strict';
import { test } from 'node:test';
import { paidRequest } from '@aihot/backend/providers/receipts';
import { isPoolEligible } from '@aihot/backend/publication/rules';
test('free-only blocks every paid provider before DB reservation or external callback', async()=>{
 const previous=process.env.RADAR_FREE_ONLY;process.env.RADAR_FREE_ONLY='1';let called=false;
 try {
  for(const service of ['llm','embeddings','dajiala','socialdata','jina']) await assert.rejects(paidRequest({service,purpose:'test',identity:{}},async()=>{called=true;throw new Error('must not run');}),/Paid services are disabled/);
  assert.equal(called,false);
 } finally { if(previous===undefined)delete process.env.RADAR_FREE_ONLY;else process.env.RADAR_FREE_ONLY=previous; }
});
test('title-only free public news stays readable, while withdrawn source modes stay ineligible',()=>{
 const previous=process.env.RADAR_FREE_ONLY;process.env.RADAR_FREE_ONLY='1';
 try {
  assert.equal(isPoolEligible({participationMode:'editorial',relevance:'pass',title:'公开新闻',summary:null}),true);
  assert.equal(isPoolEligible({participationMode:'isolated',relevance:'pass',title:'内部数据',summary:null}),false);
  assert.equal(isPoolEligible({participationMode:'editorial',relevance:'block',title:'无关信息',summary:null}),false);
 } finally {if(previous===undefined)delete process.env.RADAR_FREE_ONLY;else process.env.RADAR_FREE_ONLY=previous;}
});
