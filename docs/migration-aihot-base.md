# AI Perspective：完整架构与公开静态站

基于 [KKKKhazix/AIHOT](https://github.com/KKKKhazix/AIHOT) 的 `652bd6bf4190df0030824dd86a982ea96f5623d5`，保留 MIT 许可（`licenses/AIHOT-LICENSE.txt`）。产品使用 AI Perspective 名称与自有标识。原版 React 卡片、时间轴、侧栏、主题切换和分页组件由本机系统和 Pages 阅读器共同使用。

## 两个出口

- 本机：Node 24、PostgreSQL 17、API、worker、后台与 SSR 网页，默认仅监听 `127.0.0.1:3000`。数据库没有对外端口。
- `https://leaifish.github.io/ai-news-radar/`：静态阅读器及公开新闻投影。采用 `#/topics/doubao` 等地址，不需要本机持续联网。旧 `?space=research&kind=org&id=doubao` 链接保留跳转。
- 本机休眠或离线时，公开网页依然能访问，但本机同步会暂停。

保留近30天主题消息、国内/海外分组、20条分页、中文缓存、原文链接、空摘要不显示、免费摘要抓取、48个优先信源，以及旧规则生成的多源合并和日报结果。收藏继续保存在浏览器；不会把收藏上传后台。评分不显示，不把免费规则结果冒充模型评分。

## 在 Mac 启动

请新建独立目录，**不要把含内部 DAU/MAU 的旧本机目录整体复制、提交或作为 Docker 挂载目录**。

```bash
cd /Users/xujunyi1/AI
git clone https://github.com/LeaiFish/ai-news-radar.git ai-perspective-local
cd ai-perspective-local
python3 scripts/init-free-env.py
python3 scripts/export-public-news.py
docker compose up -d --build
```

先安装并启动 Docker Desktop。访问 `http://localhost:3000`，后台在 `/admin`；管理员密码在本机 `.env` 的 `ADMIN_PASSWORD` 行。生成程序不会打印密钥，也不会覆盖已有 `.env`。

`RADAR_FREE_ONLY=1` 在付费请求入口阻断 LLM、向量、Dajiala、SocialData 与 Jina；Compose 固定此开关，并关闭原版模型和采集调度。免费模块在每小时北京时间第10分钟运行原有 Python 流程，写入 `/data/radar-news`，通过原版 material/publication 层导入数据库，再导出公开数据。可手动执行：

```bash
docker compose exec -T worker python3 scripts/free-cycle.py
```

不付费意味着不能保证所有 X/公众号实时更新，也不能保证每条都有中文摘要。优先复用已有中文、源站摘要和免费翻译；无法取得时省略摘要，不编造内容。原版依赖模型的评分、深度研判与自动报告生成保持关闭。

## 只同步公开网页到 GitHub Pages

本机需要 Git 对该公开仓库具有推送权限；先验证本机 Git 登录。发布程序在 `.local/pages-checkout` 使用独立克隆，**不会从当前本机目录执行 `git add .` 或推送数据库**。

```bash
# 先生成本机预览，不上传
python3 scripts/sync-public-site.py
python3 -m http.server 8088 --directory .local/public-preview
# 访问 http://localhost:8088/ai-news-radar/

# 确认后发布（此命令明确执行 Git 推送）
python3 scripts/sync-public-site.py --publish
```

只允许提交 `index.html`、`public-news.json` 与 `assets/public-reader/`。后台、环境变量、数据库备份、原始正文、私有邮件、账号凭据及内部指标均不进入这个出口。公开数据库导出还要求文章带有本流程写入的 `public_import` 标记，并满足未撤回、已公开和近30天条件。远端有更新的快照时，不覆盖为旧数据。

启用 Mac 每小时同步：

```bash
python3 scripts/create-public-sync-launchagent.py
mkdir -p ~/Library/LaunchAgents
cp .local/com.ai-perspective.public-sync.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ai-perspective.public-sync.plist
```

这里只生成/安装公开网页的定时同步；Docker worker 自己负责采集。停止同步用 `launchctl bootout gui/$(id -u)/com.ai-perspective.public-sync`。错误日志在 `.local/`，不会提交。GitHub 原有免费采集工作流保留为备用；其产物也经过同一公开投影导出。

## 验证与边界

迁移在隔离云环境测试，不代表已在你的 Mac 上安装。运行过 PostgreSQL 迁移、公开数据导入、类型检查、SSR/静态构建、浏览器桌面/手机检查和 Docker 全栈页面/接口检查。内部本机文件没有被读取。

`export-public-news.py` 只读固定新闻文件，拒绝私有/内部/指标字段与本地/带凭据URL；`export-public-db.ts` 只读公开投影，不执行 `pg_dump`。Dockerfile 显式列出代码与公开配置，禁止整目录 `COPY . .`。上传前仍应把内部业务工作簿、数据库与新闻项目存放在不同目录。

回退界面可使用 `legacy-radar.html`；数据库卷不会因重建镜像删除。`docker compose down` 保留数据，不要运行带 `-v` 的删除命令，除非确实要删除本机新闻数据库。

## 界面保留（2026-10-13）
公开站和本机默认入口使用上一版 Radar 的侧栏、竞争概览、主题研究、工作台及机构页排版；AIHOT 完整后台仍用于采集、存储和管理。公开页面通过 public-news.json 适配原有界面，不导出数据库或内部数据。
