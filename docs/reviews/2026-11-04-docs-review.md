# 文档全量审查记录（2026-11-04）

> **历史快照（2026-11-04）**：本文的测试数/路径数/结论反映当时状态，不是当前事实。当前事实见 [docs/README.md](../README.md)：255 tests / 128 路径 / 143 方法 / Alembic `20261105_12`。

范围：仓库内全部现行 Markdown（`AGENTS.md`、根 README、PRD/TechSpec/Release/Roadmap/Feature/Assistant/Intelligence/Ops、`docs/`、后端/移动端/服务/客户端 README）。`archive/`、`w1-validation/` 作为历史材料保留原样，只加索引说明。

## 已修正的过期事实

1. **路径/方法数**：多个文档仍写 71/59/92/105；当时统一为 **94 路径 / 107 方法**（后端 README、client README、Feature 映射、docs 索引、AGENTS、apps 说明）。
2. **测试数**：157/159/161/166/173/99/114 等历史数字统一标注为历史快照；当时全栈审查记录为 **179 backend / 20 mobile**。
3. **`create_all` 叙述**：services/README 原写“应用启动会 create_all，所以先迁移”，与当前 Postgres `init_db()` 直接返回矛盾；改为“Postgres 启动不跑 DDL，必须 Alembic 迁移”。
4. **控制台认证**：TechSpec 仍写密码+IP 白名单/JWT；更新为当前密码 + HttpOnly cookie + 可选 IP 白名单，token 不再进 URL，新增 `/console/logout`。
5. **前端状态**：Assistant/Release/Feature 中“inbox/关注待接”“前端仍本地”已改为已接；实况仍明确只有赛果+SP 快照，真实 live feed/进球提醒未接。
6. **分享**：补充 `/s/{share_id}` 公开 HTML 落地页；README 的 `/me/export` 说明改为“通知/行为最多最近 1000 条，token 原值不导出”。
7. **备份**：TechSpec 原写“deploy/备份/cron 全自动化”与数据库文档“备份尚未自动化”冲突；统一为“备份/PITR 待配置，是上线阻塞项”。
8. **PRD UI 基准**：明确生产前端已迁到 `apps/mobile/`，旧 `jieqiu-app/index.html` 只是设计参考。
9. **ADR 状态**：ADR-0001/0002/0003 增加实现状态注记（目录未迁、Postgres CI/OpenAPI diff 未接）。
10. **Auth 默认**：文档明确 `JQ_ENV=dev|test` 才允许 stub；staging/prod 未配置真实通道时 503 fail-closed。

## 新增文档

- [docs/README.md](../README.md)：统一文档索引、事实基线、历史材料边界。
- [docs/operations-runbook.md](../operations-runbook.md)：当前部署、环境变量、cron、健康检查、控制台、回滚、事故排查。
- 本记录。

## 保留的历史文档

- `docs/reviews/2026-11-04-api-audit.md`：历史 173/92；顶部已加“历史快照”横幅。
- `docs/reviews/2026-11-04-database.md`：历史 166。
- `docs/reviews/2026-11-04-mobile-frontend.md`：历史 159/161。
- `docs/reviews/2026-11-04-monorepo-base-review.md`：历史 71 路径。
- `archive/`、`w1-validation/`：不修改结论，只通过索引标明历史属性。

## 校验

- 现行 Markdown 相对链接：0 缺失。
- 代码围栏：无奇数围栏。
- 当时事实与代码一致：OpenAPI 94/107、Alembic head `20261104_03`、后端 179、前端 20、Android bundle 3.6 MB。

## 仍待后续更新

- 真实 Postgres/备份/PITR 执行后，更新数据库文档的“已验证”状态。
- 接入真实 JPush/支付/OCR/合规服务端后，更新对应“未接”标记。
- W8 冻结基线每次新增路由后重新采纳，并同步文档中的基线说明。
- `archive/` 不参与当前事实，不应作为开发依据。
