# Monorepo 基座 Review 记录（2026-11-04）

> **历史快照（2026-11-04）**：本文的测试数/路径数/结论反映当时状态，不是当前事实。当前事实见 [docs/README.md](../README.md)：255 tests / 128 路径 / 143 方法 / Alembic `20261105_12`。


范围：上一轮 AI 优先架构落地（monorepo / Expo 基座 / OpenAPI client / Alembic / assistant feature slice）的代码、配置、脚本与产物。

## 结论

发现并修复 8 个实际问题。修复后：

- 后端：`157 passed`
- `@jieqiu/api-client`：typecheck 通过
- `@jieqiu/mobile`：typecheck / lint / Vitest（2 项）通过
- Android bundle：Metro + Hermes 成功产出 `.hbc`（2.66 MB）
- Alembic：空库 `upgrade head` → `downgrade base` → `upgrade head` 通过；`alembic check` 无差异；Postgres 离线 DDL 可生成

## 发现与修复

### 1. 生成的 client 缺 12 个 assistant 接口（高）

本机 8100 端口是旧进程 `0.7.0-w7`，OpenAPI 只有 59 条路径；当时代码是 `0.8.0-w8+assistant`，71 条路径。原先 `pnpm generate` 直接拉 8100，导致 `schema.d.ts` 漏掉 inbox/watch/notify/push 全部接口且无任何报错。

修复：改为从当前代码导出 `packages/api-client/openapi.json` 快照，再离线生成；`generate:url` 仅保留给联调。

### 2. assistant 接口没有 `response_model`（高）

12 个接口全部返回裸 dict，OpenAPI 响应为 `{}`，前端拿不到任何字段类型，契约优先名存实亡。

修复：新增 `InboxResponse` / `WatchListResponse` / `NotifyResponse` / `OkResponse` 等模型并挂到全部路由；重新生成契约与类型。

### 3. Alembic 只有脚手架、没有 baseline（高）

`migrations/versions/` 为空，`just db-migrate` 是空操作，切 Postgres 时无表可建。

修复：生成 `71af760b1e99_baseline_w8_assistant_runtime.py`，覆盖当时 24 张表；验证 downgrade/upgrade 与 `alembic check`。已有库明确走 `alembic stamp head`，禁止直接跑 baseline。

### 4. Expo bundle 缺 `@babel/runtime`（高）

typecheck/lint 全绿，但 `expo export` 在 `queries.ts` 处失败：pnpm 严格布局下 Babel 注入的运行时在 app 目录解析不到。

修复：app 显式声明 `@babel/runtime`。

### 5. `expo-router` 运行时缺 `query-string`（高）

`expo-router@4.0.22` 的 `build/fork/getPathFromState.js` 直接 `require("query-string")`，但包未声明该依赖；npm 扁平安装靠其他包碰巧提升，pnpm 下必现。

修复：app 显式声明 `query-string@^7.1.3`。

### 6. RN 版本与 Expo SDK 不匹配（中）

`expo install --check` 报告 SDK 52.0.49 期望 `react-native@0.76.9`，项目为 0.76.6。

修复：升级到 0.76.9，复查依赖为 up to date。

### 7. Windows 下 Hermes 编译失败（高，环境相关）

pnpm 严格布局的 `.pnpm/...` 深路径让 `hermesc.exe` 启动报 `ERROR_INSUFFICIENT_BUFFER`（数据区域太小），JS 打完但出不了字节码。

修复：仓库 `.npmrc` 固定 `node-linker=hoisted`；重装后 bundle 成功。该设置已写入 AGENTS 与 mobile README，禁止改回 isolated。

### 8. 检查命令覆盖不全（中）

`just check` 只跑后端测试 + mobile typecheck/test，漏掉 lint、api-client typecheck 和真正出包；`justfile` 内还硬编码 `pnpm`，本机只有 corepack。

修复：`check` 补全五项；`justfile` 统一 `corepack pnpm`；新增 `mobile-bundle`；移除不可用的 `web` 脚本（MVP 只做 Android/iOS）。

## 仍然存在的缺口（未在本轮实现）

1. **Postgres 实切**：生产仍是 SQLite；baseline 已就绪，但数据迁移、`alembic stamp head`、连接池与备份策略未演练。
2. **目录迁移**：`jieqiu-backend` → `services/api` 未执行。
3. **真机/APK**：只验证了 JS bundle，未跑 `expo run:android`、原生 autolinking、推送/支付 SDK。
4. **移动端页面**：目前仅 health 基座；`/stream`、情报层、inbox/watch/settings 未接入。
5. **CI/E2E**：无 CI；无 Detox/Maestro。
6. **管理后台**：仍在 `jieqiu-backend/app/routers/console.py`，未拆为 `apps/admin`。
