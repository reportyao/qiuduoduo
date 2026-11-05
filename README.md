# 球多多 Monorepo

有判断、有参考组合的赛前决策助手。**Decision Snapshot → AI Review → Publish 主链已接**，`/admin` 运营台已上线，合规（年龄门/未成年锁定/自排除）服务端闭环已落地，不承诺结果。

- 仓库：https://github.com/reportyao/qiuduoduo （公开）
- 生产前端：`apps/mobile/`（Expo React Native，Android 先发，iOS 后补）
- 生产后端：`jieqiu-backend/`（FastAPI 模块化单体，过渡期目录，迁移目标 `services/api/`）
- 接口契约：`packages/api-client/`（OpenAPI 快照 + 生成 TS client，禁止手写接口类型）
- 数据底座：`sp-collector/`（竞彩官方 SP 自采，家宽出口）
- 当前线上：`43.128.24.244:8100`，代码提交 `dd4555b`（2026-11-05 部署）
- 仓库最新：`3c70bbc`（2026-11-06；后端修复待部署，Android 包已更新到 `apk-20261106-8`）

| 事实 | 当前值（2026-11-06） |
|---|---|
| 版本 | `0.8.0-w8+assistant` |
| OpenAPI | 128 路径 / 143 方法 |
| 后端测试 | 271 passed |
| 前端测试 | 30 passed + typecheck / ESLint / Android Hermes bundle |
| 生产数据库 | **当前 SQLite + WAL（过渡，单写者）**；目标境内 PostgreSQL 16（云托管优先 / 自建兜底，ADR-0004） |
| Alembic head | `20261105_13`（CLV 收盘价字段；升级/降级已验证） |
| W8 冻结基线 | 145 路由（新增路由后须重新采纳） |
| 线上提交 | `dd4555b`（2026-11-05；仓库最新 `3c70bbc` 待部署） |

工程入口见 [AGENTS.md](./AGENTS.md)，完整文档索引见 [docs/README.md](./docs/README.md)，运维手册见 [docs/operations-runbook.md](./docs/operations-runbook.md)。

## 当前运行状态（2026-11-06）

- **API/后台**：`/health` 正常，封存链 OK；`/admin` 运营台可用。
- **推荐内容**：主链 build → L1–L5 复核 → publish 已跑通；但 **当前生产 `/recommendations/today` 为空**——raw 复核有 1 场“复核过三关”，尚未产出 published snapshot/plan。前端已按 published 门控，不把未发布判决当推荐；发布链仍需在 `/admin` 查 `review_runs` 失败层。
- **数据供给**：国际盘已配置，市闸/模型闸按各自阈值工作；模型闸仍有大量 `pending_data`，覆盖率提升依赖更好的当前赛季数据。
- **API-Football 已配置**：生产使用 API-Sports `apisports` Free 档（100 次/日、10 次/分钟）。已支持当天+次日 fixtures、已链接场次的线阵容/伤停；后台按“今日/明日”分开展示链接数；当日目标场次已全部链接，次日赛程在每日 06:15 同步。当前赛季积分榜被 Free 档限制，需付费档；lineups 通常在停售前才发布，由每小时 `sync-enrich` 补充。
- **已知待接**：JPush 真机推送客户端与厂商凭证；`dry-run` 和站内信不受影响。

## 最近完成（2026-11-06）

1. **概率经验区间**：`calibration.interval` 用已结算 promoted 判决的残差分布生成 `prob_low/prob_high`；样本 <20 返回 `accumulating`，绝不编造区间。
2. **CLV 闭环**：结算时锁定停售前最后一条同池 SP，写 `closing_sp_*`/`closing_at`/`clv`；周报汇总平均 CLV 与正 CLV 占比。
3. **未采纳复盘**：`/stream` 的 `unattended` 返回“看过但没记注”的已结算场次，移动端独立卡片展示，只复盘不追损。
4. **赛前提醒**：worker 增加 T-3h / T-30m 扫描、去重、中性文案和扇出事件。
5. **部署加固**：`deploy.py` 合并远端 `/etc/jieqiu-backend.env` 与 `cron.env` 的可选 key，覆盖 `cron.env` 前自动备份最近 5 份。
6. **移动端深度测试**：修复悬浮头像遮挡、详情原始 ISO 时间、覆盖面板“偏旧/缺”混淆、已砍场次误显示为在售、账本发布状态、周报空态、自排除服务端补同步、深链 `jieqiu://today`、助理发布门等；详见 [docs/frontend-deep-test-2026-11-06.md](./docs/frontend-deep-test-2026-11-06.md)。
7. **Android 内部测试包**：`apk-20261106-8`，版本 `0.1.1`，包名 `com.qiuduoduo.app`。

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
| 管理后台 | `/admin`：总览/模型池/用量/人设/推荐主链（逐条+批量+plan 操作+撤回理由）/组合/数据/运维/账号/审计/日志；RBAC + CSRF + 会话撤销 + 审计 |
| 认证 | 设备令牌 + CN 手机号/微信、GL Email/Google/Apple；JWT 轮换 + refresh 复用检测；生产 fail-closed |
| 封存与信任 | 判决哈希封存链、公开账本、分享编号可验（`/s/{id}`）、周报/复盘 |
| 推送骨架 | 事件监控（含赛前 T-3h/T-30m）→ 扇出 → 站内信/推送（JPush 未配置时 dry-run）；通知设置/收件箱/关注已通；真实 JPush 客户端待接 |
| 人设语气 | 三套 profile + 槽位 + 模型池（Key 加密/failover/缓存/预生成）；后台可改 |
| LLM Gateway | Phase 1：登录用户 `open_chat → fast`，预算/缓存/PII 脱敏/用量账本；匿名 0 LLM |
| API-Football | API-Sports Free：fixtures 当天/次日、lineups、injuries、自动/人工链接；7 秒节流 + 90/日预算。**当前赛季 standings 被 Free 档拒绝**；apifootball.com 是另一家 provider，未接入 |

### 待做（外部依赖或下一阶段）

- **API-Football 当前赛季 standings**：Free 档不支持 2026 赛季积分榜；若需要完整 focus 覆盖，升级 API-Sports 付费档（或另接 standings provider）。
- **JPush 真机推送**：客户端 token 注册、通知权限软请求、点击深链、厂商凭证。
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
just api-test             # pytest（271 tests）

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