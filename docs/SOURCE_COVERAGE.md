# Source Coverage Plan

## Free public-news processing

The public refresh workflow now sets `RADAR_FREE_ONLY=1`: paid X/SocialData/TikHub
collectors and email ingestion are disabled, model title/reason calls are skipped,
and the paid persona-scoring step is removed. Existing translated caches are reused;
new translations use the keyless Google Translate endpoint only. Its availability
is not guaranteed, and failures retain the original text without a paid fallback.

RSS/Atom descriptions and content snippets are preserved instead of discarded.
`scripts/free_news_content.py` fills missing recent company-topic excerpts from
allowlisted public article pages (JSON-LD, article paragraphs or source metadata).
Requests validate public DNS addresses and every redirect, cap responses at 512 KiB,
and limit each round to 40 fetch attempts and 20 free translations. Failed fetches
wait at least one day before retrying. No login, cookies supplied by the maintainer,
paid reader, LLM, private inbox, local internal metrics or full article body is used.

`data/news-summary-cache.json` stores short original excerpts, optional Chinese
translations and provenance. Topics reuse them by exact original URL, preserving
existing editorial summaries. These are source excerpts, not model-written summaries;
title-only pages and inaccessible bodies remain empty rather than fabricated.

```bash
RADAR_FREE_ONLY=1 python scripts/free_news_content.py --data-dir data --max-fetch 40 --max-translate 20
RADAR_FREE_ONLY=1 python scripts/build_topics.py --data-dir data --translate-max-new 20
```

This project should help ordinary AI enthusiasts scan high-signal updates
without forcing them to follow noisy timelines or manage many source choices.

## Product Model

Use a two-layer model:

1. **Signal layer**: the default web UI. It should show a high-priority curated
   subset first, with the complete AI-related pool available as an explicit
   advanced choice. It should also show AI/tech updates,
   WaytoAGI changes, search, site filtering, and a simple AI-focused / all toggle.
2. **Advanced layer**: maintainer and power-user workflows. It includes OPML,
   source health data, GitHub Actions secrets, and custom fetchers.

Do not expose every source-management decision in the first screen. Too many
choices make the tool harder for new users to understand.
The first screen may show coverage and health as read-only status signals:
source health, AI signal density, official/newsletter coverage, builders/X,
aggregator breadth, and private extension readiness.

## V2 Coverage Claim

The project can be packaged as a Skill because it covers the common public paths
for AI news collection:

- official RSS/Atom/JSON and changelog pages
- OPML collections for personal source lists
- public GitHub-generated feeds such as curated X/blog/newsletter projects
- public newsletter archives and static pages
- optional secret-backed adapters for sources that need user-owned credentials

It does not promise reliable default coverage for private inboxes, cookies,
WeChat accounts, or raw social timelines. Those belong in the advanced layer or
private forks because they need credentials, bridges, or ongoing maintenance.

## Supported Source Types

WeChat additionally supports the opt-in local `scripts/wechat_wemprss.py` adapter.
It uses an external private we-mp-rss installation and verifies account names and
original publication dates from article HTML. Seven configured publisher IDs cover
six companies. The local collector now scans list pages and all subarticles first,
then merges public seven-day AIHOT leads and cover candidates when list coverage is restricted.
Original HTML still determines account identity and publication date. Per-account page/candidate
caps and a runtime budget produce explicit incomplete-coverage diagnostics; a readable cover
never proves complete or latest coverage. All verified seven-day rows are protected from the old
20-row retention cap.
Only public metadata is published. Login state and bodies stay outside the repo;
cloud public discovery continues independently. See `WECHAT_SOURCE_BRIDGE.md`.

| Source type | Current support | Recommended path | Notes |
| --- | --- | --- | --- |
| Official RSS / Atom | Supported through OPML | Add to `feeds/follow.opml` locally, or `FOLLOW_OPML_B64` in GitHub Actions | Best default for personal customization. |
| Official AI vendor updates | Built in for selected high-signal sources | Keep OpenAI, Anthropic, Google DeepMind/AI, Hugging Face, GitHub AI/Changelog, OpenRouter, Cloudflare Blog (AI tag), Apple ML Research, and the domestic lab blogs/changelogs (Qwen, ByteDance Seed, Hunyuan, Quark, DeepSeek, Kimi, MiniMax, Zhipu) as first-class sources | These should not depend only on aggregator coverage. |
| Curated AI media RSS | Built in for selected high-signal public feeds | Keep source-specific caps and AI/research filters so media breadth does not drown the default view | Useful for product, industry, model, and research coverage. |
| OPML collections | Supported | Export from RSS reader, copy from `feeds/follow.example.opml`, keep private file out of git | Good for cross-device and multi-agent workflows. |
| Public JSON APIs | Supported by custom Python fetchers | Add a `fetch_*` function in `scripts/update_news.py` and register it in the task list | Use only stable APIs with timestamps. |
| Public GitHub-generated feeds | Supported by custom Python fetchers | Prefer raw `feed*.json` / RSS / Atom files generated by another repo's Actions | Good for curated projects like Follow Builders. |
| Public static pages | Supported by custom Python fetchers | Parse with `requests` + BeautifulSoup and normalize titles/URLs/times | Avoid fragile selectors when possible. |
| GitHub releases/blogs | Usually supported through Atom/RSS | Prefer GitHub Atom feeds or official blog RSS | Useful for model/platform/tool release tracking. |
| Newsletters | Partially supported | Prefer public archive RSS or stable archive pages | Do not scrape private inboxes. |
| X / Twitter | Supported through curated central feeds, opt-in API adapters, or a private sanitized items-file bridge | Prefer public generated feeds that already use official X API; keep direct X API optional and secret-backed; private cookie scrapes stay off-repo and ingest only via `data/bridge/x-items.json` / `X_BRIDGE_ITEMS_B64` (see `docs/X_PRIVATE_BRIDGE.md`) | Following a person often imports noise; public bridge routes can be unstable; cookies must never enter this repo. |
| WeChat public accounts | Optional verified article metadata input; cloud discovery at 10:40 Asia/Shanghai | `scripts/wechat_cloud.py` discovers public URLs, `wechat_sources.py` verifies original pages, then Actions publishes `data/bridge/wechat-accounts.json`; see `docs/WECHAT_SOURCE_BRIDGE.md` | Best-effort discovery, no completeness guarantee. No WeChat cookies, tokens or bodies in this repo. |
| Telegram / Bilibili / Zhihu / podcasts | Skipped by default when feeds are unreliable | Add only as opt-in OPML entries | These can be noisy or bridge-dependent. |

## Selection source tiers

精选 ranking reads a second tier, `select_tier`, that is not the display
`source_tier` label (官方一手源 / AI垂直源 / …).

| Value | Meaning |
| --- | --- |
| `T1` | Official first-party page or feed: company blog, changelog, newsroom. |
| `T1_5` | Official account or near-official channel, including known company X handles. |
| `T2` | Media, personal blogs, aggregators, and anything not listed. This is the default. |

Set it in one of these places. The first match wins: an explicit value on the
item, then source name, handle, feed URL, site id, then `T2`.

- Built-in RSS lists in `scripts/update_news.py` (`OFFICIAL_AI_FEEDS`,
  `CURATED_AI_MEDIA_FEEDS`) carry `select_tier` on each feed.
- `config/source_tiers.json` maps `by_site_id`, `by_source_name`, `by_handle`,
  and `by_feed_url`. Add a handle or URL there when a new official account
  should outrank media.
- A private OPML outline can set `selectTier="T1"`, `selectTier="T1_5"`, or
  `selectTier="T2"`. `feeds/follow.example.opml` shows the attribute.
  Unknown outlines stay T2.

A story takes the best tier among its sources, so one T1 confirmation lifts
the whole story. Ranking uses independent-source heat first (each outlet
once inside 48 hours; older than 24 hours counts half; the same outlet or
the same URL does not add another point), then this tier as a small bonus.
The daily cap stays 15. T2 stories need a strong signal (官方更新, 多源热议,
or at least two sources) unless that gate would leave 精选 empty.

`data/stories-merged.json` picks up `select_tier`, `source_heat`,
`other_source_count`, and follow-up fields the next time `update_news.py`
runs. This change does not regenerate that snapshot.

Follow-ups are not a second merge. A later story hangs under an earlier
parent only when they share a vendor or model, sit inside 48 hours, and the
titles are related but below the same-story merge threshold. The feed and
workbench can show `另有 N 家` and `进展 N` from `other_source_count` and
`follow_up_count`.

## Source Selection Rules

Add a source only when it passes most of these checks:

- Publishes AI, model, developer tool, or tech industry updates with low noise.
- Has a stable URL, feed, API, or page structure.
- Provides usable timestamps or enough ordering information.
- Does not require private cookies, login sessions, browser automation, or secrets.
- Can be fetched politely by GitHub Actions without heavy rate limits.
- Adds coverage not already represented by stronger sources.

## Built-In Official Nodes

The public site should directly track these high-signal official sources:

- OpenAI News RSS
- Anthropic News page
- Google DeepMind RSS
- Google AI Blog RSS
- Hugging Face Blog RSS
- GitHub AI & ML RSS
- GitHub Changelog RSS
- OpenRouter Blog RSS
- Cloudflare Blog AI-tag RSS
- Apple Machine Learning Research RSS
- Qwen Blog JSON (`qwen.ai` article API)
- ByteDance Seed Blog JSON (豆包 / Seed 技术博客)
- Hunyuan Blog JSON (`api.hunyuan.tencent.com` public list)
- 夸克扫描王开放平台 article index (titles that name 夸克 / 扫描王)
- DeepSeek API changelog (Chinese docs page)
- Kimi API changelog markdown
- MiniMax release notes markdown
- 智谱 GLM release notes markdown

These domestic sources are registered in `DOMESTIC_OFFICIAL_SOURCES` and fetched
from `fetch_official_ai_updates`. They are `T1` in `config/source_tiers.json`.
Domestic posts use a 90-day ingest window (`DOMESTIC_OFFICIAL_MAX_AGE_DAYS`)
because these labs publish about once a month. The daily radar still keys off
`published_at`, so an older post can show up under its company topic without
entering the 24-hour list. Month-only changelog labels (Kimi) are dated to the
first of that month.

Tried and not added: Quark consumer pages (`quark.cn`, `quark.cn/articles`)
have no dated news index. `yuanbao.tencent.com` and `doubao.com` are app
shells. Volcengine news and the Tencent Cloud Hunyuan changelog either require
JavaScript or return an empty shell. GitHub release atoms for the model repos
are empty or years old; high-frequency CLI atoms (`qwen-code`, `kimi-code`)
were left out so patch notes do not crowd model posts. No WeChat or X accounts
were added to those built-in fetchers. Optional checked 公众号 article metadata
can now enter through the bridge described under Domestic WeChat accounts below.

Aggregator sites may already surface some of these updates, but they are not
guaranteed to be complete or timely. Keep these official sources as a stable
baseline, then let the aggregator layer add breadth.

## First-party application updates (2026-10-20)

Application coverage complements lab/model sources. `scripts/official_app_updates.py`
is registered in `collect_all`; each endpoint gets its own source-health row.
Records join the existing global pool and company topics as `official_ai` / `T1`.

| Source | Official endpoint | Intake rule |
| --- | --- | --- |
| Meta AI / Muse Newsroom | <https://about.fb.com/feed/> | Keep Muse, Meta AI, artificial intelligence and AI-glasses announcements. The local live probe failed DNS resolution on 2026-10-20; no fresh items are claimed. The scheduled collector reports failure and retries on the next cycle. |
| Gemini App Blog | <https://blog.google/innovation-and-ai/products/gemini-app/rss/> | Only Gemini application article paths; exclude cross-posted general Google/model/API news. |
| Gemini Product Blog | <https://blog.google/products-and-platforms/products/gemini/rss/> | Same application-path filter. Both Gemini feeds share one publisher name so the same article cannot count as two independent outlets. |
| Gemini release notes | <https://gemini.google/release-notes/> | One entry per explicitly dated release card. |
| ChatGPT product updates | <https://learn.chatgpt.com/docs/whats-new> | Weekly sections with explicit full date ranges; include ChatGPT/Dots blocks, omit API/Codex-only blocks. Timeline date is the stated period's start, not an inferred publication timestamp. Undated event headings are skipped. |
| 千问办公产品更新 | <https://learn.qwenwork.cn/whatsnew/> | One issue per full dated section ID. Linked from the learning community on <https://qwenwork.cn/>. |
| 千问办公客户端更新 | <https://docs.qwenwork.cn/release-notes/desktop> | One dated version block; official homepage links this changelog. |
| 元宝官方版本更新 | <https://itunes.apple.com/lookup?id=6480446430&country=cn> | Match app ID **6480446430** and Tencent's verified seller name before importing current version, release date and release notes. This API exposes the current version; older versions accumulate only after observation. |

Keep at most 20 entries per endpoint within 45 days. Reject undated, future-dated,
off-domain and invalid app-identity records. Keep short source excerpts without
generating editorial judgments. Detect unrecognized page structures as failures.
No login, cookies, paid reader or third-party feed bridge is involved.

Native issue/version anchors remain part of the URL identity through collection
and topic deduplication. Gemini and App Store use standard text-fragment links to
the visible date/version because they offer no native release anchors. This
prevents successive releases on one page from collapsing into a single item;
unrelated article fragments are still stripped.

Verified company WeChat accounts are first-party `T1` sources. Ingest every dated,
verified historical article before applying the display/processing window; preserve
its original date. Scheduled refreshes use `--catch-up`: on Monday (Asia/Shanghai)
they include Friday00:00 through the current run, even if weekend jobs ran. A gap
since the previous snapshot also extends the processing lookback, bounded by archive
retention and recorded in `processing_window`. This does not mark anything as read.

Source Overlap Check against the 30-day archive (2026-10-20), before the stricter
application-path filter: Gemini App Blog had 5 recent entries, 20% hard duplicates
(`accept_default`); Gemini Product Blog had 15, 40% (`watchlist`). The latter is
included with the narrower filter to cover application announcements such as
Skills missing from the first feed; shared URLs/publishers are deduplicated.
Claude developer RSS was 100% duplicated (10/10) and was not added. Notion,
LangChain and Grok remain outside this first application-source batch.

## Built-In Curated Feeds

- **Follow Builders**: reads public `feed-x.json`, `feed-blogs.json`, and
  `feed-podcasts.json` generated by `zarazhangrui/follow-builders`. That project
  uses centralized GitHub Actions plus official X API credentials. This project
  consumes only its public generated JSON files, so public visitors do not need
  X API credentials.
- **Curated AI media RSS**: reads a small set of public RSS/Atom feeds that add
  coverage without requiring login: The Decoder AI News, TechCrunch AI, The
  Verge RSS with strict AI-title filtering, MarkTechPost Research with research
  filtering, VentureBeat AI, Artificial Intelligence News, and Claude Code
  GitHub releases. These feeds are capped per source and pass through the same
  AI relevance scoring as the rest of the radar. Research-heavy feeds are
  intentionally filtered and downweighted so they fill the research lane without
  dominating the default hot view.
- **AI Breakfast**: reads the public Beehiiv archive through Jina Reader because
  the original Beehiiv feed can be blocked from GitHub Actions.
- **AI HOT**: reads the anonymous `https://aihot.news/api/v1/items`
  API (`mode=selected`, `window=7d`, `by=published`, `limit=100`) and keeps only items whose AI HOT card score is at least
  60. The parser preserves AI HOT's Chinese title, valid English original title,
  editorial summary, category, score, and canonical source URL. The RSS feed is
  intentionally not used for the default fetch path because it does not expose
  the source score field needed for this quality gate.
- **Hacker News Algolia**: reads the public
  `https://hn.algolia.com/api/v1/search_by_date` endpoint for the last 24 hours
  of HN stories matching focused AI/tooling keywords such as OpenAI, Anthropic,
  Claude Code, Codex, MCP, Cursor, Gemini, DeepSeek, Qwen, LLM, GPT, Sora, and
  Copilot. This is not a private HN API and does not require a key. It keeps
  only titles with multiple AI keyword signals and enough discussion
  (`num_comments >= 2` or `points >= 10`), so it remains a discussion/heat
  reference rather than a broad HN firehose.
- **WaytoAGI**: reads the public Feishu wiki update log into
  `data/waytoagi-7d.json`; the latest update day is also promoted into the
  community signal lane so it can appear under the Community tab without
  occupying a standalone homepage block.

## Disabled Default Sources

- **X API direct recent search**: supported as an advanced, secret-backed adapter
  through `X_API_ENABLED=1` and `X_BEARER_TOKEN`, but disabled by default because
  current official X API docs describe paid read credits rather than a free daily
  read quota. Use `X_API_MAX_RESULTS`, `X_API_DAILY_POST_LIMIT`, and
  `X_API_RUN_UTC_HOUR` to cap usage.
- **Private X cookie bridge**: supported as an advanced file/secret ingress only.
  An external private scraper may write sanitized public tweet metadata to
  `data/bridge/x-items.json` or supply the same JSON via `X_BRIDGE_ITEMS_B64`.
  Cookies, `auth_token`, `ct0`, and Playwright `storage_state` must never enter
  this repository. Details: `docs/X_PRIVATE_BRIDGE.md`.
- **SocialData.tools X search**: supported as an advanced, secret-backed adapter
  through `SOCIALDATA_ENABLED=1` and `SOCIALDATA_API_KEY`, but disabled by
  default. It reads public X/Twitter search results from the third-party
  SocialData API, not from the official X API. Use `SOCIALDATA_QUERY`,
  `SOCIALDATA_MAX_RESULTS`, `SOCIALDATA_DAILY_TWEET_LIMIT`, and
  `SOCIALDATA_RUN_INTERVAL_HOURS` to keep cost and noise bounded. The default
  SocialData interval is 12 hours. The previous `SOCIALDATA_RUN_UTC_HOUR`
  setting still controls the first run window when no paid-source state exists
  yet. SocialData search normally returns about 20
  tweets per page; the fetcher follows `next_cursor` with the `cursor`
  parameter until the configured effective cap is reached or the API stops
  returning a cursor.
- **TikHub Douyin/Xiaohongshu search**: supported as an advanced,
  secret-backed adapter through `TIKHUB_ENABLED=1` and `TIKHUB_API_KEY`, but
  disabled by default. It reads public Douyin and Xiaohongshu keyword search
  results through TikHub's paid API, not official RSS. Use `TIKHUB_QUERY`,
  `TIKHUB_PLATFORMS`, `TIKHUB_MAX_RESULTS`, `TIKHUB_DAILY_ITEM_LIMIT`, and
  `TIKHUB_RUN_INTERVAL_HOURS` to keep cost and noise bounded. The default
  TikHub interval for Douyin/Xiaohongshu is 24 hours. The previous
  `TIKHUB_RUN_UTC_HOUR` setting still controls the first run window when no
  paid-source state exists yet. Prefer focused AI
  keywords over general hot lists so entertainment trends do not flood the
  Signal view. The default query puts focused AI terms such as OpenAI, Claude,
  large models, Agent, and AI tools ahead of broad `AI`/`人工智能` fallbacks, and
  per-platform caps are spread across keywords so one broad term cannot consume
  the whole paid-source budget. TikHub requests use the most-liked/popularity
  sort and a one-week publish bucket, then the radar enforces the current-week
  cutoff in code. The creator lane uses a separate seven-day pool ranked by
  85% engagement heat plus a 15-point bonus for posts published in the last
  24 hours; the rest of the site remains a 24-hour radar. Xiaohongshu uses the
  recommended App V2 search endpoint
  first and only falls back to Web V3 when App V2 cannot fill the current
  keyword budget. It deduplicates by note id, ignores sentinel API timestamps
  such as zero, infers missing note times from the timestamp prefix in the
  Xiaohongshu note id, and drops results whose publish time is missing or older
  than the current-week window; Douyin stays on TikHub's current Douyin Search
  API rather than deprecated App V3 search paths.

  The official TikHub Python SDK is generated from OpenAPI V5.3.2, so SDK
  resources mirror OpenAPI tags. The SDK documents Douyin coverage as
  `douyin_web`, `douyin_app_v3`, `douyin_search`, `douyin_billboard`,
  `douyin_creator`, and `douyin_xingtu` with 400+ endpoints. The current
  OpenAPI also includes `douyin_creator_v2`, `douyin_index`, and
  `douyin_xingtu_v2`. For AI News Radar, keep the default TikHub read on
  `douyin_search.fetch_general_search_v2`; App V3 search endpoints are
  deprecated, while billboard, creator, xingtu, and index endpoints are better
  future candidates for separate advanced trend/creator lanes.

  The SDK documents Xiaohongshu coverage as `xiaohongshu_web` and
  `xiaohongshu_app` plus v2/v3 variants with 80+ endpoints. Current OpenAPI
  priority is `xiaohongshu_app_v2` first, then `xiaohongshu_app`, then
  `xiaohongshu_web_v2`, then `xiaohongshu_web`; however, the old
  `xiaohongshu_app` and `xiaohongshu_web` tags are marked deprecated in
  OpenAPI. The radar therefore scans `xiaohongshu_app_v2.search_notes` and
  `xiaohongshu_web_v3.fetch_search_notes`, records the `search_surface` in
  public raw output, and treats Web V3 failures as non-fatal when App V2
  succeeds.
- **AgentMail digest**: supported as an advanced metadata-only source through
  `EMAIL_DIGEST_ENABLED=1`, but disabled by default. For the current QQ Agent
  Mail path, set `AGENTMAIL_PROVIDER=agently_cli` after `agently-cli auth login`;
  the fetcher defaults to `agently-cli message +list`. In a privately authorized run, `AGENTMAIL_RESOLVE_PUBLIC_URLS=1` may read allowed senders’ messages in memory to extract newsletter archive URLs; bodies are never written to output. The
  legacy API path remains available with `AGENTMAIL_PROVIDER=api`,
  `AGENTMAIL_API_KEY`, and `AGENTMAIL_INBOX_ID`. It deliberately lists messages
  only and does not publish body text, raw `.eml`, full email addresses, or
  secrets. Use `AGENTMAIL_ALLOWED_SENDER_DOMAINS` to scope a shared inbox. Only
  set `EMAIL_DIGEST_INCLUDE_IN_RADAR=1` when the maintainer explicitly wants
  subject/snippet metadata to appear as the standalone `agentmail` source in
  Radar data.

See `docs/research/advanced-source-free-tier-budget-2026-05-10.md` for the X API
and AgentMail budget notes.

## Domestic WeChat accounts (optional article bridge)

The domestic products already tracked as company topics also publish on WeChat
公众号: 豆包 / ByteDance Seed, 通义千问 / Qwen, 混元·元宝, 夸克, DeepSeek,
Kimi / 月之暗面, MiniMax, and 智谱 / GLM. Those account identities remain
**subject to verification**. An optional metadata bridge now accepts checked
article pages; see `docs/WECHAT_SOURCE_BRIDGE.md` and `config/wechat_sources.json`.
GitHub Actions discovers candidate links through a public no-key search service
and verifies original article pages daily at 10:40 Asia/Shanghai. It does not use
WeChat login sessions or maintain a live RSSHub route. The table below
retains the dated identity research; current article coverage lives in the
bridge snapshot and `source-status.json`.

The ingress follows the optional items-file pattern of
`docs/X_PRIVATE_BRIDGE.md`, using sanitized public article fields only (title,
canonical URL, time, account name and verification evidence). Cookies,
login sessions, and WeChat tokens must never be committed. A self-hosted
RSSHub route or a hand-maintained private OPML entry is acceptable on that
fork only. Do not add these accounts to `feeds/follow.example.opml` or to a
built-in fetcher.

Names below were checked on 2026-09-29 from a public article page or an
official site link. `alias` is the public WeChat ID, `gh_id` is the account
username, and `biz` is the article `__biz` value. Blank ids were not found.
Do not invent them. Rows marked unverified are candidate display names only.

| Product | 公众号名称 | Public id | Status | Check |
| --- | --- | --- | --- | --- |
| 豆包 | 豆包 | not verified | 待覆盖 / pending | IT之家 and 凤凰网 cite 「豆包」微信公众号 as the source of product posts. No article page was opened, so biz and gh_id stay blank. |
| ByteDance Seed | none confirmed | — | 待覆盖 / pending | `seed.bytedance.com` does not link a 公众号. Research posts stay on the public blog. |
| 豆包 / Seed, cloud channel | 火山引擎 | alias `volcengine`; gh_id `gh_dbeb3684fdc7`; biz `MzI0NzU1NzI5NQ==` | 待覆盖 / pending | Verified on a case article linked from `volcengine.com` (`https://mp.weixin.qq.com/s/3IDolpM9CtaHbn8t94aukQ`). Cloud account that mentions 豆包大模型. Not the consumer 「豆包」 account and not a Seed research feed. |
| 通义千问 / Qwen | 通义实验室 | alias `AlibabaTongYiQianWen`; gh_id `gh_954f49cf86d0`; biz `MzkxMTYyMTAzNA==` | 待覆盖 / pending | Articles linked from `qianwen.aliyun.com` use this display name (`https://mp.weixin.qq.com/s/7l5EPTU7cpz7GSN4RP91rg`). The alias is Tongyi Qianwen. A second account titled exactly 「通义千问」 was not confirmed. |
| 混元 | 腾讯混元 (unverified candidate) | not verified | 待覆盖 / pending | Brand name only. No article metadata captured. |
| 元宝 | 腾讯元宝 (unverified candidate) | not verified | 待覆盖 / pending | Press mentions an official account. `yuanbao.tencent.com` has no article index. Display name and biz were not confirmed. |
| 夸克 | 夸克 (unverified candidate) | not verified | 待覆盖 / pending | No official page or article metadata found in this pass. |
| DeepSeek | DeepSeek | alias `deepseek-ai`; gh_id `gh_bc02ff24ae0f`; biz `Mzk0OTYwNzc3NQ==` | 待覆盖 / pending | Ids from the public V4 announcement (`https://mp.weixin.qq.com/s/8bxXqS2R8Fx5-1TLDBiEDg`). `deepseek.com` exposes a follow-account QR. |
| Kimi / 月之暗面 | Kimi智能助手 | alias `kimiai_moonshot`; gh_id `gh_0b101c0f2eb3`; biz `MzkzMTY4NTIyNA==` | 待覆盖 / pending | `moonshot.cn` links `https://mp.weixin.qq.com/s/l2HNlnXaPWT9hW-OXUYrig` as its 微信公众号. Some press says 「月之暗面官方公众号」; the account display name is Kimi智能助手. |
| MiniMax | MiniMax 稀宇科技 | not verified | 待覆盖 / pending | The official MiniMax GitHub poster is titled MiniMax 稀宇科技 and says 扫码关注公众号. That QR payload is a WeCom group link, not a biz id. No article-page gh_id or biz. |
| 智谱 / GLM | 智谱AI or 智谱清言 (unverified candidates) | not verified | 待覆盖 / pending | The `zhipuai.cn` footer QR is a WeCom contact, not a 公众号. The GLM repo WeChat asset is a discussion group. No verified 公众号 id. |

## Example OPML Seeds

`feeds/follow.example.opml` contains a public, low-risk demo set that is expected
to pass through the real project fetch path on GitHub Actions:

- **Official examples**: OpenAI News, OpenRouter Blog, Cloudflare Blog (AI tag),
  Apple Machine Learning Research, Hugging Face Blog, Google DeepMind Blog,
  Google AI Blog, and Microsoft AI Blog.
- **AI media / builder feeds**: Wired AI, InfoQ CN, NVIDIA Generative AI Blog,
  宝玉, and Simon Willison.

This fork's GitHub Actions currently loads the public demo OPML when
`FOLLOW_OPML_B64` is not set (confirmed by `data/source-status.json`: 10 OPML
feeds matching `feeds/follow.example.opml`). Built-in official fetchers always
run regardless of that secret. OpenRouter, Cloudflare Blog (AI tag), and Apple
ML Research are registered in `OFFICIAL_AI_FEEDS` so they ingest even when the
OPML cap or a private follow list omits them. Copy them into a private
`feeds/follow.opml` (or `FOLLOW_OPML_B64`) if you want the OPML path to fetch
them too. The workflow default `RSS_MAX_FEEDS` is 20 so the expanded example
file still loads in full.

In GitHub Actions, `feeds/follow.example.opml` is also used as the public demo
fallback when no private `FOLLOW_OPML_B64` secret is configured. This keeps the
hosted page visibly proving that RSS/OPML import works without requiring any
private subscriptions. Maintainers can override it by setting `FOLLOW_OPML_B64`.
Substack newsletters are intentionally excluded from the public demo OPML because
GitHub Actions runners can receive `403 Forbidden` even when the same feeds work
locally. QbitAI remains on the watchlist because the direct feed probed via
`urllib` but returned `403 Forbidden` through the project fetch path. Broad
sources such as Hacker News frontpage, general hot lists, X bridges, and WeChat
bridges remain outside the example file unless the maintainer explicitly accepts
the extra filtering and maintenance risk.

Recent candidates skipped from the built-in default set:

- **Apple Developer News / Core AI product pages**:
  `https://developer.apple.com/news/rss/news.rss` is a stable public RSS
  (HTTP 200, recent items) but it is general SDK, App Store, and device news,
  not an Apple Intelligence or Core ML changelog. The Apple Intelligence and
  Core ML developer pages have no RSS or timestamped news index worth scraping.
  Best-effort links for maintainers: [Apple Developer News](https://developer.apple.com/news/),
  [Apple Intelligence](https://developer.apple.com/apple-intelligence/),
  [AI & Machine Learning](https://developer.apple.com/machine-learning/).
  The built-in Apple coverage uses
  [Apple Machine Learning Research RSS](https://machinelearning.apple.com/rss.xml)
  instead.
- **LMSYS Blog**: probed feed endpoints redirected or returned 404.
- **Hugging Face Daily Papers**: probed RSS-style endpoints returned 401/404;
  keep it out of the default set until a stable public feed is available.
- **Berkeley RDI Blog**: `/feed.xml` returned only a stale Jekyll placeholder
  item from 2021, so it is not useful as a default source yet.

## Personal Source Workflow

For a private custom setup:

1. Copy `feeds/follow.example.opml` to `feeds/follow.opml`.
2. Add official RSS/Atom feeds to `feeds/follow.opml`.
3. Run:

   ```bash
   python scripts/update_news.py --output-dir data --window-hours 24 --rss-opml feeds/follow.opml
   ```

4. Check `data/source-status.json` for `failed_feeds`, `zero_item_feeds`,
   `skipped_feeds`, and `replaced_feeds`.
5. Keep `feeds/follow.opml` private. For GitHub Actions, store its base64
   content in the `FOLLOW_OPML_B64` secret.

## Adding A Built-In Source

Use this only for sources that should benefit every public visitor:

1. Add a `fetch_<source_name>(session, now)` function in `scripts/update_news.py`.
2. Return `RawItem` objects with `site_id`, `site_name`, `source`, `title`, `url`,
   `published_at`, and `meta`.
3. Register the fetcher in the built-in task list.
4. Normalize URLs and dates using existing helpers.
5. Update this document if the source changes coverage.
6. Run the fastest relevant checks:

   ```bash
   python -m py_compile scripts/update_news.py
   pytest -q
   ```

## Deployment

The public deployment should remain GitHub Pages + GitHub Actions:

- GitHub Actions updates `data/*.json`.
- GitHub Pages serves `index.html` and `assets/*`.
- Private OPML input belongs in `FOLLOW_OPML_B64`, not in the repository.

This keeps the public version easy to fork while still letting each maintainer
bring their own private source list.

## Official service status

The collector reads OpenAI’s public status API and writes `data/service-status.json` separately from news. Only investigating, identified and monitoring incidents appear in the shared mobile/classic banner; resolved incidents, failed reads and snapshots older than two hours stay hidden. A hidden banner is not an assertion that every service is healthy. The normal update workflow publishes the generated file.

## Product-first source supplementation (2026-10-20)

The user prioritizes product functionality, usage, experience and application
scenarios. Model evaluations and technical research remain useful indirect
signals, but do not imply a product release or receive the highest default
selection priority.

| Source | Verified public entry | Intake and bounded capture |
| --- | --- | --- |
| Testing Catalog | <https://www.testingcatalog.com/rss/> | Up to 8 recent long-form entries, T2. The RSS is not a complete mirror of its X account. |
| IT之家 | <https://www.ithome.com/rss/> | Up to 8 dated AI product/use-case articles per refresh, T2; product functionality and user experience come first, with at most 2 technical/evaluation entries after them. Hardware sales, generic AI business headlines, missing/future dates and duplicate canonical URLs are excluded. The public feed holds only 60 recent site-wide articles, so it cannot guarantee historical recovery or complete coverage between polls. |
| LangChain Blog | <https://www.langchain.com/blog/rss.xml> | Up to 8 recent entries, T1. Product updates and real use cases take priority; engineering and eval articles get internal technical tags. The old `blog.langchain.com/rss/` redirects to HTML. |
| Meta Engineering Blog | <https://engineering.fb.com/feed/> | Up to 6 entries with AI/ML/model/agent/inference/training/recommendation signals, T1. Complements the existing Meta product Newsroom. |
| vLLM Blog | <https://vllm.ai/blog/rss.xml> | Up to 4 entries, T1 authority, with an internal `model_technology` tag and lower selection priority. The old `blog.vllm.ai/feed.xml` returned 404. |

The 7-day Source Overlap Check found LangChain 4/14 hard duplicates, Meta 3/7,
vLLM 5/9, and Testing Catalog 0/4 (one possible overlap). Small samples and
moderate overlap remain advisory. These capped direct sources are included at
the user's request to improve first-party independence; duplication does not
create additional independent outlets. Evidence and live probe results are in
`reports/source-intake/2026-10-20-supplement.json`.

Internal `editorial_focus` / `editorial_tags` distinguish product updates,
model evaluation, model technology and technical research. The labels are
rule-based editorial hints, not claims about future product plans. Purely
technical stories rank after other eligible stories in the limited 精选 view;
they remain in the full pool. Their importance score receives a 0.12 deduction.
A mixed story with actual product evidence retains product focus. Source
credibility tiers and AI relevance thresholds are not reduced. No new labels
or filters are added to the reader UI; the public-news projection omits these
internal fields.

Product recognition also uses `scripts/product_context.py`: a known AI product
identity plus concrete functionality, usage instructions, customer scenarios or
experience changes can rescue a title that omits the words AI/LLM. Identity can
come from an exact official host/X handle or matching verified WeChat account
metadata. General cloud accounts, source names alone, ambiguous Muse/museum
substrings, promotional footers, coupons and greetings do not grant this rescue.
Existing adult-promotion rejection runs first. Existing positive relevance scores
are retained. The same evidence drives internal product tags, while evaluation
accounts and model-technology sources keep their technical priority. This changes
selection rules, not reader-facing tags or source credibility tiers.

AIHOT v1 reads original URLs from `links.original`, publisher names from
`source.name`, English titles from `originalTitle`, and pagination from `page`.
The previous `/api/public/*` endpoint is announced to stop on 2026-10-31.
Invalid response envelopes fail explicitly instead of reporting a successful
empty source. Existing score >=60 and selected-only rules remain in place.

The official WeChat discovery flow also collects allowlisted candidate article
URLs from AIHOT's public **all** mode (up to 10 pages / 1,000 entries in 7 days,
with truncation and failures recorded). It never imports aggregator titles,
dates or publisher identity as verification. Every candidate still passes
`wechat_sources.py` original-page account/date checks before admission. Targeted
search remains separate; search failures are not disguised as successful
aggregator coverage.

WeChat quality checks prioritize recent public API leads and date-filtered search, with bounded transient retries, pilot identity checks and explicit historical-versus-24-hour counts. Partial coverage remains visible as a warning and source-health status; see `WECHAT_SOURCE_BRIDGE.md`.

## Personal Agent case leads (2026-10-27)

`https://agentusecases.ai/feed.xml` is collected by `scripts/collect_case_leads.py`
into the independent public metadata file `data/case-leads.json`. The existing
`product-entry` route is now named **Personal Agent 专题**; keeping the route
preserves bookmarks. The topic covers multi-device access, ongoing tasks and
practical delegation. Its case panel prioritizes Shopping & Errands, Life Admin
& Home / Money, Bills & Benefits, and Work & Operations, with separate filters.
Cases never enter latest-news pools, stories, daily briefs or trend-count inputs.

`collected_at` is the directory RSS publication date; `first_seen_at` is our first
observation. `original_published_at` is a nullable day taken from the case page's
explicit Source date, with `date_source=case_directory`. Month/year-only labels
retain their precision without inventing a day; unknown dates remain null. The
original source is linked but not fetched by this collector. Dates and outcomes
are directory-reported metadata, not independent verification or reproduced tests.
Only selected metadata fields are stored; page bodies and suggested prompts are
not retained. RSS/detail fetch failures retain previous cases with visible partial
status. Successful runs retain up to 500 cases collected within 120 days. The RSS
currently exposes 60 entries, so this is ongoing discovery, not a full directory
backfill or a guarantee that all new cases are recovered between refreshes.

Both GitHub Actions and the local free cycle invoke this collector through the
existing `build_topics.py` CLI step; `--skip-case-leads` permits offline topic
rebuilds. No additional workflow permissions are needed. The static
packager and local sync explicitly copy only `data/case-leads.json` as an extra
public artifact, preserving the narrow public export boundary.
