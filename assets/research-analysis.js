/* Free, evidence-based aggregation. Counts describe collected reports, not company strategy. */
(() => {
  const themes = [
    {id:'agent',name:'Agent 与任务执行',pattern:/agent|智能体|千问\s*go|qwen\s*go|自动执行|代理式/i,direction:'从对话能力向可执行任务的产品与工具链延伸'},
    {id:'multimodal',name:'多模态与内容生成',pattern:/多模态|图像|视频|语音|音频|image|video|audio|speech|seedream|seedance/i,direction:'拓展图像、视频和语音等交互及内容生产能力'},
    {id:'model',name:'模型能力与开发生态',pattern:/模型|开源|权重|推理|训练|评测|benchmark|model|reasoning|inference|open.weight|github|开发者/i,direction:'持续投入模型能力、推理效率及开发者生态'},
    {id:'product',name:'应用入口与场景落地',pattern:/app|应用|入口|助手|搜索|办公|上线|公测|assistant|search|launch/i,direction:'把能力接入用户入口和具体使用场景'},
    {id:'business',name:'商业化与合作',pattern:/收费|订阅|价格|定价|付费|商业|合作|企业|token套餐|pricing|subscription|partnership|enterprise/i,direction:'探索付费、企业服务与生态合作的落地路径'},
    {id:'safety',name:'安全与治理',pattern:/安全|对齐|风险|监管|隐私|越界|cbrn|safety|security|alignment|privacy/i,direction:'加强能力上线后的安全、对齐和风险治理'},
    {id:'organization',name:'组织与资本动作',pattern:/融资|收购|组织|部门|人事|ipo|funding|acquisition|valuation/i,direction:'通过组织或资本动作支持后续投入'}
  ];
  globalThis.radarAnalyzeResearch = (beats, end) => {
    const seen=new Set();
    const rows=beats.filter(row=>{
      const time=Date.parse(row.published_at);
      const key=String(row.title||'').toLowerCase().replace(/[\s\p{P}]/gu,'');
      if (!key || seen.has(key) || !Number.isFinite(time) || time>end || time<end-30*86400000) return false;
      seen.add(key);return true;
    });
    const ranked=themes.map(theme=>{
      const evidence=rows.filter(row=>theme.pattern.test(row.title||''));
      return {...theme,count:evidence.length,evidence:evidence.slice(0,2)};
    }).filter(theme=>theme.count>=2).sort((a,b)=>b.count-a.count);
    return {total:rows.length,sources:new Set(rows.map(row=>row.source).filter(Boolean)).size,themes:ranked.slice(0,3)};
  };
})();
