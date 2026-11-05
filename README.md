# 球多多 Monorepo

有判断、有参考组合的赛前决策助手。**Decision Snapshot → AI Review → Publish 主链已接**，`/admin` 运营台已上线，合规（年龄门/未成年锁定/自排除）服务端闭环已落地，不承诺结果。

- 仓库：https://github.com/reportyao/qiuduoduo （私有）
- 生产前端：`apps/mobile/`（Expo React Native，Android 先发，iOS 后补）
- 生产后端：`jieqiu-backend/`（FastAPI 模块化单体，过渡期目录，迁移目标 `services/api/`）
- 接口契约：`packages/api-client/`（OpenAPI 快照 + 生成 TS client，禁止手写接口类型）
- 数据底座：`sp-collector/`（竞彩官方 SP 自采，家宽出口）

| 事实 | 当前值（2026-11-05） |
|---|---|
| 版本 | `0.8.0-w8+assistant` |
| OpenAPI | 128 路径 / 143 方法 |
| 后端测试 | 256 passed |
| 前端测试 | 22 passed + typecheck / ESLint / Android Hermes bundle |
| 数据库 | 境内 PostgreSQL 16（云托管优先 / 自建兜底，ADR-0004）；未设置 `JQ_PROD_DATABASE_URL` 时仍是旧 SQLite |
| Alembic head | `20261105_12` |
| W8 冻结基线 | 145 路由（新增路由后须重新采纳） |

工程入口见 [AGENTS.md](./AGENTS.md)，完整文档索引见 [docs/README.md](./docs/README.md)，运维手册见 [docs/operations-runbook.md](./docs/operations-runbook.md)。

## 功能完成度

### 已实现

| 模块 | 现状 |
|---|---|
| 推荐主链 | `decision_snapshots` + `recommendation_plans` + `review_runs` + `recommendation_events`；build → L1–L5 复核 → publish → expire/withdraw；`GET /recommendations/today` 只返回 published |
| 公开推荐契约 | snapshot/plan 返回方向、把握度、成立条件、失效条件、AI 复核徽章（状态/复核人/时间/各层结果）；Today Hero 与组合卡已消费 |
| 首页聚焦 | 选中比赛 → 回首页聚焦；`/matches/{id}/focus` 覆盖率/事实/未知项/可用动作真实接入 |
| 数据脉搏 | `/stats/pulse` 真实计数 + 展示系数；首页指标与数据状态页已接，不再前端拼数 |
| 在售与选择器 | `coverage` 覆盖分、"覆盖足"筛选、promoted → 覆盖 → 停售排序 |
| 互动埋点 | `POST /interactions` 白名单幂等；前端 `focus_select` / `action_click` / `free_text_send` / `pulse_open` 已上报 |
| 合规闭环 | `/gate/verify`、`/me/under18-lock`、`/compliance/state|self-exclusion|self-assessment`；`POST /bets` 与 focus capabilities 服务端硬拦截未成年/自排除/休息中；移动端启动回填服务端状态 |
| 串关体检 | `POST /tools/parlay/check` 四维体检（成本/信息/模型/结构），缺模型不伪造组合概率 |
| 管理后台 | `/admin`：总览/模型池/用量/人设/推荐主链（逐条+批量+plan 操作+撤回理由）/组合/数据/运维/账号/审计/日志；RBAC + CSRF + 会话撤销 + 审计 |
| 认证 | 设备令牌 + CN 手机号/微信、GL Email/Google/Apple；JWT 轮换 + refresh 复用检测；生产 fail-closed |
| 封存与信任 | 判决哈希封存链、公开账本、分享编号可验（`/s/{id}`）、周报/复盘 |
| 推送骨架 | 事件监控 → 扇出 → 站内信/推送（JPush 未配置时 dry-run）；通知设置/收件箱/关注已通 |
| 人设语气 | 三套 profile + 槽位 + 模型池（Key 加密/failover/缓存/预生成）；后台可改 |
| LLM Gateway | Phase 1：登录用户 `open_chat → fast`，预算/缓存/PII 脱敏/用量账本；匿名 0 LLM |
| API-Football | fixtures/lineups/injuries/standings 同步、免费额度、自动/人工链接；配 key 的部署自动装每日 cron |

### 待做（外部依赖或下一阶段）

- **JPush 真机推送**：客户端 token 注册、通知权限软请求、点击深链、厂商凭证。
- **支付/订阅权益**：`subscriptions/entitlements`、RevenueCat/微信商户号、免费 1 条/其余锁定。
- **备份/PITR**：云控制台自动备份或自建 `pg_backup.sh` + WAL 归档 + 恢复演练（上线阻塞项）。
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
just api-test             # pytest（256 tests）

# 前端（Node 22 自带 corepack；仓库 .npmrc 固定 node-linker=hoisted）
just install              # corepack pnpm install
just api-client-generate  # 从后端导出 OpenAPI 快照并重新生成 client
just mobile-start         # expo start
just mobile-android       # expo run:android

# 契约变更后必须重新生成 client，禁止对着可能过期的本地服务生成
just api-openapi
```

部署到 VPS：`cd jieqiu-backend && python deploy.py`（需导出 `JQ_DEPLOY_PASSWORD` 与 `JQ_ADMIN_PASSWORD`；细节见 [docs/operations-runbook.md](./docs/operations-runbook.md)）。

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