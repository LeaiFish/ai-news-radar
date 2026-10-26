import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../assets/trend-history.js',import.meta.url),'utf8');
for(const malformed of [null,{schema:'radar_trend_history_v1',latest_report_id:'a'.repeat(64),reports:[null]},{schema:'radar_trend_history_v1',latest_report_id:'a'.repeat(64),reports:[],directions:null}]) {
 test('malformed history cannot break the current page: '+JSON.stringify(malformed),()=>{
  const ctx=vm.createContext({document:{createElement(){throw new Error('invalid history rendered');}},URL});vm.runInContext(source,ctx);
  assert.doesNotThrow(()=>{ctx.radarTrendHistory.set(malformed);ctx.radarTrendHistory.overview({querySelector(){return null;}});});
 });
}
