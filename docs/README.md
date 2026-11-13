# 球多多文档索引

最后对账：2026-11-12。App 品牌为 **球多多**（技术标识/包名仍 `jieqiu`，Android/iOS 包名 `com.qiuduoduo.app`）。当前代码事实：后端 `0.8.0-w8+assistant` / 移动端 `0.3.4`，OpenAPI **158 路径 / 174 方法**，后端 **353 tests**，前端 **59 tests**，Alembic head `20261112_24`；开发库仍是 SQLite + WAL，生产目标境内 PostgreSQL 16 尚未切库。

> **产品/技术方案唯一有效版本：** [qiuduoduo-v4-final-plan.md](./qiuduoduo-v4-final-plan.md)。  
> 其他 `ai-*` / `membership-*` / `grounded-*` 产品方案已标记作废，仅作历史参考；技术文档（architecture / database / API / workbench / OPC）不受影响。

## 当前状态（2026-11-12）

- **v4.1 已完成并部署腾讯云生产（2026-11-12 11:38 CST）；v4 APK 已由 GitHub Actions 构建并在模拟器安装验证；最终对话版 APK 为 commit `2d8e75e`（run `43351698209`）。** 4 Tab 为助理/比赛/计划/我的；记录移入“我的 → 我的记录”。
- **计划**：`plan_cycles / plan_bets / plan_bet_legs` 已落地；每期最多 4 场、每场 100、总预算 400；稳健/平衡/进取三种结构；v1 选场只处理 1X2/让球，要求正 edge、正 EV，同联赛最多 2 场，不足 4 场不硬凑。
- **会员**：权益、每日免费额度、Max 计划门控、后台手动开通/撤销、到期 job 已实现；充值页只是假 UI，不创建订单、不接支付。
- **赛果**：FT90 口径、整数亚盘 void/push、`market_settlements`、独立 `settle_pending`、`performance_daily` 已实现；账本/周报/复盘排除 void。
- **人设**：`/chat` 接受 `persona`，回复走 `assistant_copy` + DB copy slots；三种语气共享同一事实包。
- **OPC 后台**：用户与会员、AI 计划、异常队列、引擎配置、推荐主链、数据源、模型效果已接。
- **明确缺口**：真实支付、多盘口完整数据、计划自训练模型、计划更新提醒、生产 Postgres 切库、JPush 真机验收、v4 正式 APK 均未完成。
- **历史状态**：推荐主链、概率经验区间、CLV、未采纳复盘、T-3h/T-30m 赛前提醒仍有效；`/recommendations/today` 只读 published。API-Football 仍是 API-Sports Free（当前赛季 standings 受限）。

## 先读

| 文档 | 用途 |
|---|---|
| [AGENTS.md](../AGENTS.md) | 工程协作规则、目录约定、Definition of Done |
| [README.md](../README.md) | monorepo 入口、当前事实、v4.1 实现/边界 + SP 采集器说明 |
| [architecture.md](./architecture.md) | 目标架构、当前实现与迁移阶段 |
| [persona-system.md](./persona-system.md) | **三种人设语气配置**：profiles/copy slots/模型池/后台编辑；`/chat` 已消费 copy slots，推荐文案三套生成仍待接 |
| [recommendation-product.md](./recommendation-product.md) | **赛前判断 / 串关参谋 / AI 复核发布**：snapshot/review/publish 主链、CLV/经验区间、未采纳复盘已实现；会员权益已接，充值仍是假 UI |
| [qiuduoduo-v4-final-plan.md](./qiuduoduo-v4-final-plan.md) | **唯一有效方案（v4.1）**：4 Tab、HeaderMetrics、每日战绩、4 场定投计划、选场引擎、会员权益（仅充值假 UI）、赛果结算、人设单一事实源、OPC 后台、记忆；计划提醒/真实推送仍是下一阶段；文首附实现状态 |
| [mobile-ai-assistant-refactor.md](./mobile-ai-assistant-refactor.md) | **已作废**：AI 助理交互重构早期方案；UI/产品以 v4.1 为准 |
| [frontend-optimization-review.md](./frontend-optimization-review.md) | **历史审查稿**：前端优化汇总，部分结论已被 v4.1 取代 |
| [opc-ai-refactor.md](./opc-ai-refactor.md) | OPC / 数据层 / 联赛门控技术参考；实施状态以 v4.1 与代码为准 |
| [jc-data-model.md](./jc-data-model.md) | 竞彩/Sportmonks 数据模型参考 |
| [sportmonks-refactor-plan.md](./sportmonks-refactor-plan.md) | Sportmonks 数据源收编方案（技术参考） |
| [sportmonks-v3-real-data-plan.md](./sportmonks-v3-real-data-plan.md) | Sportmonks v3 真实数据计划与联赛覆盖证据 |
| [sm_deepseek_review.md](./sm_deepseek_review.md) | Sportmonks 方案 DeepSeek 独立评审记录 |
| [sm_review_context.md](./sm_review_context.md) | Sportmonks 评审上下文与数据材料 |
| [ai-native-token-plan.md](./ai-native-token-plan.md) | **已作废**：AI-native 一个助理三个脑、Token 计费；仅历史参考 |
| [ai-warroom-monetization-plan.md](./ai-warroom-monetization-plan.md) | **已作废**：AI 作战室/分析员团队/计划单；仅历史参考 |
| [ai-match-membership-plan.md](./ai-match-membership-plan.md) | **已作废**：用户选场、每日 1 次免费、会员无限；仅历史参考 |
| [membership-pro-max-ai-plan.md](./membership-pro-max-ai-plan.md) | **已作废**：Pro/Max 早期方案；仅历史参考 |
| [grounded-app-optimization.md](./grounded-app-optimization.md) | **已作废**：基于旧 4 Tab 的改造清单；仅历史参考 |
| [ai-daily-one-subscription.md](./ai-daily-one-subscription.md) | **已作废**：AI 每日只推一场、订阅制；仅历史参考 |
| [three-gate-refactor-decision.md](./three-gate-refactor-decision.md) | 三闸与预测呈现重构决策：保留三闸做诊断，前台改为核验预测/市场参考/回避三层，附联赛模型门控与落地阶段 |
| [focused-decision-flow.md](./focused-decision-flow.md) | **聚焦决策流 / 数据脉搏 / 情报层**：前端聚焦、focus/pulse/interactions API、首页真实脉搏/聚焦面板/覆盖筛选/埋点、后台 `/admin` 的数据源/运维/模型用量/人设文案/推荐主链/组合预览页已实现；intel 表/LLM 深读仍待做 |
| [llm-gateway.md](./llm-gateway.md) | **LLM Gateway / 多模型路由**：fast/deep、任务矩阵、预算/缓存、`llm_*` 表、后台 `/admin` 模型用量页、审核任务与 persona 传输统一（Phase 1 已实现，deep 解读待做） |
| [api-football.md](./api-football.md) | **API-Football 接入**：API-Sports 直连 / RapidAPI、fixtures/lineups/injuries/standings、免费额度、7 秒节流、当天+次日、focus 集成、后台页面；apifootball.com 是另一家 provider，未接入 |
| [database-architecture.md](./database-architecture.md) | 境内 Postgres（云托管优先/自建兜底）、连接池、索引、保留、备份/PITR 落地、切换 |
| [operations-runbook.md](./operations-runbook.md) | 当前部署、cron、健康检查、`/admin` 后台、回滚与事故排查 |
| [performance.md](./performance.md) | 性能基线：接口 p50/p95、缓存/gzip/SQLite/包体优化、网络与并发限制 |
| [frontend-deep-test-2026-11-06.md](./frontend-deep-test-2026-11-06.md) | 移动端深度测试：已修复问题、回归结果与仍未闭环的上线缺口 |
| [prediction-first-frontend-2026-11-06.md](./prediction-first-frontend-2026-11-06.md) | 预测优先的前端口径：取消“不预测”底线、首页/详情/助理/工具改版与边界 |
| [ui-unslop-2026-11-06.md](./ui-unslop-2026-11-06.md) | Unslop 逐页 UI 审计：方向、页面处理、全局 tokens 与交互细节 |
| [jpush.md](./jpush.md) | JPush Android 6.3.0 接入、registration id 上报、系统通知权限、厂商通道后续配置 |
| [workbench.md](./workbench.md) | 运营工作台：全链路阶段、状态语义、AI 体检与安全动作 |
| [admin-console-refactor.md](./admin-console-refactor.md) | 2026-11-11 后台重构 + 2026-11-12 v4 增补：逐场数据矩阵、Sportmonks 手动映射、SM Pinnacle 市闸、模型效果页、用户/会员、AI 计划、异常队列、引擎配置 |
| [xg-providers.md](./xg-providers.md) | xG 第三方数据源选型：Sportmonks / StatsBomb / FBref / SofaScore / Understat 的适用边界 |
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
| [PRD-v5.1.md](../PRD-v5.1.md) | 历史产品定义；当前 UI/商业化以 v4.1 为准 |
| [TechSpec-v2.1.md](../TechSpec-v2.1.md) | 历史技术选型/数据模型/API 草案；当前契约以 OpenAPI 为准 |
| [Release-plan-v1.1.md](../Release-plan-v1.1.md) | 周次排期与上线 Gate（历史计划 + 当前状态注记） |
| [Roadmap-v1.1.md](../Roadmap-v1.1.md) | 版本路线与转向门 |
| [Feature-API-Mapping-v1.0.md](../Feature-API-Mapping-v1.0.md) | 功能 ↔ API ↔ 数据表映射 + 2026-11-04 补全 |
| [Assistant-Runtime-v1.0.md](../Assistant-Runtime-v1.0.md) | 助理运行时设计、事件/推送/记忆 |
| [Intelligence-Layer-v1.0.md](../Intelligence-Layer-v1.0.md) | 情报层设计；signals/AI 表仍未实现 |
| [OpsAutomation-blueprint-v1.0.md](../OpsAutomation-blueprint-v1.0.md) | 运营自动化蓝图（目标态，不代表已部署） |

## 实现/交接

| 文档 | 说明 |
|---|---|
| [jieqiu-backend/README.md](../jieqiu-backend/README.md) | 当前后端（过渡期目录）、v4 接口、认证、部署、数据库命令 |
| [services/README.md](../services/README.md) | 后端目录迁移目标与 Postgres 切换注意事项 |
| [apps/mobile/ARCHITECTURE.md](../apps/mobile/ARCHITECTURE.md) | 移动端 4 Tab 路由、v4 查询/会员/计划、会话、已知缺口 |
| [apps/mobile/README.md](../apps/mobile/README.md) | 移动端启动/构建/自检 |
| [packages/api-client/README.md](../packages/api-client/README.md) | OpenAPI client 生成与契约规则 |
| [jieqiu-backend/app/features/assistant/README.md](../jieqiu-backend/app/features/assistant/README.md) | assistant feature slice 不变量与待办 |

## 审查记录（按时间）

| 文档 | 内容 |
|---|---|
| [2026-11-12-sportmonks-data-gap-review.md](./reviews/2026-11-12-sportmonks-data-gap-review.md) | Sportmonks 数据能力与前端缺口：首发/阵型/伤停/积分榜/H2H/天气/裁判/25 维预测/选定市场，P0–P2 落地状态与边界 |
| [2026-11-12-v4-verification.md](./reviews/2026-11-12-v4-verification.md) | v4.1 交付验证：349/53 测试、OpenAPI 158/174、模拟器路径、已修问题、明确未完成 |
| [2026-11-11-deep-review.md](./reviews/2026-11-11-deep-review.md) | 当日深审：概率卡模型字段、SM 数据覆盖/过期、赛果回填 500、脉搏/聚焦数据源、同场串关等修复与剩余缺口 |
| [2026-11-04-code-review-pass2.md](./reviews/2026-11-04-code-review-pass2.md) | 第二轮代码复审（历史快照）：并发/事务/采集器/前端清理；当时 182 tests |
| [2026-11-04-full-stack.md](./reviews/2026-11-04-full-stack.md) | 第一轮全栈深审与修复（历史快照）；残余风险 |
| [2026-11-04-docs-review.md](./reviews/2026-11-04-docs-review.md) | 文档审查（历史快照）：过期事实、状态标注、索引与链接校验 |
| [2026-11-04-api-audit.md](./reviews/2026-11-04-api-audit.md) | API 全量对账与补全（历史快照；当时 100/113，当前 158/174） |
| [2026-11-04-database.md](./reviews/2026-11-04-database.md) | 数据库深审（历史测试数 166） |
| [2026-11-04-mobile-frontend.md](./reviews/2026-11-04-mobile-frontend.md) | 移动端验收（历史测试数 159） |
| [2026-11-04-monorepo-base-review.md](./reviews/2026-11-04-monorepo-base-review.md) | monorepo 基座审查（历史 71 路径） |

## 历史材料

- `archive/`：旧版 PRD/TechSpec/Review，仅用于追溯，不代表当前实现。
- `w1-validation/`：W1 数据验证结果，历史数据口径。
- `archive/legacy/jieqiu-app/`：临时展示 UI，只作设计参考，禁止继续加功能（见 [archive/legacy/jieqiu-app/README.md](../archive/legacy/jieqiu-app/README.md)）。

## 维护规则

- 文档中的数字必须能从代码/OpenAPI/测试命令复现；
- 历史审查记录不改写结论，只加“历史快照”标注；
- 新增/删除接口必须同步：后端 README、Feature-API-Mapping、OpenAPI 快照、client；
- 新增路由后重新采纳 W8 冻结基线；
- 数据库/Schema 变更同步 `database-architecture.md` 与 Alembic head。
