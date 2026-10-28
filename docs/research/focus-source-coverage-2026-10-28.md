# 48个重点信源实际追踪审计（2026-10-28）

本表按原始渠道核对。官网替代、固定快照、聚合发现均不冒充指定账号的持续直采。

当前配置统计：{'official_alternative_only': 19, 'original_web_direct': 14, 'indirect_only': 10, 'wechat_verified_partial': 5}。新增18个官方公开入口，线上验收见对应JSON回执。

| 信源 | 原渠道状态 | 直接采集入口／边界 |
|---|---|---|
| suno | 已接官方替代；X仍间接 | [Suno Blog](https://suno.com/blog)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 |
| OpenRouter（x） | 已接官方替代；X仍间接 | [OpenRouter Blog](https://openrouter.ai/blog/feed.xml)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 |
| OpenRouter（官网） | 原网站渠道已直采 | [OpenRouter Blog](https://openrouter.ai/blog/feed.xml)。仅所列官方栏目/AI内容；不是全站全量。 |
| Hugging Face | 原网站渠道已直采 | [Hugging Face Blog](https://huggingface.co/blog/feed.xml)。仅所列官方栏目/AI内容；不是全站全量。 |
| IT之家 | 原网站渠道已直采 | [IT之家](https://www.ithome.com/rss/)。仅所列官方栏目/AI内容；不是全站全量。 |
| OpenAI Developers | 已接官方替代；X仍间接 | [OpenAI Codex Changelog](https://developers.openai.com/codex/changelog)；[OpenAI Skills](https://github.com/openai/skills/commits/main.atom)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 |
| OpenAI | 已接官方替代；X仍间接 | [OpenAI News](https://openai.com/news/rss.xml)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 |
| Replit | 已接官方替代；X仍间接 | [Replit Blog](https://blog.replit.com/feed.xml)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 |
| Perplexity | 仍为间接覆盖 | 暂无稳定直采入口。官方changelog及blog返回403；API changelog RSS试读404，不绕过访问限制。 |
| Cursor | 原网站渠道已直采 | [Cursor Changelog](https://cursor.com/changelog/rss.xml)。仅所列官方栏目/AI内容；不是全站全量。 |
| GitHub | 原网站渠道已直采 | [Hugging Face open-r1 Commits](https://github.com/huggingface/open-r1/commits/main.atom)。用户样例实际指huggingface/open-r1；直接读取该仓库commit Atom，内部标技术动态，不作模型/产品发布。 |
| xAI | 原网站渠道已直采 | [xAI News](https://x.ai/news)；[Grok Bot Changelog](https://x.ai/changelog/bot)。仅所列官方栏目/AI内容；不是全站全量。 |
| Krea | 已接官方替代；X仍间接 | [Krea Blog](https://www.krea.ai/blog)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 |
| 千问 | 公众号已核验，部分覆盖 | [Qwen Blog](https://qwen.ai/api/v2/article/retrieval?language=zh-CN&type=qwen_ai)。已核验公众号桥接仍部分覆盖，不能把官网替代渠道当该公众号全量。 |
| 腾讯混元 | 公众号已核验，部分覆盖 | [Hunyuan Blog](https://api.hunyuan.tencent.com/api/blog/publicList)。已核验公众号桥接仍部分覆盖，不能把官网替代渠道当该公众号全量。 |
| The Verge | 原网站渠道已直采 | [The Verge](https://www.theverge.com/rss/index.xml)。仅所列官方栏目/AI内容；不是全站全量。 |
| Xiaomi MiMo | 仍为间接覆盖 | 暂无稳定直采入口。原公众号未配置；MiMo首页条目缺完整日期且站点sitemap返回404；不编造发布日期。 |
| Berryxia.AI | 仍为间接覆盖 | 暂无稳定直采入口。指定X账号未建立稳定匿名轮询；AIHOT全量重点补漏仍是间接覆盖。 |
| MiniMax | 已接官方替代；X仍间接 | [MiniMax Blog](https://www.minimax.io/blog)；[MiniMax Release Notes](https://platform.minimaxi.com/docs/release-notes.md)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 |
| Hacker News | 原网站渠道已直采 | [Hacker News AI query](https://hn.algolia.com/api/v1/search_by_date)。仅所列官方栏目/AI内容；不是全站全量。 |
| Huawei Cloud | 已接官方替代；X仍间接 | [Huawei AI Press Releases](https://www.huawei.com/en/rss-feeds/huawei-updates/rss)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 新RSS来自华为集团，仅云/AI相关条目，不等于Huawei Cloud账号全量。 |
| 火山引擎 | 公众号已核验，部分覆盖 | [ByteDance Seed Blog](https://seed.bytedance.com/zh/blog)。已核验公众号桥接仍部分覆盖，不能把官网替代渠道当该公众号全量。 |
| claude | 原网站渠道已直采 | [Claude Articles](https://claude.com/resources/articles)。仅所列官方栏目/AI内容；不是全站全量。 |
| NotebookLM | 已接官方替代；X仍间接 | [Gemini Notebook Blog](https://blog.google/innovation-and-ai/products/gemini-notebook/rss/)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 |
| eric zakariasson | 仍为间接覆盖 | 暂无稳定直采入口。指定X账号未建立稳定匿名轮询；AIHOT全量重点补漏仍是间接覆盖。 |
| Fei-Fei Li | 仍为间接覆盖 | 暂无稳定直采入口。指定X账号未建立稳定匿名轮询；AIHOT全量重点补漏仍是间接覆盖。 |
| Luma | 已接官方替代；X仍间接 | [Luma News](https://lumalabs.ai/news)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 |
| Apple | 原网站渠道已直采 | [Apple Developer News](https://developer.apple.com/news/rss/news.rss)；[Apple Machine Learning Research](https://machinelearning.apple.com/rss.xml)。仅所列官方栏目/AI内容；不是全站全量。 |
| Viggle AI | 已接官方替代；X仍间接 | [Viggle Blog](https://viggle.ai/blog)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 官网列表缺日期，每轮最多读取8个公开文章元数据；无法保证列表之外的回填。 |
| TechCrunch | 原网站渠道已直采 | [TechCrunch AI](https://techcrunch.com/category/artificial-intelligence/feed/)。仅所列官方栏目/AI内容；不是全站全量。 |
| Kimi | 公众号已核验，部分覆盖 | [Kimi API Changelog](https://platform.kimi.com/docs/changelog.md)。已核验公众号桥接仍部分覆盖，不能把官网替代渠道当该公众号全量。 |
| MarkTechPost | 原网站渠道已直采 | [MarkTechPost Research](https://www.marktechpost.com/feed/)。仅所列官方栏目/AI内容；不是全站全量。 |
| ChatGPT | 已接官方替代；X仍间接 | [ChatGPT Product Updates](https://learn.chatgpt.com/docs/whats-new)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 |
| Runway | 已接官方替代；X仍间接 | [Runway News](https://runway.com/news)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 |
| Rohan Paul | 仍为间接覆盖 | 暂无稳定直采入口。指定X账号未建立稳定匿名轮询；AIHOT全量重点补漏仍是间接覆盖。 |
| Michael Truell | 仍为间接覆盖 | 暂无稳定直采入口。指定X账号未建立稳定匿名轮询；AIHOT全量重点补漏仍是间接覆盖。 |
| Google Gemini | 已接官方替代；X仍间接 | [Gemini App Blog](https://blog.google/innovation-and-ai/products/gemini-app/rss/)；[Gemini Release Notes](https://gemini.google/release-notes/)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 |
| Google AI | 已接官方替代；X仍间接 | [Google AI Blog](https://blog.google/innovation-and-ai/technology/ai/rss/)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 |
| Cloudflare Blog | 原网站渠道已直采 | [Cloudflare Blog](https://blog.cloudflare.com/tag/ai/rss/)。仅所列官方栏目/AI内容；不是全站全量。 |
| OpenBMB | 已接官方替代；X仍间接 | [OpenBMB MiniCPM Releases](https://github.com/OpenBMB/MiniCPM/releases.atom)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 |
| 通义实验室 | 公众号已核验，部分覆盖 | [Qwen Blog](https://qwen.ai/api/v2/article/retrieval?language=zh-CN&type=qwen_ai)。已核验公众号桥接仍部分覆盖，不能把官网替代渠道当该公众号全量。 |
| Elon Musk | 仍为间接覆盖 | 暂无稳定直采入口。指定X账号未建立稳定匿名轮询；AIHOT全量重点补漏仍是间接覆盖。 |
| Alibaba Cloud | 已接官方替代；X仍间接 | [Alibaba Cloud Blog](https://www.alibabacloud.com/blog)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 |
| anthropic | 原网站渠道已直采 | [Anthropic News](https://www.anthropic.com/news)。仅所列官方栏目/AI内容；不是全站全量。 |
| SiliconFlow | 已接官方替代；X仍间接 | [SiliconFlow Blog](https://www.siliconflow.com/blog)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 |
| Satya Nadella | 仍为间接覆盖 | 暂无稳定直采入口。指定X账号未建立稳定匿名轮询；AIHOT全量重点补漏仍是间接覆盖。 |
| Logan Kilpatrick | 仍为间接覆盖 | 暂无稳定直采入口。指定X账号未建立稳定匿名轮询；AIHOT全量重点补漏仍是间接覆盖。 |
| ClaudeDevs | 已接官方替代；X仍间接 | [Claude Code Releases](https://github.com/anthropics/claude-code/releases.atom)；[Claude Articles](https://claude.com/resources/articles)。官方官网/RSS是补充渠道，指定X账号仍仅有聚合/既有快照覆盖。 |

## 已知边界

- 官网页面只使用明确发表日期；dateModified、抓取时间、月份缺日均不替代发布日期。
- 每源独立健康记录；近期零条与访问/解析失败分开。原有官方RSS也已拆出独立健康记录。
- 文章保留原始标题和来源，按已有URL及事件规则去重。技术、营销、个人评论不因优先级变成产品发布。
- Perplexity 403、MiMo日期/发现缺口及公众号部分覆盖保留未解决状态。
- 人物账号与机构账号分别标注；@poteto为团队成员个人账号，来源层级T2。

回执：`reports/source-intake/2026-10-28-focus-direct-tracking.json`。
