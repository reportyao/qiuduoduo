# AGENTS.md · 球多多工程协作约定

本文件是 AI 与人类协作开发的**仓库级上下文入口**。任何 AI/开发者在改动代码前必须先读本文件；提交前必须按 Definition of Done 自检。

**H5 预览（2026-11-14）**：`apps/mobile` 已开启 Expo Web，与 App 共用同一套组件；生产预览 http://43.128.24.244:8100/h5/ ，本地 `just mobile-web`，重新导出 `just mobile-web-export`（产物进 `jieqiu-backend/app/static/h5/`）。**H5 只做合并式发布（`just h5-publish`），严禁在服务器 `rm -rf` h5 目录**：浏览器缓存旧 index.html 还引用旧 entry，删了旧 JS 会让缓存用户白屏；服务器滚动保留近 6 代产物（旧 entry 是缓存旧 index.html 用户的回退路径），`deploy.py` 全量部署时滚动保留 h5_prev/h5_prev2 并合回。H5 可用 `?theme=light|dark` 强制主题（仅 web 预览核对用，App 端跟随系统不受影响）。后端对缺失的资源（js/css 等）返回 404 而不是回退 index.html（回退会被浏览器当 JS 模块加载 → MIME 失败 → 白屏）；`_expo/` 与 `assets/` 下产物 immutable 长缓存，index.html no-cache。H5 只做内部预览，不替代原生推送/安装包能力。

当前事实（2026-11-14）：生产代码仍在 `jieqiu-backend/`，OpenAPI **162 路径 / 178 方法**，后端 **375 tests**，前端 **64 tests**，Alembic head `20261113_26`；生产数据库目标是境内 PostgreSQL 16（**云托管优先 / 自建兜底**，ADR-0004），未设置 `JQ_PROD_DATABASE_URL` 时仍是旧 SQLite。v4.1 已部署腾讯云生产（2026-11-12 11:38 CST，管理后台静态资源 v=20261113b）；17:00 CST 追加 Sportmonks 情报层（首发/阵型/伤停/积分榜/H2H/天气/裁判/25 维预测/选定市场，Alembic `20261112_24`）。2026-11-13 UI 完成 unSlop 整站重构（字号、间距、预测可视化、市场卡片）；新增比赛中心：即时/赛果/预测战绩三 Tab，赛前预测快照锁定、赛后 25 维逐条对照（Alembic `20261113_26`）。2026-11-14 全站 UX 五轮整改落地（commit `434b94c`）：ErrorBoundary/触控目标/a11y/下拉刷新/焦点保持/触觉反馈/NetInfo 离线横幅/证据链多选/预测分组全展/暗色模式（tokens 按 `Appearance.getColorScheme()` 启动时选定，运行中切换需重启；新增原生依赖 `@react-native-community/netinfo@11.4.1`，版本对齐 Expo）。**同日色彩语义全面改版（commit `dfea7dc`，复查整改 `4860234`/`c018dec`，最新 APK tag `apk-20261114-redblack2` 构建成功）：红 brand=中/命中/通过/盈利/品牌主行动（"红中"心智，hero 深红黑渐变+金 accent）；黑 loss=不中/回避/亏损/砍错/连败/高风险（暗色灰化表示负向）；琥珀 amber=等数据/走水/离线/会员金；红 danger=删除/退出/表单错误/系统错误（破坏性与品牌同族、场景隔离）。token 重命名 green→brand、danger 保留并新增 loss 族；tone key green→positive、danger→negative；暗色底绿黑→暖炭 `#171210`；对比度脚本 32 组关键对全部 ≥4.5。**后端同日改动：`app/main.py` 的 `/h5/*` 路由对缺失的 js/css 等资源返回真 404（回退 index.html 会让缓存页面拿 HTML 当 JS 模块加载 → MIME 失败白屏）、`_expo/` 与 `assets/` 哈希产物 immutable 长缓存、index.html no-cache；`deploy.py` 打包跳过 `app/static/h5` 并在部署时滚动保留 `h5_prev/h5_prev2` 两代合回（防全量部署抹掉旧 entry 造成缓存用户白屏）。**管理后台同日 OPC 补全（commit `271ff27`，静态资源 v=20261113b→20261114a）：** OPC 生产者补全——`settle_open_cycles`/`membership_expire`/`seed_daily` 接入 `ops_jobs`+`ops_exception`（此前仅 `settle_pending` 有记录）；`/api/ops-v4` 新增 `summary`（按 job_key 聚合最近 200 次运行：最近状态/耗时/失败数）；`/api/app-users` 新增合规巡检字段（`age_verified`/`under18_locked`/`self_exclusion_*`/`discipline_on`/`rested_until`/今日分析额度，与前端 我的·合规 能力对齐）；异常队列页新增「任务健康汇总」卡、用户表新增「合规/额度」列。**同日工作台并入 OPC（commit `c39731e`）：`build_workbench` 新增 ops 阶段（seed_daily/settle_pending/settle_open_cycles/membership_expire 健康汇总 + 未处理异常，核心任务失败或 sev≥3 异常 → blocked，管理员首屏一眼定生死）；`run_action` 全部一键动作接入 `ops_jobs`（业务失败 error+sev2、崩溃 sev3，每个按钮可追溯）；diagnose 上下文带 ops 摘要。**同日数据接口深挖（commit `d96ffd8`，后端 375 tests）：先进球队判定（board `first_side`，TEAM_TO_SCORE_FIRST 25 维对照）与 `parse_result` 比分提取同类过滤/覆盖修复——点球(16)/乌龙(15)计入进球、开纪录方按累计比分推导、FT 行缺失时 1ST+2ND 求和；生产 14/14 场 postmatch 重同步，事件不全场次 5/11→0/14。**正式签名/上架未做。文档索引见 [docs/README.md](./docs/README.md)。

## 1. 架构地图

```text
apps/
  mobile/        Expo React Native + TypeScript（Android 先发，iOS 后补；交接见 apps/mobile/ARCHITECTURE.md）
  web/           Next.js 落地页 / 公开账本 / 分享页（规划中）
  admin/         管理后台（规划中；当前实现是 jieqiu-backend/app/routers/admin_api.py + app/static/admin/）
packages/
  api-client/    OpenAPI 生成的 TS client，禁止手写接口类型
  ui/            设计 tokens / 基础组件（规划中）
  i18n/          文案目录 + 类型化 key（规划中）
  config/        ESLint / TS / 共享配置（规划中）
services/
  api/           FastAPI 模块化单体（自 jieqiu-backend 迁移目标；当前旧目录仍可用）
```

v4.1 新增入口：

```text
apps/mobile/app/(tabs)/plans.tsx        计划 Tab
apps/mobile/app/plans/[id].tsx          计划详情（Max 完整 legs）
apps/mobile/app/membership.tsx          会员权益（充值假 UI）
apps/mobile/src/features/plans/         计划/会员查询
jieqiu-backend/app/features/plans/      计划 API
jieqiu-backend/app/features/v4_router.py  engine/membership/record/profile API
jieqiu-backend/app/modules/plan_service.py
jieqiu-backend/app/modules/settlement.py
jieqiu-backend/app/modules/membership.py
jieqiu-backend/app/modules/performance.py
jieqiu-backend/app/modules/assistant_copy.py
jieqiu-backend/app/modules/ops.py
```

比赛中心（2026-11-13）：

```text
apps/mobile/app/(tabs)/matches.tsx              即时/赛果/预测战绩
apps/mobile/app/predictions/[id].tsx            单场 25 维预测 vs 实际
apps/mobile/src/features/matches/               查询/卡片/标签
jieqiu-backend/app/features/board/              live state、预测快照、结算
jieqiu-backend/app/sportmonks_cli.py            live/freeze/enrich/settle/board 命令
jieqiu-backend/migrations/versions/20261113_25_match_board.py
jieqiu-backend/migrations/versions/20261113_26_product_top_pick.py
```

当前过渡期保留：

```text
jieqiu-backend/  旧后端目录（生产部署仍使用）
archive/legacy/jieqiu-app/      临时展示 UI（只作设计参考，禁止继续加功能）
```

## 2. 一键命令

优先使用 `just`；没有 just 时可按 `justfile` 里的等价命令执行。

```bash
just --list
just api-test
just api-run
just db-up
just db-migrate
just mobile-install
just mobile-start
just mobile-android
just api-client-generate
```

## 3. 编码约定

### 后端（Python / FastAPI）

- 使用 Python 3.12+、FastAPI、SQLAlchemy 2.x、Pydantic v2、Alembic。
- 业务按 **feature slice** 组织：

```text
app/features/<feature>/
  router.py       只做 HTTP 参数校验和响应
  service.py      业务规则
  repository.py   数据访问
  schemas.py      Pydantic
  models.py       该域的 ORM 表（逐步迁移）
  tests/
```

- 共享能力目标放 `app/core/`：DB、配置、认证、安全、事件、审计；当前过渡期仍在 `app/modules/` 与 `app/db.py`，新代码不要继续扩大全局模块。
- `router.py` 不写业务逻辑；`service.py` 不直接拼 SQL；`repository.py` 不做业务规则。
- 新增/修改接口必须有 `response_model` 和明确的 HTTPException；存量老端点仍有 dict 返回，补契约时不要一次改爆移动端。
- 禁止在生产代码里用 `print`；用 logging。
- 禁止裸 `except:`；必须记录错误或转换为领域异常。
- 数据库变更使用 Alembic，不用 `create_all` 更新已有生产库。

### 前端（Expo / React Native / TypeScript）

- 使用 TypeScript strict。
- 页面路由只做薄壳，业务放 `features/<feature>/`。
- 服务端状态用 TanStack Query；本地 UI 状态用 Zustand 或 `useState`。
- 接口类型来自 `packages/api-client`，禁止手写接口类型。
- 单文件 < 300 行，组件 < 150 行。
- 文案必须走 `packages/i18n`，禁止硬编码中文/英文/货币/赔率术语。
- 图标使用 `react-native-svg` 线性图标，不使用 emoji 表达核心状态。
- 触控目标 ≥ 44pt；列表使用 FlashList；动画使用 Reanimated。
- 仓库 `.npmrc` 固定 `node-linker=hoisted`；Windows 下 pnpm 严格布局会让 Hermes 编译器路径过长而失败，不要改回 isolated。
- 构建前必须跑 `expo export`（Metro + Hermes）；typecheck 通过不代表 bundle 能出包。

## 4. 数据与契约

- OpenAPI 是唯一接口事实源；后端代码导出 `packages/api-client/openapi.json` 快照，client 从快照离线生成；禁止对着可能过期的本地服务生成。
- Postgres 是生产事实源（云托管优先 / 自建兜底，非 Supabase，ADR-0004）；SQLite 只允许用于纯单元测试或本地工具；架构/索引/备份见 `docs/database-architecture.md`。
- Alembic 管理迁移；迁移必须可 up/down；生产禁止 `create_all`。
- 领域事件必须有 `dedupe_key`、`payload_hash`、`data_cutoff`。
- 推送/通知文案保持中性，不得出现“买 / 注 / 赔率 / 推荐 / 稳赚”。

## 5. Definition of Done

一个功能合并前必须满足：

1. 代码符合本文件的目录与分层；
2. 新增/修改接口有 OpenAPI 文档和测试；
3. 数据库有 Alembic migration；
4. 单测/集成测试通过；
5. lint/typecheck/test 全绿；
6. 影响部署/配置时更新文档；
7. 有回滚方式；
8. 不引入新的敏感数据落盘。

## 6. AI 协作规则

- AI 改动前先读目标 feature 的 `README.md` 和相关测试。
- AI 一次只处理一个 feature；跨 feature 只允许通过 service 接口或领域事件。
- AI 不得直接修改生成文件 `packages/api-client/src/schema.d.ts`。
- AI 不得重写认证、支付、封存链、合规扫描，除非有明确任务和安全 review。
- AI 不得引入新的数据库方言分支。
- AI 不得把业务逻辑放进 router 或 UI 组件。
- AI 提交前必须运行 `just api-test` 和相关前端测试。

## 7. 产品内容规则（2026-11-13 修订）

- 允许经审核的赛前预测、参考组合、参考预算；不承诺收益。
- 公开文案明确使用“预测方向/预测概率/置信度”；不得使用“精准预测/必中/稳赚”，付费详情必须写明方向、条件、失效条件与成本。
- 推荐观点与组合必须经 `decision_snapshots` / `recommendation_plans` → `review_runs`（L1 规则/事实、L2 数字、L3 人设、L4 对抗、L5 发布门）→ `published` 后才能作为正式内容；Today Hero 只读 `/recommendations/today` 的 published。`/tools/parlay/plan` 仍是**preview**，UI 必须标注“参考·未复核”，不得进入付费区。
- **比赛中心**：比赛 Tab 只做即时/赛果/预测战绩三块；即时只展示有竞彩映射的进行中场次，即时与赛果都不返回预测字段；预测战绩展示全部 25 维预测 vs 实际。命中率按“预测条目”统计，只计主流玩法（主预测、当前盘口大小球、BTTS），角球/半全场等只对照不计入。大小球必须按竞彩实际盘口匹配，不固定 2.5。所有用户都能看预测结果。
- **预测历史不可补造**：只认开球前锁定的 `sportmonks_prediction_snapshots`；覆盖更新表不作为历史事实，没有赛前快照就不生成战绩。
- **主预测口径**：预测战绩列表的主预测展示模型三方向最高概率；`verdict.pick` 的 EV 方向保留为内部/下注口径，不拿低概率 EV 方向冒充“推荐”。预测战绩详情页返回每条预测的完整概率分布。
- **静默排序**：关注/看过/问过的比赛只影响排序，不在 UI 打“看过/问过”标签；赛果与预测战绩按比赛时间倒序分组，个性化组在前。
- **AI 计划是 4 场模拟定投，不是跟单**：每期最多 4 场、每场 100、预算 400；不做 `plan_follows`、不自动记注、不代购、不托管资金；文案必须写“模拟方案/模拟收益”。
- **计划分级**：免费/Pro 只能看历史摘要与锁定态，Max 才能看完整 bets/legs；Pro 文案不得暗示含 AI 计划。
- **会员**：权益、额度、计划门控、后台手动开通是真实能力；充值/支付 UI 是假的，不得创建订单、不得伪造支付成功。会员只能由 `/admin` 手动开通/撤销。
- **计划与战绩数字**：收益按 `risk_level` 分开，不把三套相加；只算已结算注单；void 不计赢/输；没有数据返回空态，不补假数字。
- **多盘口边界**：HeaderMetrics 的“5 盘口/7 模型”是配置展示；大小球/BTTS/半全场未完整入库时，不得在计划或付费区宣称已可用。
- 推送/锁屏只写“今日预测已更新”等中性提示，不写具体赔率、投注或赛事结果；计划提醒不做跟单。
- 保留年龄确认、自排除、连败保护作为支付/上架合规能力，不是内容禁区。
- 不收集未成年人数据；不向第三方上传用户原始下注数据。

## 8. 目录迁移说明

- 新代码不要加到 `archive/legacy/jieqiu-app/index.html`；
- 新后端代码优先进入 `app/features/<feature>`；
- `jieqiu-backend/` 到 `services/api/` 的目录迁移将在 Alembic/Postgres 切换后执行，避免一次性大迁移。
- W8 冻结基线不是永久常量：新增路由后必须用控制台登录调用 `POST /review/freeze/adopt` 重新采纳，否则 `/review/freeze` 会报新增违规。
- 认证默认 fail-closed：`JQ_ENV=dev|test` 才允许 `JQ_AUTH_STUB=true`；staging/prod 必须配置真实短信/邮件/OAuth。
