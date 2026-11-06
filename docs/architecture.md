# 球多多 · AI 优先架构（v1）

> 状态：已采纳（ADR-0001 / 0002 / 0003）。**本文描述目标态，不等同于当前目录。**
> 目标：让 AI 开发“每次只在一个小上下文里写对”，并让错误在类型、契约、测试层被立刻发现。

## 0. 当前实现（2026-11-05）

- 生产后端仍在 `jieqiu-backend/`，尚未迁到 `services/api/`；`services/` 只有迁移说明。
- 生产前端在 `apps/mobile/`；`apps/web/`、`apps/admin/` 仍是规划，当前管理后台是后端同进程的 `/admin`。
- OpenAPI 138 路径 / 154 方法；后端 295 tests；Alembic head `20261106_16`。
- Postgres 是目标生产库；未设置 `JQ_PROD_DATABASE_URL` 时生产部署仍可能是旧 SQLite 兼容模式。
- 新增的 catalog/actions 已按 feature slice 落地；verdict/assistant 仍是混合目录，迁移未完成。
- **聚焦决策流部分实现**：前端已有 `focusStore`、头像/选择器选中回首页聚焦、聚焦卡、详情页“让助理看这场”；后端 `/stats/pulse`、`/matches/{id}/focus`、`/interactions`、`interaction_events` 已实现；`/matches/on-sale` 已返回与 focus 同一判定的 `coverage`；`intel_items`/`match_coverage`/`pulse_daily` 与前端数据脉搏首屏仍未实现。目标契约见 [focused-decision-flow.md](./focused-decision-flow.md)。
- **API-Football 已接入但默认关闭**：配置 `JQ_API_FOOTBALL_KEY` 后同步 fixtures/lineups/injuries/standings；未配置时 focus 明确返回 missing，不伪造。见 [api-football.md](./api-football.md)。
- **产品口径 2026-11-05 转向**：允许经 AI 复核的赛前预测/参考组合/串关参谋；推荐主链（`decision_snapshots`/`recommendation_plans` + AI 复核/发布）已实现，Today Hero 优先消费 published snapshot，`/tools/parlay/plan` 保留未复核预览，付费/权益待做，见 [recommendation-product.md](./recommendation-product.md)。
- **LLM Gateway Phase 1 已实现**：`open_chat` fallback → fast，带缓存、原子预算、PII 脱敏、调用账本与 后台 `/admin` 模型用量页只读看板；persona 传输已走 `call_profile`；deep 分析与 focus 解读待 Phase 2。见 [llm-gateway.md](./llm-gateway.md)。
- **推荐主链已实现**：`decision_snapshots` + `recommendation_plans` + `review_runs` + `recommendation_events`；build → L1–L5 review → publish → expire/withdraw；`GET /recommendations/today` 只返回 published；Today Hero 已优先消费 snapshot，组合页已优先 published，preview 仅回退。见 [recommendation-product.md](./recommendation-product.md)。

## 1. 架构原则

1. **单仓多包**：后端、移动端、Web、共享包在一个仓库，接口与类型可原子变更。
2. **模块化单体**：先不做微服务；API 是一个部署单元，按 feature 切分。
3. **契约优先**：OpenAPI 生成前端 client；数据库迁移是 schema 事实源；AI 输出有 JSON Schema。
4. **垂直切片**：按业务能力（verdict / intel / assistant / billing / account）组织代码，而不是按技术层堆文件。
5. **强类型 + 可验证**：Pydantic、TypeScript strict、测试、契约测试、迁移测试。
6. **一键命令**：AI 与人都能用 `just ...` 完成开发、测试、迁移、构建。
7. **可回滚**：部署、迁移、feature flag 都必须有回退方式。
8. **无聊技术栈**：使用主流、文档充足、AI 训练语料丰富的框架，减少猜错概率。

## 2. 目标结构

```text
apps/
  mobile/        Expo React Native + TypeScript（Android 先发）
  web/           Next.js：落地页 / 公开账本 / 分享页
  admin/         管理后台（React 或 Jinja+HTMX；后续迁移）
services/
  api/           FastAPI 模块化单体
packages/
  api-client/    OpenAPI 生成的 TS client
  ui/            设计 tokens / 基础组件
  i18n/          多语言文案
  config/        共享工程配置
infra/
  docker-compose.yml
deploy/
docs/
AGENTS.md
justfile
```

## 3. 后端结构

```text
services/api/app/
  core/
    config.py
    db.py
    security.py
    errors.py
    events.py
  features/
    account/
    verdict/
    intel/
    assistant/
    billing/
    report/
  workers/
    assistant_worker.py
    settle_worker.py
```

每个 feature：

```text
router.py      HTTP 层
service.py     业务规则
repository.py  数据访问
schemas.py     Pydantic
models.py      ORM（逐步从全局 models.py 迁移）
tests/
README.md
```

跨 feature 只允许：

- 调用对方 `service`；
- 订阅领域事件；
- 通过共享 `core` 依赖。

禁止 feature 直接 import 另一个 feature 的 `repository`。

## 4. 前端结构

```text
apps/mobile/src/
  features/
    home/
    verdict/
    intel/
    assistant/
    account/
    billing/
  app/             Expo Router 路由薄壳
  shared/          通用 hooks/工具
packages/ui        共享组件
packages/i18n      文案
packages/api       生成的 client
```

规则：

- 单文件 < 300 行；
- 组件 < 150 行；
- 服务端状态用 TanStack Query；
- 本地状态用 Zustand；
- 动效用 Reanimated；
- 文案全部 i18n。

## 5. 数据与契约

- 目标生产/CI 使用境内 Postgres 16（云托管优先 / 自建兜底，非 Supabase，ADR-0004）；详见 [数据库架构](./database-architecture.md)；当前旧部署仍可能使用 SQLite，切换步骤见该文；
- Alembic 是 schema 事实源；
- SQLite 仅允许纯单元测试、一次性工具或尚未切换的旧部署；
- OpenAPI 由 FastAPI 生成；后端导出 `packages/api-client/openapi.json` 快照，client 从快照离线生成；
- Postgres 迁移先于应用启动；Alembic head 为 `20261106_16`，baseline 24 张表，当前 ORM 共 46 张表（新增 interaction_events、API-Football 5 张表、LLM 4 张表、AI 解读 1 张表、人设翻译 4 张表、推荐主链 4 张表与管理账号/审计 2 张表）；
- AI 输出必须通过 Pydantic / JSON Schema 校验；
- 领域事件必须有 `dedupe_key`、`payload_hash`、`data_cutoff`。

## 6. 部署

- `services/api` 一个部署单元 + 独立 worker；
- Web 是静态站点；
- 使用发布目录 + symlink 原子切换；
- 配置走环境变量模板；
- 迁移先于应用启动；
- staging 先行，prod 人工确认；
- 禁止部署脚本删除数据目录。

## 7. 测试策略

| 层 | 工具 | 覆盖 |
|---|---|---|
| 后端单测 | pytest | service / 纯函数 |
| 后端集成 | pytest + Postgres | router / repository / migration |
| 契约 | OpenAPI diff + client 生成 | 前后端契约 |
| 前端单测 | Vitest + RNTL | hooks / 组件 |
| E2E | Maestro | 核心用户流程 |

> 当前实际（2026-11-06）：后端 pytest 271 项仍主要跑 SQLite；未接真实 Postgres CI；前端 Vitest 30 项 + typecheck/lint + Expo Android bundle；Maestro/E2E 尚未接入。

## 8. 迁移路线

| 阶段 | 内容 |
|---|---|
| Phase 0 | monorepo / AGENTS / justfile / docker compose |
| Phase 1 | assistant 作为后端 feature slice 试点 |
| Phase 2 | Postgres + Alembic；SQLite 退出集成测试 |
| Phase 3 | OpenAPI client 生成接入 mobile |
| Phase 4 | verdict / intel / billing 迁移到 feature slice |
| Phase 5 | admin 迁移；旧目录退役 |

## 9. 内容与发布规则（2026-11-05 修订）

- 允许经 AI 复核的赛前预测、参考组合与参考预算；不承诺收益。
- 推荐观点/组合正式发布必须经 `decision_snapshots` / `recommendation_plans` 的 AI 复核流水线（L1–L5 → publish）；当前 `/tools/parlay/plan` 是未复核预览，不得进入付费区。
- 公开文案用委婉语；付费详情必须写明方向、条件、失效条件与成本。
- 推送只写“今日预测已更新”等中性提示，不写具体赔率/结果。
- 年龄确认、自排除、连败保护作为支付/上架能力保留；
- 用户原始下注数据不得上传第三方。


## 10. 聚焦决策流与情报层（目标态）

> 部分实现：前端已有选中→回首页聚焦、focusStore、聚焦卡、详情入口；后端 focus/pulse/interactions 已实现；intel_items/match_coverage/pulse_daily 与前端数据脉搏首屏仍未实现。OpenAPI 为 128/143。详见 [focused-decision-flow.md](./focused-decision-flow.md)。

首页从“12 张判决卡 + 常驻输入框”改为：

```text
数据脉搏 → 选一场 → 首页聚焦这一场 → 客观情报 + 解读 → 动作按钮
```

对应后端边界：

| 能力 | 目标接口/模块 | 数据 |
|---|---|---|
| 数据脉搏 | `GET /stats/pulse` · `features/intel` | 现有 sp_matches/sp_snapshots/intl_odds/model_runs/verdicts |
| 单场聚焦 | `GET /matches/{id}/focus` · `features/intel` | focus service 复用 verdict/catalog；新增 intel_items/match_coverage |
| 比赛选择器覆盖徽章 | `GET /matches/on-sale` 扩展 | match_coverage |
| 动作漏斗 | `POST /interactions` | interaction_events |
| 深读解读 | `ai_analyses` + LLM Gateway；`analysis_jobs` 待做 | 仅 eligible 场次，同步生成 + hash/6h 缓存 |
| 多模型路由 | [llm-gateway.md](./llm-gateway.md) · `/admin` 模型用量页 | fast/deep、预算、缓存、usage |
| 客观情报 | [api-football.md](./api-football.md) · `modules/api_football.py` | fixtures/lineups/injuries/standings；免费档 90/日 |
| 后台 | `/admin` 运营台 + `/admin/api/*` | 总览/模型池/用量/人设/主链/组合/数据/日志 |

约束：

- 选中比赛必须回首页聚焦，不直接跳详情；详情仍走 `/verdicts/{id}`。
- `capabilities` 由后端计算，前端不能自行放开下注/关注/休息。
- 数据脉搏只展示真实计数；无数据返回 0/missing，不造假。
- 事实层由确定性代码生成；LLM 只做解读，且只对 coverage 达标场次。
- 新增路由需重新采纳 W8 freeze 基线；新表走 Alembic，禁止 `create_all`。
