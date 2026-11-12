# 球多多 Monorepo

AI 足球助理 / 赛前预测产品。当前产品口径以 [docs/qiuduoduo-v4-final-plan.md](docs/qiuduoduo-v4-final-plan.md)（v4.1）为唯一有效方案：4 Tab = **助理 · 比赛 · 计划 · 我的**，计划是“每期 4 场、每场 100、总预算 400”的模拟定投方案，只展示、不跟单。

- 仓库：https://github.com/reportyao/qiuduoduo
- 当前开发分支：`feat/v4-plan-settlement`
- 生产后端：`jieqiu-backend/`（FastAPI 模块化单体，过渡期目录，迁移目标 `services/api/`）
- 生产前端：`apps/mobile/`（Expo React Native，Android 先发，iOS 后补）
- 接口契约：`packages/api-client/`（OpenAPI 快照 + 生成 TS client，禁止手写接口类型）
- 数据底座：`sp-collector/`（竞彩官方 SP 自采，家宽出口）

## 当前事实（2026-11-12）

| 事实 | 当前值 |
|---|---|
| 后端版本 | `0.8.0-w8+assistant`（`app.main`） |
| 移动端版本 | `0.3.4` / versionCode `9`（`app.config.ts`，v4.1 尚未出正式 APK） |
| OpenAPI | **158 路径 / 174 方法**（以 `packages/api-client/openapi.json` 为准） |
| 后端测试 | **341 passed**（`python -m pytest -q`，2026-11-12 实测） |
| 前端测试 | **47 passed** + typecheck / ESLint / Android Hermes bundle（2026-11-12 实测） |
| Alembic head | `20261112_23`（v4 core，up/down 已实现） |
| 开发数据库 | SQLite + WAL（过渡）；生产目标境内 PostgreSQL 16，**尚未切库** |
| v4.1 部署状态 | **已部署腾讯云生产（2026-11-12 11:38 CST）；管理后台 v=20261112d；v4 APK 尚未构建发布** |

## v4.1 已实现

| 模块 | 状态 |
|---|---|
| 4 Tab | 助理 / 比赛 / 计划 / 我的；原“记录”移入“我的 → 我的记录” |
| 首页 HeaderMetrics | 陪伴时长、引擎版本、今日数据点、盘口/模型复审；配置读 `engine_config`，无数据不显示 0 |
| 每日 AI 战绩 | `/stats/record/summary`；只统计已发布且已结算，按竞彩日；无数据返回空态 |
| AI 计划 | `plan_cycles / plan_bets / plan_bet_legs`；每期最多 4 场、每场 100、预算 400；稳健/平衡/进取三种结构；收益按 risk 分开 |
| 计划选场 v1 | 只处理 1X2/让球；候选必须有模型概率、市场概率、正 edge、正 EV；同场去重、同联赛最多 2 场；不足 4 场不硬凑 |
| 会员权益 | `user_memberships / membership_events / analysis_quota / market_access`；免费每日 1 场，Pro/Max 不限；Max 可看计划完整 legs |
| 手动开通 | `/admin` 用户与会员页可开通/撤销 Pro/Max；写 membership event + admin audit |
| 充值 UI | **假 UI**：展示价格与权益，按钮只提示“充值暂未开放”；不建订单、不接支付、不伪造支付成功 |
| 赛果与结算 | `match_results` 90 分钟字段、`market_settlements`、`settle_pending`；1X2/让球/OU/BTTS/比分按 FT90；整数亚盘走 void/push |
| 每日表现 | `performance_daily`；账本/周报/复盘排除 void |
| 人设单一事实源 | `persona_copy_slots` + `assistant_copy.render`；`/chat` 接受 `persona`，三种语气共享同一事实包 |
| OPC 管理后台 | 用户与会员、AI 计划、异常队列、引擎配置、推荐主链、数据源、模型效果、OPS |
| 助理记忆 | `user_profile_features` 从注单/关注/显式记忆推导；`/me/profile` 暴露 |
| 训练脚手架 | `feature_snapshots / model_registry / training_runs` 表已建；**离线训练/影子上线尚未实现** |

## 明确未完成 / 边界

- **支付**：没有支付渠道、订单、回调；会员只能由后台手动开通。
- **多盘口数据**：HeaderMetrics 的“5 个盘口 / 7 大模型”是后台配置的展示口径；实际数据仍以竞彩 1X2/让球为主，大小球/BTTS/半全场尚未完整入库。Max 权益写“全市场逐项开放”，不能把未接市场说成已可用。
- **计划自训练模型**：当前是规则 + 现有模型概率的 v1 选场，不是自训练模型；训练表和快照只是脚手架。
- **计划通知**：计划更新提醒/收藏未接；推送只做中性提示，不做跟单。
- **生产 Postgres**：迁移与离线 SQL 已验证，真实切库需要云托管实例和维护窗口。
- **JPush 真机**：Android core 已接，MuMu/Houdini 转译会崩；需 arm64 真机验收，Master Secret 与厂商通道待配。
- **v4 发布包**：本轮只做了 Metro/Hermes bundle 与模拟器验收，没有生成、签名、上传正式 APK。
- **生产部署**：2026-11-12 11:38 CST 已用 `deploy.py` 部署到 `43.128.24.244`；部署前备份代码 `jieqiu-backend-20261112-113522.tar.gz` 与 SQLite 库 `jieqiu-20261112-113522.db`（`/home/ubuntu/backups/`）。

## 工程入口

- 协作规则 / Definition of Done：[AGENTS.md](AGENTS.md)
- 文档索引：[docs/README.md](docs/README.md)
- 移动端交接：[apps/mobile/ARCHITECTURE.md](apps/mobile/ARCHITECTURE.md)
- 后端说明：[jieqiu-backend/README.md](jieqiu-backend/README.md)
- 运维手册：[docs/operations-runbook.md](docs/operations-runbook.md)
- 数据库架构：[docs/database-architecture.md](docs/database-architecture.md)

## 快速开始

优先使用 `just`（`just --list` 查看全部命令）；没有 just 时按 `justfile` 等价命令执行。

```bash
# 后端
just api-install          # pip install -r jieqiu-backend/requirements.txt
just db-up                # 本地 Postgres（docker compose，端口 5433）
just db-migrate           # alembic upgrade head
just api-run              # uvicorn app.main:app --port 8100
just api-test             # pytest（当前 341 tests）

# 前端（Node 22 自带 corepack；仓库 .npmrc 固定 node-linker=hoisted）
just install              # corepack pnpm install
just api-client-generate  # 从后端导出 OpenAPI 快照并重新生成 client
just mobile-start         # expo start
just mobile-android       # expo run:android

# 契约变更后必须重新生成 client，禁止对着可能过期的本地服务生成
just api-openapi
```

移动端构建前必须跑：

```bash
cd apps/mobile
corepack pnpm typecheck
corepack pnpm lint
corepack pnpm test
corepack pnpm exec expo export --platform android --output-dir .export-check --clear
```

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
archive/legacy/jieqiu-app/      临时展示 UI（只作设计参考，禁止加功能）
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
