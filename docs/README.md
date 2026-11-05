# 球多多文档索引

最后对账：2026-11-05。App 品牌为 **球多多**（技术标识/包名仍 `jieqiu`）。当前代码事实：`0.8.0-w8+assistant`，OpenAPI **128 路径 / 143 方法**，后端 **251 tests**，前端 **22 tests**，Alembic head `20261105_12`。

## 先读

| 文档 | 用途 |
|---|---|
| [AGENTS.md](../AGENTS.md) | 工程协作规则、目录约定、Definition of Done |
| [README.md](../README.md) | monorepo 入口 + SP 采集器说明 |
| [architecture.md](./architecture.md) | 目标架构与迁移阶段 |
| [persona-system.md](./persona-system.md) | **三种人设语气配置**：profiles/copy slots/模型池/AI 复核/后台编辑（部分实现） |
| [recommendation-product.md](./recommendation-product.md) | **赛前判断 / 串关参谋 / AI 复核发布**：新红线、免费付费、帮我配、组合卡、AI 复核流水线（snapshot/review/publish 主链已实现；组合页 published 优先、preview 回退；付费待做） |
| [focused-decision-flow.md](./focused-decision-flow.md) | **聚焦决策流 / 数据脉搏 / 情报层**：前端聚焦、focus/pulse/interactions API、后台 `/admin` 的数据源/运维/模型用量/人设文案/推荐主链/组合预览页已实现；intel 表/数据脉搏首屏/LLM 深读仍待做 |
| [llm-gateway.md](./llm-gateway.md) | **LLM Gateway / 多模型路由**：fast/deep、任务矩阵、预算/缓存、`llm_*` 表、后台 `/admin` 模型用量页、审核任务与 persona 传输统一（Phase 1 已实现，deep 解读待做） |
| [api-football.md](./api-football.md) | **API-Football 免费档接入**：fixtures/lineups/injuries/standings、免费额度、队名链接、focus 集成、后台页面 |
| [database-architecture.md](./database-architecture.md) | 境内 Postgres（云托管优先/自建兜底）、连接池、索引、保留、备份/PITR 落地、切换 |
| [operations-runbook.md](./operations-runbook.md) | 当前部署、cron、健康检查、`/admin` 后台、回滚与事故排查 |
| [open-source-watchlist.md](./open-source-watchlist.md) | 开源引用/候选清单：维护状态、许可证、采纳/降级结论 |

## 决策记录（ADR）

| 文档 | 决策 |
|---|---|
| [0001-ai-native-modular-monolith.md](./decisions/0001-ai-native-modular-monolith.md) | AI 原生模块化单体 + 单仓多包 |
| [0002-postgres-only.md](./decisions/0002-postgres-only.md) | 生产/CI 统一 Postgres，退出双数据库方言 |
| [0003-contract-first-api-client.md](./decisions/0003-contract-first-api-client.md) | 前后端契约优先，客户端代码生成 |
| [0004-managed-postgres-preferred.md](./decisions/0004-managed-postgres-preferred.md) | **境内 Postgres：云托管优先 / 自建兜底，不用 Supabase** |

## 产品与技术规格

| 文档 | 说明 |
|---|---|
| [PRD-v5.1.md](../PRD-v5.1.md) | 产品定义、用户/功能/商业化；UI 实现以 `apps/mobile` 为准 |
| [TechSpec-v2.1.md](../TechSpec-v2.1.md) | 技术选型、数据模型、API v1 草案、模型/合规约束 |
| [Release-plan-v1.1.md](../Release-plan-v1.1.md) | 周次排期与上线 Gate（历史计划 + 当前状态注记） |
| [Roadmap-v1.1.md](../Roadmap-v1.1.md) | 版本路线与转向门 |
| [Feature-API-Mapping-v1.0.md](../Feature-API-Mapping-v1.0.md) | 功能 ↔ API ↔ 数据表映射 + 2026-11-04 补全 |
| [Assistant-Runtime-v1.0.md](../Assistant-Runtime-v1.0.md) | 助理运行时设计、事件/推送/记忆 |
| [Intelligence-Layer-v1.0.md](../Intelligence-Layer-v1.0.md) | 情报层设计；signals/AI 表仍未实现 |
| [OpsAutomation-blueprint-v1.0.md](../OpsAutomation-blueprint-v1.0.md) | 运营自动化蓝图（目标态，不代表已部署） |

## 实现/交接

| 文档 | 说明 |
|---|---|
| [jieqiu-backend/README.md](../jieqiu-backend/README.md) | 当前生产后端、认证、部署、数据库命令 |
| [services/README.md](../services/README.md) | 后端目录迁移目标与 Postgres 切换注意事项 |
| [apps/mobile/ARCHITECTURE.md](../apps/mobile/ARCHITECTURE.md) | 移动端路由、适配器、会话、已知缺口 |
| [apps/mobile/README.md](../apps/mobile/README.md) | 移动端启动/构建/自检 |
| [packages/api-client/README.md](../packages/api-client/README.md) | OpenAPI client 生成与契约规则 |
| [jieqiu-backend/app/features/assistant/README.md](../jieqiu-backend/app/features/assistant/README.md) | assistant feature slice 不变量与待办 |

## 审查记录（按时间）

| 文档 | 内容 |
|---|---|
| [2026-11-04-code-review-pass2.md](./reviews/2026-11-04-code-review-pass2.md) | 第二轮代码复审（历史快照）：并发/事务/采集器/前端清理；当时 182 tests |
| [2026-11-04-full-stack.md](./reviews/2026-11-04-full-stack.md) | 第一轮全栈深审与修复（历史快照）；残余风险 |
| [2026-11-04-docs-review.md](./reviews/2026-11-04-docs-review.md) | 文档审查（历史快照）：过期事实、状态标注、索引与链接校验 |
| [2026-11-04-api-audit.md](./reviews/2026-11-04-api-audit.md) | API 全量对账与补全（历史快照；当时 100/113，当前 128/143） |
| [2026-11-04-database.md](./reviews/2026-11-04-database.md) | 数据库深审（历史测试数 166） |
| [2026-11-04-mobile-frontend.md](./reviews/2026-11-04-mobile-frontend.md) | 移动端验收（历史测试数 159） |
| [2026-11-04-monorepo-base-review.md](./reviews/2026-11-04-monorepo-base-review.md) | monorepo 基座审查（历史 71 路径） |

## 历史材料

- `archive/`：旧版 PRD/TechSpec/Review，仅用于追溯，不代表当前实现。
- `w1-validation/`：W1 数据验证结果，历史数据口径。
- `jieqiu-app/`：临时展示 UI，只作设计参考，禁止继续加功能。

## 维护规则

- 文档中的数字必须能从代码/OpenAPI/测试命令复现；
- 历史审查记录不改写结论，只加“历史快照”标注；
- 新增/删除接口必须同步：后端 README、Feature-API-Mapping、OpenAPI 快照、client；
- 新增路由后重新采纳 W8 冻结基线；
- 数据库/Schema 变更同步 `database-architecture.md` 与 Alembic head。
