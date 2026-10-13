/* Adapt the public-only news outlet to the unchanged Radar presentation. */
(() => {
  let snapshot;
  window.radarPublicProjection = async (path, root) => {
    snapshot ||= fetch(new URL('public-news.json', root), {cache:'no-cache'}).then(response => {
      if (!response.ok) throw new Error('Public news unavailable');
      return response.json();
    });
    const data = await snapshot;
    const items = data.items.map(row => ({id:row.id,title:row.title,title_zh:row.originalTitle ? row.title : null,title_en:row.originalTitle,url:row.links.original,summary:row.summary || '',source:row.source.name,source_name:row.source.name,published_at:row.timelineAt || row.publishedAt,curated:row.selected,source_count:1}));
    const byId = new Map(items.map(row => [row.id,row]));
    const topics = data.topics.map(topic => {
      const rows = topic.itemIds.map(id => byId.get(id)).filter(Boolean);
      return {...topic,item_count:rows.length,recent_item_count:rows.length,listed_count:rows.length,latest_title:rows[0]?.title || '',latest_published_at:rows[0]?.published_at || '',items:rows};
    });
    const stories = data.stories.map(story => {
      const rows=story.itemIds.map(id=>byId.get(id)).filter(Boolean);
      return {story_id:story.publicId,title:story.title,items:rows,sources:rows,source_count:new Set(rows.map(row=>row.source)).size,latest_at:rows[0]?.published_at,url:rows[0]?.url,primary_url:rows[0]?.url,curated:story.selected};
    });
    const base={generated_at:data.generatedAt,window_hours:24};
    if (path==='data/topics.json') return {...base,topics,groups:data.groups};
    if (path==='data/stories-merged.json') return {...base,stories};
    if (path==='data/daily-brief.json') return {...base,items:data.dailyIds.map(id=>byId.get(id)).filter(Boolean)};
    const match=path.match(/^data\/topics\/([^/]+)\.json$/);
    if (match) return topics.find(topic=>topic.id===match[1]) || {items:[]};
    throw new Error('Unsupported public projection path');
  };
})();
