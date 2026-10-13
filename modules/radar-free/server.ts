import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import type { ServerModule } from '@aihot/backend/modules';
const exec = promisify(execFile);
export const radarFree: ServerModule = {
 name: 'radar-free',
 schedules: [{name:'radar-free.refresh',cron:'10 * * * *',missed:'once',when:()=>process.env.RADAR_FREE_ONLY==='1' && process.env.RADAR_REFRESH_ENABLED!=='false',run:async()=>{
  const {stdout}=await exec('python3',['scripts/free-cycle.py'],{timeout:45*60*1000,maxBuffer:4*1024*1024});
  return {summary:stdout.slice(-1000)};
 }}],
};
