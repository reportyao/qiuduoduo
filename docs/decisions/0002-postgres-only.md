# ADR-0002 · 生产/CI 统一 Postgres，退出双数据库方言

- 状态：已采纳
- 日期：2026-11-03

## 背景

当前项目同时支持 SQLite 与 Postgres，导致：

1. AI 需要同时理解两种方言；
2. 部分测试在 SQLite 通过、Postgres 失败；
3. JSON/索引/时间类型行为不一致；
4. 迁移策略无法统一。

## 决策

- 生产、staging、CI 集成测试统一使用 **Postgres 16**；
- 本地开发使用 Docker Compose 启动 Postgres；
- SQLite 仅允许用于纯单元测试或一次性工具；
- 新增代码不得添加 SQLite-only 方言分支；
- 数据库迁移统一使用 Alembic。

## 后果

- 减少方言分支；
- JSON、索引、约束、事务行为一致；
- AI 生成迁移更可靠；
- 本地开发需要 Docker；
- 需要逐步迁移现有测试。
