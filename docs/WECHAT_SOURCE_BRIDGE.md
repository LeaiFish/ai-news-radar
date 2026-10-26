# 官方公众号补充信源

公众号文章通过可选元数据文件接入现有 Radar，不需要 Cowork Studio 部署工具。
目标清单在 `config/wechat_sources.json`：8 个机构，24 个候选账号名。
这些名字是待核验候选，不是已确认覆盖的账号。
千问消费端账号为「千问APP」（已读取代表原文核对名称），与模型研究账号「通义实验室」分开搜索。

## 云端每日采集与发布

GitHub Actions 的 `update-news.yml` 每天北京时间 **10:40** 开始采集公众号文章，
对应 UTC `40 2 * * *`。整个流程在 GitHub 托管 runner 上运行，不依赖本机开机，
不接收微信登录态。其他信源保持原有刷新频率。GitHub 定时任务可能排队或延迟，
10:40 是计划开始时间，网页更新时间还取决于采集和部署耗时。

`scripts/wechat_cloud.py` 优先使用已有公开 AIHOT API 的近 7 日原文线索，
并对「千问」「通义」执行定向查询，避免全站分页上限漏掉试点账号的近期记录。
随后使用 [Exa 的公开免 Key MCP](https://exa.ai/mcp) 的高级搜索，限制微信域名和最近 30 日；
没有结果时才用宽泛搜索补充历史线索。近期 API 线索先占候选预算，不被旧搜索结果挤出。
每账号最多 10 条候选，原文账号和日期仍需独立核验；聚合站日期和搜索日期都不能替代原文日期。
不调用付费 API、不需要新增 Secret，也不绕过微信验证页。

公开搜索仍不能保证完整覆盖最新文章。通义实验室未发现近期候选时保持该事实，
不能把历史文章、聚合站时间或抓取时间填成新文章。两个试点账号近 7 日已核验文章数会单独报告。

以下核验、合并和新闻生成规则同时适用于云端和手动采集：

1. 读取目标清单，用可用网页搜索工具逐账号搜索：`<账号名> 发布 site:mp.weixin.qq.com/s/`。
   可以换产品、月份关键词重试；域名限定无结果时，可从官方站或新闻中的原文链接发现候选。
   搜索成功但无结果记录为成功的空搜索；工具失败记录为失败，不能当成没有新文章。
   仓库现有代表文章可以补充候选，但必须重新核验。每账号最多 10 个候选 URL。
2. 将搜索状态和候选 URL 写入 runner 的 `$RUNNER_TEMP/wechat-candidates.json`，手动操作可使用 `/tmp/radar-wechat-candidates.json`。不要信任搜索摘要中的账号或日期：

   ```json
   {
     "searches": [{"account_name": "DeepSeek", "ok": true}],
     "candidates": [{
       "company_id": "deepseek", "account_name": "DeepSeek",
       "url": "https://mp.weixin.qq.com/s/ARTICLE_ID"
     }]
   }
   ```

   实际任务应包含全部候选账号的搜索状态；遗漏或失败会标记本次发现不完整。
3. 执行 `python scripts/wechat_sources.py --candidates "$RUNNER_TEMP/wechat-candidates.json"`。
   本机手动操作使用虚拟环境 Python 和本机候选文件路径。
   该脚本用移动端 User-Agent 直接读取公开原文；被拦截或限流时，尝试当年 Wayback 存档。
   404、验证页、账号不匹配等均不收录。只比较账号完整名称，忽略空格和大小写，不模糊匹配品牌名。
   原文账号名吻合只证明与候选清单一致，不构成独立的机构所有权认证。
4. 合并至 `data/bridge/wechat-accounts.json`（`wechat_accounts_v1`），按 URL 去重，每个实际账号保留最新 20 条；近7日有效记录超过20条时全部保留。
   只保存公开标题、原文 URL、账号、发布日期与核验时间/依据。没有日期则 `published: null`。
   抓取失败不清空历史。退出码 0 表示本轮无错误，2 表示部分搜索或核验失败；两者均已原子写回结果。
5. 正常运行 `scripts/update_news.py`，即可进入原有归档、AI 相关性、时间窗口和事件合并流程。
   正常流水线随后生成主题与公开新闻投影。未推送的本机文件不会自动出现在 GitHub Pages。

云端随后按工作流的免费配置生成新闻、提交快照、请求 Pages 构建并回读线上
`wechat_bridge.discovery.at`，必须与本轮 `last_run.at` 一致才算部署成功。
文章与搜索服务响应全文只在内存或 runner 临时目录中处理；只有公开字段白名单进入 Git。
采集部分失败时仍发布已核验记录，来源健康状态保留不完整，工作流输出告警和具体原因；
正常账号不匹配仅计为剔除。所有发现渠道不可用、候选核验全部失败或部署失败才将整轮标红。任务不发送 Hi 或其他消息工具通知。

需要立即执行时，在 Actions 的 `Update AI News Snapshot` 中选择 Run workflow，
勾选 `refresh_wechat`；或运行：

```bash
gh workflow run update-news.yml --repo LeaiFish/ai-news-radar --ref master -f refresh_wechat=true
```

采集结果、覆盖账号数、新增归档条数（含历史）、近 24 小时入池数、部署状态和版本在该轮 Actions Summary 中查看。
为避免 10:40 采集被其他刷新取消，工作流对同一分支串行运行、不取消正在执行的任务。

在仓库根目录手动执行免费刷新命令（如有私有 OPML，改用 `feeds/follow.opml`，不提交该文件）：

```bash
RADAR_FREE_ONLY=1 X_API_ENABLED=0 SOCIALDATA_ENABLED=0 TIKHUB_ENABLED=0 EMAIL_DIGEST_ENABLED=0 \
TITLE_ENHANCE_MAX_PER_RUN=0 REASON_ENHANCE_MAX_PER_RUN=0 \
.venv/bin/python scripts/update_news.py --output-dir data --window-hours 24 --archive-days 35 \
  --translate-max-new 0 --translate-max-new-broad 0 --rss-opml feeds/follow.example.opml --rss-max-feeds 20
.venv/bin/python scripts/export-public-news.py --output public-news.json
```

## 可选：手动推送本机快照

云端每日任务直接使用临时 `GITHUB_TOKEN` 提交和请求 Pages 构建，
不需要 SSH 密钥。以下脚本仅用于手动发布本机已核验快照：

```bash
.venv/bin/python scripts/publish_wechat_snapshot.py
```

此命令先校验并重新构造公开字段白名单，再在独立临时目录克隆
`LeaiFish/ai-news-radar` 的最新 `master`，合并远端历史记录，每账号保留最新 20 条（近7日有效记录超过20条时全部保留），
仅提交 `data/bridge/wechat-accounts.json`。不读取或提交本机 Git 暂存区、其他改动、
私有 OPML、登录凭据或全文。远端快照更新时拒绝旧采集覆盖，并发推送失败最多重新合并三次。
需要本机已有 GitHub SSH 推送权限；不要求把凭据复制到仓库或工作流。

推送触发现有 `update-news.yml`：免费更新新闻、生成公开阅读器，然后由现有 GitHub Pages
从 `master` 根目录发布到 <https://leaifish.github.io/ai-news-radar/>。
原有其他信源刷新频率保持不变。网页更新时间取决于采集、Actions 和 Pages 部署是否完成。
若使用本机任务，运行设备需开机并保持网络可用。

发布脚本输出 `pushed` 和提交 SHA 只说明推送成功，不代表部署成功。
手动发布时还必须等待该提交触发的更新工作流和 Pages 部署完成，读取线上
`data/source-status.json`，确认 `wechat_bridge.discovery.at` 与本轮快照
`last_run.at` 一致后才报告线上更新成功。失败或超时如实报告，并附 Actions 链接。
采集部分失败时可以发布已经核验的有效记录，但摘要必须保留失败状态。
每日采集任务只发布经过白名单过滤的元数据，不自动修改产品代码。

## 接入与状态

- 缺少文件：公众号补充源跳过，不请求微信，不影响其他来源。
- 这些公司已核验的官方公众号均按 `T1` / 官方一手源处理。所有日期有效的历史稿先进入新闻归档，不再在入库前套用24小时窗口；保留原始发布日期、账号和核验依据。
- 默认24小时限制用于日常展示，不决定文章能否归档。自动任务启用 `--catch-up`：北京时间周一覆盖周五零点至今，即使周末定时采集正常运行也补看；其他日期若生成任务中断，则回看上次生成后的空档，最多回看归档保留范围，并显式标记截断。定时生成成功不代表用户已读或已处理。
- 日期未知、未来日期、未核验或账号不匹配的文章不会进入当天新闻；未知日期保留在桥接文件中。
- `source-status.json` 的 `wechat_bridge.item_count` 是本轮可入库的全部有效记录数，`recent_window_item_count` 和 `historical_item_count` 分开表示处理窗口内与更早的记录；未知/未来日期另行计数，搜索覆盖和部分失败不因历史回填而清零。
  快照超过 30 小时没有更新会报告 `wechat_snapshot_stale`，仍可使用其中有效的近期文章。
- 本文件只包含公开元数据，可作为 GitHub Actions 的输入提交。不得写入 cookies、token、登录态或全文。
  工作流监测该文件的推送并正常更新站点；云端每日采集与手动快照推送均可触发更新。
- 搜索结果不等于全量订阅。这是尽力补充渠道，不保证新文章的完整性或实时性。

## 本地验证

```bash
.venv/bin/python -m pytest -q tests/test_wechat_sources.py
.venv/bin/python -m pytest -q tests/test_publish_wechat_snapshot.py
.venv/bin/python -m pytest -q tests/test_wechat_cloud.py
.venv/bin/python -m py_compile scripts/wechat_sources.py scripts/update_news.py
```

首次部署需要把脚本、账号配置和工作流一起发布；不能只上传一个 JSON 就声称线上已经接入。

## 可选：在本机配置微信读书通道

登录通道是私有扩展，云端采集仍使用公开搜索和原文核验。本机已提供可选的
`scripts/wechat_wemprss.py`，通过仓库外 we-mp-rss 的微信读书登录读取文章。
`config/wemprss_sources.json` 只含 7 个公众号的公开标识，覆盖 6 个机构；夸克、智谱暂未配置。
如需使用 [we-mp-rss](https://github.com/rachelos/we-mp-rss)，按其
[上游部署说明](https://github.com/rachelos/we-mp-rss/blob/main/README.zh-CN.md)
在 Radar 仓库之外运行。以下只是配置示例，不包含任何现成账号或凭据：

```bash
WECHAT_DATA_DIR="$HOME/.local/share/we-mp-rss"
mkdir -p "$WECHAT_DATA_DIR"
docker run -d --name we-mp-rss \
  -p 127.0.0.1:8001:8001 \
  -v "$WECHAT_DATA_DIR:/app/data" \
  ghcr.io/rachelos/we-mp-rss:latest
```

1. 在本机打开 `http://127.0.0.1:8001`，按上游说明设置独立管理密码。
2. 部署者自行扫码完成授权，再添加 `config/wechat_sources.json` 中需要跟踪的账号。
3. 对已有源码和虚拟环境的 we-mp-rss 安装运行以下命令。适配器在独立子进程中使用上游 SDK，
   读取封面候选及原文 HTML，核对账号和原文日期；正文仅在内存处理。只输出公开元数据，
   不把带凭据的 RSS/API 地址作为公共来源。
4. 登录数据库、Cookie、token、会话文件、二维码和运行日志留在上述私有数据目录。
   不复制到仓库，不上传到 GitHub，不粘贴到文档或 Actions 输出。
5. API 返回的文章列表可能陈旧、缺失或失败；抓取时间不能代替原文发布时间。
   若原文无法核验，只报告未核验，不将其作为新文章发布。

```bash
.venv/bin/python scripts/wechat_wemprss.py --source-dir /absolute/private/we-mp-rss
.venv/bin/python scripts/publish_wechat_snapshot.py
```

每轮本机补采先做一次正常会话续期：`POST /web/login/renewal`，
请求为 `{"rq":"%2Fweb%2Fbook%2Fread","ql":false}`。
2026-10-22 同一新授权的对照验证中，`ql=true` 返回 `-2013`，`ql=false` 返回 `succ=1`；
因此续期失败不能单独证明账号配额耗尽或 Cookie 已过期。
只认可 HTTP 成功、无业务错误且整数 `succ=1`，不以 cookie jar 中仍存在旧令牌判定成功。
续期失败即停止本轮私有文章请求，不枚举令牌、不轮换账号、不重试；公开发现仍可独立完成。
成功续期后如令牌变化，仅在本轮至少一篇原文通过核验后，原子更新仓库外已有主账号的
私有登录文件（权限 0600），保留其他配置并拒绝覆盖已发生变化的会话。
保存失败记录 `wemprss_renewal_persist_failed`，不把内存中的临时成功当成持久恢复。

随后读取文章列表 `/web/mp/articles`：偏移按顶层推送分组递增，
展开每组全部子文章，逐篇用原文 HTML 核验账号、标题和发布日期。完成整页后，
才能在已验证日期保持倒序且整页均早于7日时停止；未知日期或乱序不能作为停止边界。
列表结束或确认窗口边界、且没有核验缺口时，才标记本轮列表覆盖完整。

列表返回 `-2041` 时，本轮停止继续调用列表入口，不轮换读书账号；
再合并现有公开 AIHOT API 最近7日的候选与可读封面。列表日期和聚合站日期
只作发现线索，不代替原文日期。公开长链接直接用无登录头的移动端请求核验，
不跟随验证/登录页、不绕过验证；公开短链接可用对应已配置公众号的正文入口核验。
封面仅作补充，不再是每账号一篇的采集上限。

安全上限为每账号最多 10 个列表页、100 个去重候选；软运行预算 4 分钟，
子进程硬超时 6 分钟。列表受限、核验失败、日期未知或触及安全上限都会明确标记缺口，
保留有效结果和历史，不得把“已扫描到的文章”表述为公众号全量。
`last_run.coverage_complete` 与 `account_coverage` 报告每个公开公众号的列表页数、
候选/核验/未核验数和 complete/fallback/blocked/limited 状态；也进入线上来源状态。
同一 URL 不重复核验；旧的每账号 10 个云端搜索候选上限不用于本机多篇结果。
原有每账号 20 条保留上限在最近7日有效记录超过20条时相应延长，避免丢失新文章。

认证或限流错误停止后续私有请求，服务错误不自动重试、不轮换登录账号。
公开入口限流时停止该入口的核验，已获取结果仍可保留。所有 Cookie、上游响应和正文
仅在仓库外私有子进程内存中处理；只发布经过白名单重构的公开字段。
公开回执保留精确白名单故障码和 `collector`（`wemprss` 或 `public_search`），
不包含上游错误文本、登录账号标识或请求头。`-2012` 只能说明当前访问被拒绝，
单凭它不能区分会话失效和账号配额；不要自动反复扫码或重试。
公开核验依据允许 `weread.qq.com/web/mp/content?reviewId=...`，必须与原文短链接标识一致，
禁止附加登录参数。每日本机任务需设备开机联网；云端 10:40 的公开采集继续作为补充。

公开仓库只保留候选机构账号名、公开文章元数据、校验/发布代码及配置方法。
候选名匹配不等于机构所有权认证；机构归属仍需官网链接或其他公开证据核对。

## 试点身份与重试策略

`config/wechat_sources.json` 的 `identities` 单独记录千问APP、通义实验室的公开 biz 标识和原文依据。
搜索关键词可以映射到同一个待核验实际账号，候选按实际账号和规范 URL 去重；
关键词不代表已确认的公众号别名或独立的机构所有权认证。其他候选仍保持待确认。
URL 的 biz 明确不匹配时直接剔除，避免重复抓取已知其他账号；原文仍须匹配实际账号名。

超时、连接错误、429、500/502/503/504 最多尝试 3 次。
有 `Retry-After` 时遵守服务端等待时间；超过 120 秒的要求保留失败，留待后续运行，不能提前重试。
没有等待提示时限流采用 15/45 秒退避，其他临时错误采用 2/8 秒；401/403/404 不盲目重试。
认证失败或限流重试耗尽时停止该搜索后端，保留各候选名的具体错误代码。

摘要明确区分首次保留到档案的记录数、近 24 小时有效记录数、正常剔除数、采集状态和部署状态。
超过每账号 20 条保留上限而被淘汰的新候选不计入新增归档，历史回填不冒充今日新闻。
