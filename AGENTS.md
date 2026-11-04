# AGENTS.md · 解球工程协作约定

本文件是 AI 与人类协作开发的**仓库级上下文入口**。任何 AI/开发者在改动代码前必须先读本文件；提交前必须按 Definition of Done 自检。

当前事实（2026-11-04）：生产代码仍在 `jieqiu-backend/`，OpenAPI **94 路径 / 107 方法**，后端 **182 tests**；生产数据库目标是境内 PostgreSQL 16（**云托管优先 / 自建兜底**，ADR-0004），未设置 `JQ_PROD_DATABASE_URL` 时仍是旧 SQLite。文档索引见 [docs/README.md](./docs/README.md)。

## 1. 架构地图

```text
apps/
  mobile/        Expo React Native + TypeScript（Android 先发，iOS 后补；交接见 apps/mobile/ARCHITECTURE.md）
  web/           Next.js 落地页 / 公开账本 / 分享页（规划中）
  admin/         管理后台（规划中；当前旧控制台在 jieqiu-backend/app/routers/console.py）
packages/
  api-client/    OpenAPI 生成的 TS client，禁止手写接口类型
  ui/            设计 tokens / 基础组件（规划中）
  i18n/          文案目录 + 类型化 key（规划中）
  config/        ESLint / TS / 共享配置（规划中）
services/
  api/           FastAPI 模块化单体（自 jieqiu-backend 迁移目标；当前旧目录仍可用）
```

当前过渡期保留：

```text
jieqiu-backend/  旧后端目录（生产部署仍使用）
jieqiu-app/      临时展示 UI（只作设计参考，禁止继续加功能）
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
- Postgres 是生产事实源（自建，非 Supabase）；SQLite 只允许用于纯单元测试或本地工具；架构/索引/备份见 `docs/database-architecture.md`。
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

## 7. 禁区

- 不实现“稳赚/回本/推荐买”类文案；
- 不在推送/锁屏出现赔率、投注、赛事结果字样；
- 不收集未成年人数据；
- 不绕过自排除/连败保护/年龄确认；
- 不向第三方上传用户原始下注数据。

## 8. 目录迁移说明

- 新代码不要加到 `jieqiu-app/index.html`；
- 新后端代码优先进入 `app/features/<feature>`；
- `jieqiu-backend/` 到 `services/api/` 的目录迁移将在 Alembic/Postgres 切换后执行，避免一次性大迁移。
- W8 冻结基线不是永久常量：新增路由后必须用控制台登录调用 `POST /review/freeze/adopt` 重新采纳，否则 `/review/freeze` 会报新增违规。
- 认证默认 fail-closed：`JQ_ENV=dev|test` 才允许 `JQ_AUTH_STUB=true`；staging/prod 必须配置真实短信/邮件/OAuth。
