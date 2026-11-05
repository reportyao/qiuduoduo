# services/

后端最终迁移目标。

当前生产后端仍在 `jieqiu-backend/`；Alembic/Postgres 基座已具备，目录迁移尚未执行，避免在功能迭代期做一次性大迁移。

迁移顺序：

1. ~~完成 Alembic baseline~~ **已完成**：baseline `71af760b1e99` 覆盖 W8 时点 24 张表；后续 `20261104_02`–`20261105_12` 增加注单赔率快照、热路径索引、结算索引、interaction_events、API-Football 5 表、LLM 3 表、人设 4 表、推荐主链 4 表、管理账号/审计 2 表。当前 head 为 `20261105_12`，ORM 共 43 张表；已在空库验证 `upgrade head`、`downgrade base` 往返与 `alembic check`；
2. 将 `jieqiu-backend/app` 迁到 `services/api/app`；
3. 保留 deploy/worker/cron 配置；
4. 旧目录保留一个 release 周期后删除。

数据库架构与索引/保留/备份方案见 [docs/database-architecture.md](../docs/database-architecture.md)。

切换 Postgres 时注意：**Postgres 方言下应用启动不再 `create_all`/`ALTER`**（`init_db()` 直接返回），schema 只由 `python -m alembic upgrade head` 管理，必须先迁移再启动 API。已有表但没有 `alembic_version` 的旧库，先在临时库核对 schema 后再决定 `stamp`，禁止对已有表直接跑 baseline。

禁止在迁移完成前同时维护两套后端代码。

当前实现事实（2026-11-05）：

- 运行目录仍是 `jieqiu-backend/`；`services/api/` 是迁移目标，不是当前生产路径。
- OpenAPI 128 路径 / 143 方法；后端测试 260；Alembic head `20261105_12`。
- 生产默认切 Postgres 仍需设置 `JQ_PROD_DATABASE_URL`；未设置时是旧 SQLite 兼容模式。
- 全栈深审记录（历史快照）：[docs/reviews/2026-11-04-full-stack.md](../docs/reviews/2026-11-04-full-stack.md)。
