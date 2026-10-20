# 官方公众号补充信源

公众号文章通过可选元数据文件接入现有 Radar，不需要 Cowork Studio 部署工具。
目标清单在 `config/wechat_sources.json`：8 个机构，24 个候选账号名。
这些名字是待核验候选，不是已确认覆盖的账号。
千问消费端账号为「千问APP」（已读取代表原文核对名称），与模型研究账号「通义实验室」分开搜索。

## 每日采集

定时 Agent 在 Asia/Shanghai 每天 10:40 开始执行以下流程。不发送任何 Hi 消息。

1. 读取目标清单，用可用网页搜索工具逐账号搜索：`<账号名> 发布 site:mp.weixin.qq.com/s/`。
   可以换产品、月份关键词重试；域名限定无结果时，可从官方站或新闻中的原文链接发现候选。
   搜索成功但无结果记录为成功的空搜索；工具失败记录为失败，不能当成没有新文章。
   仓库现有代表文章可以补充候选，但必须重新核验。每账号最多 10 个候选 URL。
2. 将搜索状态和候选 URL 写入 `/tmp/radar-wechat-candidates.json`，不要信任搜索摘要中的账号或日期：

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
3. 执行 `.venv/bin/python scripts/wechat_sources.py --candidates /tmp/radar-wechat-candidates.json`。
   该脚本用移动端 User-Agent 直接读取公开原文；被拦截或限流时，尝试当年 Wayback 存档。
   404、验证页、账号不匹配等均不收录。只比较账号完整名称，忽略空格和大小写，不模糊匹配品牌名。
   原文账号名吻合只证明与候选清单一致，不构成独立的机构所有权认证。
4. 合并至 `data/bridge/wechat-accounts.json`（`wechat_accounts_v1`），按 URL 去重，每个实际账号保留最新 20 条。
   只保存公开标题、原文 URL、账号、发布日期与核验时间/依据。没有日期则 `published: null`。
   抓取失败不清空历史。退出码 0 表示本轮无错误，2 表示部分搜索或核验失败；两者均已原子写回结果。
5. 正常运行 `scripts/update_news.py`，即可进入原有归档、AI 相关性、时间窗口和事件合并流程。
   正常流水线随后生成主题与公开新闻投影。未推送的本机文件不会自动出现在 GitHub Pages。

本机定时任务使用免费刷新命令（如有私有 OPML，改用 `feeds/follow.opml`，不提交该文件）：

```bash
RADAR_FREE_ONLY=1 X_API_ENABLED=0 SOCIALDATA_ENABLED=0 TIKHUB_ENABLED=0 EMAIL_DIGEST_ENABLED=0 \
TITLE_ENHANCE_MAX_PER_RUN=0 REASON_ENHANCE_MAX_PER_RUN=0 \
.venv/bin/python scripts/update_news.py --output-dir data --window-hours 24 --archive-days 35 \
  --translate-max-new 0 --translate-max-new-broad 0 --rss-opml feeds/follow.example.opml --rss-max-feeds 20
.venv/bin/python scripts/export-public-news.py --output public-news.json
```

## 自动发布到线上

首次发布接入脚本、账号配置和工作流后，每日采集完成执行：

```bash
.venv/bin/python scripts/publish_wechat_snapshot.py
```

此命令先校验并重新构造公开字段白名单，再在独立临时目录克隆
`LeaiFish/ai-news-radar` 的最新 `master`，合并远端历史记录，每账号最多保留 20 条，
仅提交 `data/bridge/wechat-accounts.json`。不读取或提交本机 Git 暂存区、其他改动、
私有 OPML、登录凭据或全文。远端快照更新时拒绝旧采集覆盖，并发推送失败最多重新合并三次。
需要本机已有 GitHub SSH 推送权限；不要求把凭据复制到仓库或工作流。

推送触发现有 `update-news.yml`：免费更新新闻、生成公开阅读器，然后由现有 GitHub Pages
从 `master` 根目录发布到 <https://leaifish.github.io/ai-news-radar/>。
原有其他信源刷新频率保持不变。10:40 是公众号采集开始时间，网页上线会晚于该时间，
且本机定时采集需要电脑开机、应用运行和网络可用。

发布脚本输出 `pushed` 和提交 SHA 只说明推送成功，不代表部署成功。
每日 Agent 还必须等待该提交触发的更新工作流和 Pages 部署完成，读取线上
`data/source-status.json`，确认 `wechat_bridge.discovery.at` 与本轮快照
`last_run.at` 一致后才报告线上更新成功。失败或超时如实报告，并附 Actions 链接。
采集部分失败时可以发布已经核验的有效记录，但摘要必须保留失败状态。
每日任务不得修改或推送产品代码，不发送任何 Hi 或其他消息工具通知。

## 接入与状态

- 缺少文件：公众号补充源跳过，不请求微信，不影响其他来源。
- 核验通过且发布时间在过去 24 小时的文章进入当日 Radar，官方账号采用 `T1_5`。
- 日期未知、未来日期、未核验或账号不匹配的文章不会进入当天新闻；未知日期保留在桥接文件中。
- `source-status.json` 的 `wechat_bridge` 报告入池数量、无日期数量、搜索覆盖和部分失败。
  快照超过 30 小时没有更新会报告 `wechat_snapshot_stale`，仍可使用其中有效的近期文章。
- 本文件只包含公开元数据，可作为 GitHub Actions 的输入提交。不得写入 cookies、token、登录态或全文。
  工作流监测该文件的推送并正常更新站点；每日 Agent 的本机执行与远端发布是两个可分别验证的环节。
- 搜索结果不等于全量订阅。这是尽力补充渠道，不保证新文章的完整性或实时性。

## 本地验证

```bash
.venv/bin/python -m pytest -q tests/test_wechat_sources.py
.venv/bin/python -m pytest -q tests/test_publish_wechat_snapshot.py
.venv/bin/python -m py_compile scripts/wechat_sources.py scripts/update_news.py
```

首次部署需要把脚本、账号配置和工作流一起发布；不能只上传一个 JSON 就声称线上已经接入。

## 微信读书通道实测（2026-10-20）

在独立的本机临时环境测试了 [we-mp-rss](https://github.com/rachelos/we-mp-rss)，
代码版本 `d94db01372105bc479db81a0ac91829dac7f43e4`。用户扫码登录成功，
微信读书封面接口返回两个目标账号的文章；再次直接读取公众号原文，核对账号名和发布日期：

| 原文账号 | 返回文章 | 原文发布时间（北京时间） |
| --- | --- | --- |
| 千问APP | [千问AI耳机接入千问App，有事开口聊！](https://mp.weixin.qq.com/s/63gcPhH99__DUGgLuO__lQ) | 2026-10-15 17:54 |
| 通义实验室 | [从“能说话”到“会表达”：Qwen-Audio-3.0-TTS 发布](https://mp.weixin.qq.com/s/INvrqTrWLMm2WCLIqhqTrg) | 2026-07-20 16:54 |

两条公开元数据已去重合入桥接文件，均不在过去 24 小时窗口内。
这是接口返回的最新文章，不足以证明公众号实际最新文章；通义实验室的返回结果明显陈旧。
两个账号的文章列表接口都返回业务错误码 `-2041`，本次未取得完整历史列表。

该版本上游封面兜底逻辑使用抓取时间填写 `create_time` / `update_time`，
不能把据此生成的订阅时间直接当成原文发布时间。此次写入使用原文日期。
尚未将此登录通道接入每日任务；每日任务仍使用公开搜索和原文核验。
登录凭据留在独立测试环境，不进入 Radar 仓库；本次未发布线上变更。
