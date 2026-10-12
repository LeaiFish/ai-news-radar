# Tidings RSS 与公众号导出上游核查

核查日期：2026-10-12。仅阅读公开源码、目录与验证记录，没有登录微信、抓取账号凭据或读取本地内部数据。

## RSS 候选

`fuxiaoai/tidings-rss` 提供 718 个订阅目录，其中 AI 包 99 个、公众号包 30 个。
最适合补充本项目的是：

| 来源 | 作用 | 处理建议 |
| --- | --- | --- |
| IT之家 `https://www.ithome.com/rss/` | 国内产品、消费端 AI、豆包等消息 | 直接媒体 RSS，优先重新验证和检查重复率；过滤非 AI 消息 |
| 量子位 `https://www.qbitai.com/feed` | 中文 AI 专门媒体 | 优先重新验证和检查重复率 |
| 通义实验室 | 千问官方公众号发布 | 公开 WeChat2RSS 桥候选，补充 Qwen Blog |
| 月之暗面 Kimi | Kimi 官方公众号发布 | 公开 WeChat2RSS 桥候选，补充 API Changelog |
| 智谱、腾讯混元、DeepSeek | 官方公众号消息 | 公开桥候选，不替换现有官方网页 |
| 机器之心、新智元、机器之心SOTA模型 | 中文研究、产品、模型消息 | 媒体公众号候选，注意多源重复 |
| 字节跳动技术团队 | 工程与基础设施 | 不是豆包产品公众号，不作为豆包产品信源的替代 |

目录中未找到明确名为“豆包”的官方公众号 RSS。候选清单已保存为
`feeds/tidings-ai-candidates.opml`，未合并到默认订阅。

目录中的这些 feed 多数标注 `validated_at=2026-08-12`。通义实验室、Kimi、DeepSeek
当时的最新文章日期分别为 7 月 20 日、7 月 28 日、6 月 25 日，不能据此声称
10 月仍持续更新。当前云环境对候选 RSS 域名的探测被代理网络政策拒绝，未取得新样本，
所以没有自动晋升为公共默认源。现有程序也明确跳过 `wechat2rss.bestblogs.dev`，
仅拷贝 OPML 不会自动解除这一限制。

公开目录是免费访问入口，不代表 WeChat2RSS 后端永久免费或可自行批量抓取所有公众号。
下一步应在可访问环境做 source-only probe 和 Source Overlap Check，再接入稳定的低重复源。

## 上游源码

用户提供的 `mcncarl/yichen` 当前无法公开 clone；作者个人主页指向实际公开仓库：

- `https://github.com/mcncarl/yichen-skills`
- 批量导出 Skill 位于 `yichen-wechat-mp-batch-exporter/`
- README 和 `references/exporter-workflow.md` 明确依赖 `wechat-article/wechat-article-exporter`
- 已知 URL 的下载脚本默认调用公共 exporter 下载 API，不是完全独立的抓取器

已成功 clone 上游：

- `https://github.com/wechat-article/wechat-article-exporter`，当前读取版本 `152f238`，MIT。
- `https://github.com/wechat-article/wxdown-service`，源码也仍公开可读。

上游 README 明确写明：2026-07-30 停止维护，原因是微信官方关闭了核心接口；
仓库不会删除，保留源码与 issue。公告为
`https://github.com/wechat-article/wechat-article-exporter/issues/200`。
公开 API 已下线；作者称在线域名将于 2026-10-30 到期。

因此，“上游关闭”不能理解为源码全丢失：源码可以保留，但旧的公众号名搜索、
历史列表同步不能因找到 fork 或重新部署代码而自动恢复。

另已取得 `lifayustart/yichen-skills` 的公开镜像，但其内容较旧，不能把镜像存在
当作当前批量同步功能可用的证据。yichen-skills 当前授权限制商业与内部公司部署；
本次没有把其代码复制进本项目。原 exporter 的 MIT 许可与 Skill 的许可应分别核对。

同类公开项目 `https://github.com/rachelos/we-mp-rss` 也有源码，当前读取版本
`9b40351`（2026-10-10）。这是独立实现的调查候选，不是旧接口仍可用的证明；
没有启动服务、登录或操作微信。默认公共站仍应优先采用已验证公开 RSS 和官方网页。
