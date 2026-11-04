# 解球 · AI 优先架构（v1）

> 状态：已采纳（ADR-0001 / 0002 / 0003）。**本文描述目标态，不等同于当前目录。**
> 目标：让 AI 开发“每次只在一个小上下文里写对”，并让错误在类型、契约、测试层被立刻发现。

## 0. 当前实现（2026-11-04）

- 生产后端仍在 `jieqiu-backend/`，尚未迁到 `services/api/`；`services/` 只有迁移说明。
- 生产前端在 `apps/mobile/`；`apps/web/`、`apps/admin/` 仍是规划，当前管理后台是后端同进程的 `/console`。
- OpenAPI 94 路径 / 107 方法；后端 182 tests；Alembic head `20261104_04`。
- Postgres 是目标生产库；未设置 `JQ_PROD_DATABASE_URL` 时生产部署仍可能是旧 SQLite 兼容模式。
- 新增的 catalog/actions 已按 feature slice 落地；verdict/assistant 仍是混合目录，迁移未完成。

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
- Postgres 迁移先于应用启动；Alembic head 为 `20261104_04`，baseline 覆盖 24 张表；
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

> 当前实际（2026-11-04）：后端 pytest 182 项仍主要跑 SQLite；未接真实 Postgres CI；前端 Vitest 20 项 + typecheck/lint + Expo Android bundle；Maestro/E2E 尚未接入。

## 8. 迁移路线

| 阶段 | 内容 |
|---|---|
| Phase 0 | monorepo / AGENTS / justfile / docker compose |
| Phase 1 | assistant 作为后端 feature slice 试点 |
| Phase 2 | Postgres + Alembic；SQLite 退出集成测试 |
| Phase 3 | OpenAPI client 生成接入 mobile |
| Phase 4 | verdict / intel / billing 迁移到 feature slice |
| Phase 5 | admin 迁移；旧目录退役 |

## 9. 当前红线

- `jieqiu-app/index.html` 不继续扩展；
- 认证、支付、封存链、合规文案必须人工 review；
- 推送/通知不得出现赔率/投注/“稳赚”字样；
- 未成年保护、自排除、连败保护不得绕过；
- 用户原始下注数据不得上传第三方。
