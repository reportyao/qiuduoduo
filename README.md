# 球多多 Monorepo

有赛前预测、概率区间和参考组合的决策助手。**Decision Snapshot → AI Review → Publish 主链已接**，`/admin` 运营台已上线，合规（年龄门/未成年锁定/自排除）服务端闭环已落地，不承诺结果。

- 仓库：https://github.com/reportyao/qiuduoduo （公开）
- 生产前端：`apps/mobile/`（Expo React Native，Android 先发，iOS 后补）
- 生产后端：`jieqiu-backend/`（FastAPI 模块化单体，过渡期目录，迁移目标 `services/api/`）
- 接口契约：`packages/api-client/`（OpenAPI 快照 + 生成 TS client，禁止手写接口类型）
- 数据底座：`sp-collector/`（竞彩官方 SP 自采，家宽出口）
- 当前线上：`43.128.24.244:8100`，代码提交 `dd4555b`（2026-11-05 部署）
- 仓库最新：2026-11-06 JPush 客户端接入（后端修复待部署，真机包 `apk-20261106-21`）
- Android 测试包：https://github.com/reportyao/qiuduoduo/releases/tag/apk-20261106-21

| 事实 | 当前值（2026-11-06） |
|---|---|
| 版本 | `0.8.0-w8+assistant` |
| OpenAPI | 131 路径 / 146 方法 |
| 后端测试 | 271 passed |
| 前端测试 | 30 passed + typecheck / ESLint / Android Hermes bundle；APK 18 已含 JPush 原生库 |
| 生产数据库 | **当前 SQLite + WAL（过渡，单写者）**；目标境内 PostgreSQL 16（云托管优先 / 自建兜底，ADR-0004） |
| Alembic head | `20261106_14`（后台 LLM 能力配置；升级/降级已验证） |
| W8 冻结基线 | 145 路由（新增路由后须重新采纳） |
| 线上提交 | `dd4555b`（2026-11-05；仓库最新预测改版待部署） |

工程入口见 [AGENTS.md](./AGENTS.md)，完整文档索引见 [docs/README.md](./docs/README.md)，运维手册见 [docs/operations-runbook.md](./docs/operations-runbook.md)。

## 当前运行状态（2026-11-06）

- **API/后台**：`/health` 正常，封存链 OK；`/admin` 运营台可用。
- **推荐内容**：主链 build → L1–L5 复核 → publish 已跑通；但 **当前生产 `/recommendations/today` 为空**——raw 复核有 1 场“复核过三关”，尚未产出 published snapshot/plan。前端已按 published 门控，不把未发布判决当推荐；发布链仍需在 `/admin` 查 `review_runs` 失败层。
- **数据供给**：国际盘已配置，市闸/模型闸按各自阈值工作；模型闸仍有大量 `pending_data`，覆盖率提升依赖更好的当前赛季数据。
- **API-Football 已配置**：生产使用 API-Sports `apisports` Free 档（100 次/日、10 次/分钟）。已支持当天+次日 fixtures、已链接场次的线阵容/伤停；后台按“今日/明日”分开展示链接数；当日目标场次已全部链接，次日赛程在每日 06:15 同步。当前赛季积分榜被 Free 档限制，需付费档；lineups 通常在停售前才发布，由每小时 `sync-enrich` 补充。
- **JPush**：Android 客户端已接入 core SDK（`JCommonService` 已补，registration id 上报、连接状态、通知权限、设备推送状态）。模拟器实测能拿到 registration id 且 `connected=true`，但 MuMu/Houdini 的 arm64 转译会在 RN 启动阶段被 JCore 原生库带崩；**需真机（arm64）复测可用性**。厂商通道与 Master Secret 待配置，服务端目前仍可能 dry-run。详见 [docs/jpush.md](./docs/jpush.md)。

## 最近完成（2026-11-06）

1. **概率经验区间**：`calibration.interval` 用已结算 promoted 判决的残差分布生成 `prob_low/prob_high`；样本 <20 返回 `accumulating`，绝不编造区间。
2. **CLV 闭环**：结算时锁定停售前最后一条同池 SP，写 `closing_sp_*`/`closing_at`/`clv`；周报汇总平均 CLV 与正 CLV 占比。
3. **未采纳复盘**：`/stream` 的 `unattended` 返回“看过但没记注”的已结算场次，移动端独立卡片展示，只复盘不追损。
4. **赛前提醒**：worker 增加 T-3h / T-30m 扫描、去重、中性文案和扇出事件。
5. **部署加固**：`deploy.py` 合并远端 `/etc/jieqiu-backend.env` 与 `cron.env` 的可选 key，覆盖 `cron.env` 前自动备份最近 5 份。
6. **移动端深度测试**：修复悬浮头像遮挡、详情原始 ISO 时间、覆盖面板“偏旧/缺”混淆、已砍场次误显示为在售、账本发布状态、周报空态、自排除服务端补同步、深链 `jieqiu://today`、助理发布门等；详见 [docs/frontend-deep-test-2026-11-06.md](./docs/frontend-deep-test-2026-11-06.md)。
7. **Android 内部测试包**：`apk-20261106-21`，版本 `0.3.2`（versionCode 7），包名 `com.qiuduoduo.app`，含 JPush 6.3.0 core 与 `JCommonService`，已移除定位/电话/外部存储权限；[Release](https://github.com/reportyao/qiuduoduo/releases/tag/apk-20261106-21) · SHA256 `4b39dec5036c51735ef9f91d90c174141537c9d07dd3c5ad50489da00ec6ce88`。
8. **预测优先前端改版**：取消“不预测”底线，首页 Tab 改为“预测”，重写首页/详情/助理/工具/账本/周报/设置文案与信息层级；详见 [docs/prediction-first-frontend-2026-11-06.md](./docs/prediction-first-frontend-2026-11-06.md)。
9. **Unslop 逐页 UI 精修**：收敛页面节奏、卡片圆角与内边距、字重/对比度、图标颜色和无意义动效；工具页改为“主工具 + 分组列表”；复核轮又降低永久自排除按钮权重、删除隐私页重复返回、拆分登录法律文案、预览卡改中性。详见 [docs/ui-unslop-2026-11-06.md](./docs/ui-unslop-2026-11-06.md)。
10. **JPush Android 接入**：JPush 6.3.0 + JCore 5.6.0 core、`JCommonService`、registration id 上报、通知权限与“设备推送”状态；模拟器已拿到 `registration_id` 与 `connected=true`，但 MuMu/Houdini 转译会在 RN 启动阶段崩溃，需真机复测。厂商通道可后补。详见 [docs/jpush.md](./docs/jpush.md)。
11. **后台接入中心**：`/admin` 按“用途”重排 AI 能力（对话问答/发布前复核/人设文案/单场分析）、数据源与推送通道；fast/deep 支持后台直接上传 Base URL、Model、Key，加密存 `llm_profiles` 并优先于环境变量；新增迁移 `20261106_14`。详见 [docs/llm-gateway.md](./docs/llm-gateway.md)。

## 功能完成度

### 已实现

| 模块 | 现状 |
|---|---|
| 推荐主链 | `decision_snapshots` + `recommendation_plans` + `review_runs` + `recommendation_events`；build → L1–L5 复核 → publish → expire/withdraw；`GET /recommendations/today` 只返回 published |
| 公开推荐契约 | snapshot/plan 返回方向、把握度、成立条件、失效条件、AI 复核徽章（状态/复核人/时间/各层结果）；Today Hero 与组合卡已消费 |
| 概率经验区间 | `calibration.interval` 用已结算 promoted 判决的残差经验分布给 `prob_low/prob_high`；样本 <20 标 `accumulating`，不编造区间；移动端已展示 |
| 赛后归因 / CLV | 结算时锁定停售前最后一条同池 SP，写 `closing_sp_*`/`closing_at`/`clv`；周报展示平均 CLV 与正 CLV 占比；移动端展示“看完未跟”的未采纳复盘 |
| 首页聚焦 | 选中比赛 → 回首页聚焦；`/matches/{id}/focus` 覆盖率/事实/未知项/可用动作真实接入 |
| 数据脉搏 | `/stats/pulse` 真实计数 + 展示系数；首页指标与数据状态页已接，不再前端拼数 |
| 在售与选择器 | `coverage` 覆盖分、"覆盖足"筛选、promoted → 覆盖 → 停售排序 |
| 互动埋点 | `POST /interactions` 白名单幂等；前端 `focus_select` / `action_click` / `free_text_send` / `pulse_open` 已上报 |
| 合规闭环 | `/gate/verify`、`/me/under18-lock`、`/compliance/state` · `/compliance/self-exclusion` · `/compliance/self-assessment`；`POST /bets` 与 focus capabilities 服务端硬拦截未成年/自排除/休息中；移动端启动回填服务端状态 |
| 串关体检 | `POST /tools/parlay/check` 四维体检（成本/信息/模型/结构），缺模型不伪造组合概率 |
| 管理后台 | `/admin`：总览/接入中心/调用用量/文案模型池/人设文案/推荐主链（逐条+批量+plan 操作+撤回理由）/组合/数据/运维/账号/审计/日志；RBAC + CSRF + 会话撤销 + 审计 |
| 认证 | 设备令牌 + CN 手机号/微信、GL Email/Google/Apple；JWT 轮换 + refresh 复用检测；生产 fail-closed |
| 封存与信任 | 判决哈希封存链、公开账本、分享编号可验（`/s/{id}`）、周报/复盘 |
| 推送 | 事件监控（含赛前 T-3h/T-30m）→ 扇出 → 站内信/推送；通知设置/收件箱/关注已通；JPush Android core 已接（registration id/连接状态），Master Secret 未配置时 dry-run；厂商通道待补 |
| 人设语气 | 三套 profile + 槽位 + 模型池（Key 加密/failover/缓存/预生成）；后台可改 |
| LLM Gateway | Phase 1：登录用户 `open_chat → fast`，预算/缓存/PII 脱敏/用量账本；匿名 0 LLM |
| API-Football | API-Sports Free：fixtures 当天/次日、lineups、injuries、自动/人工链接；7 秒节流 + 90/日预算。**当前赛季 standings 被 Free 档拒绝**；apifootball.com 是另一家 provider，未接入 |

### 待做（外部依赖或下一阶段）

- **API-Football 当前赛季 standings**：Free 档不支持 2026 赛季积分榜；若需要完整 focus 覆盖，升级 API-Sports 付费档（或另接 standings provider）。
- **JPush 真机验收**：在 arm64 真机确认启动不崩、registration id 上报、通知展示/点击深链；再配 Master Secret 与厂商凭证。模拟器（MuMu/Houdini）已确认会被 JCore 原生库带崩，不能作为验收环境。
- **支付/订阅权益**：`subscriptions/entitlements`、RevenueCat/微信商户号、免费 1 条/其余锁定。
- **备份/PITR**：云控制台自动备份或自建 `pg_backup.sh` + WAL 归档 + 恢复演练（上线阻塞项）。
- **当前赛季 xG**：API-Football 不提供 xG；当前仍是静态历史 xG + 进球代理。选型见 [docs/xg-providers.md](./docs/xg-providers.md)，优先 Sportmonks，回测可用 StatsBomb/FBref。
- **真实 live feed / 进球提醒**：`/matches/{id}/live` 目前基于已同步赛果与 SP 快照。
- **推荐三套人设文案**：`recommendation_copies` 表、按 persona 生成、L3 逐套复核。
- **持久化告警/任务中心**：ack/静默/外发 webhook、任务 last-run。
- **Vision OCR**（v1.5）、**编辑台变体池**（v1.5）、**多 worker 会话**（Redis/DB）。

详见 [docs/recommendation-product.md](./docs/recommendation-product.md)、[docs/focused-decision-flow.md](./docs/focused-decision-flow.md)、[docs/llm-gateway.md](./docs/llm-gateway.md)。

## 快速开始

优先使用 `just`（`just --list` 查看全部命令）；没有 just 时按 `justfile` 等价命令执行。

```bash
# 后端
just api-install          # pip install -r jieqiu-backend/requirements.txt
just db-up                # 本地 Postgres（docker compose，端口 5433）
just db-migrate           # alembic upgrade head
just api-run              # uvicorn app.main:app --port 8100
just api-test             # pytest（278 tests）

# 前端（Node 22 自带 corepack；仓库 .npmrc 固定 node-linker=hoisted）
just install              # corepack pnpm install
just api-client-generate  # 从后端导出 OpenAPI 快照并重新生成 client
just mobile-start         # expo start
just mobile-android       # expo run:android

# 契约变更后必须重新生成 client，禁止对着可能过期的本地服务生成
just api-openapi
```

部署到 VPS：

```bash
cd jieqiu-backend
export JQ_DEPLOY_PASSWORD='...'          # 必填
export JQ_ADMIN_PASSWORD='...'           # 仅首次建管理员需要；后续会保留远端值
export JQ_API_FOOTBALL_PROVIDER='rapidapi'   # 用 RapidAPI key 时；API-Sports 直连用 apisports
export JQ_API_FOOTBALL_KEY='...'
export JQ_ODDS_API_KEY='...'
python deploy.py
```

`deploy.py` 会合并远端 `/etc/jieqiu-backend.env` 与 `cron.env` 中已有的可选 key，覆盖 `cron.env` 前自动备份，避免未导出的 key 被清空。细节见 [docs/operations-runbook.md](./docs/operations-runbook.md)。

## 目录结构

```text
apps/
  mobile/        Expo RN + TS 生产前端（Android 先发）
  web/           落地页/公开账本/分享页（规划中）
  admin/         独立管理后台（规划中；当前实现在后端同进程 /admin）
packages/
  api-client/    OpenAPI 快照 + 生成的 TS client
  ui/ i18n/ config/   规划中
services/
  api/           FastAPI 迁移目标（当前旧目录 jieqiu-backend 仍可用）
jieqiu-backend/  生产后端（过渡期）
jieqiu-app/      临时展示 UI（只作设计参考，禁止加功能）
sp-collector/    竞彩 SP 采集器（家宽出口）
docs/            架构/产品/运维/审查文档
```

---

# 竞彩 SP 采集器 v0.1

**采集内容**：体彩官网在售竞彩场次 + SP 赔率（had/hhad 双池 + 让球线 + 单关标记），每 5 分钟一张快照存 SQLite。

**为什么存在**：竞彩无商业数据 API，官方 SP 时间序列必须自采。它是三件东西的数据底座——数②③重测、判决卡实时 SP、竞彩滞后验证（商业模式核心假设）。

## 运行

```bash
export JQ_COLLECTOR_PASSWORD='...'   # SFTP 备份密码；不再写进代码
# 可选：JQ_COLLECTOR_HOST / JQ_COLLECTOR_USER
python collector.py        # 前台
# 当前已以分离进程常驻运行（日志 collector.log）
```

- 出口：**必须家宽**（体彩 WAF 拒机房 IP，服务器直连 567）
- 备份：每 30 分钟 SFTP 推送到 43.128.24.244:/home/ubuntu/jieqiu-sp/
- 容错：连续失败 20 次自动退出（人工重启）；单轮失败只计数不中断

## 表结构

- `matches`: match_no/match_id/league/home/away/kickoff/single_flag
- `sp_snapshots`: match_id/pool/goal_line/sp_h/sp_d/sp_a/captured_at（只追加）

## 已知限制与升级路径

| 限制 | 对策（W2 内定） |
|---|---|
| 依赖本机开机+家宽 | ① 4G 迷你主机 ② 住宅代理+云机 ③ 与常开设备共存 |
| 5min 固定轮询 | 后续：停售前 60min 加密至 60s（尚未实现） |
| 无赛果回填 | 赛果由后端 `sync_results_football_data` 回填，不由采集器写 `settled` |