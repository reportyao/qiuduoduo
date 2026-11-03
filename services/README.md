# services/

后端最终迁移目标。

当前生产后端仍在 `jieqiu-backend/`，原因是避免在引入 Alembic/Postgres 前做一次性大迁移。

迁移顺序：

1. ~~完成 Alembic baseline~~ **已完成**：`migrations/versions/71af760b1e99_baseline_w8_assistant_runtime.py` 覆盖当前 24 张表，`20261104_02_bet_sp.py` 增加注单赔率快照；已在空库验证 `upgrade head` 与 `alembic check`；
2. 将 `jieqiu-backend/app` 迁到 `services/api/app`；
3. 保留 deploy/worker/cron 配置；
4. 旧目录保留一个 release 周期后删除。

数据库架构与索引/保留/备份方案见 [docs/database-architecture.md](../docs/database-architecture.md)。

切换 Postgres 时注意：应用启动会 `create_all`，所以必须先跑 `python -m alembic upgrade head` 再启动 API；已在用的库用 `alembic stamp head` 纳管，禁止直接对已有表跑 baseline。

禁止在迁移完成前同时维护两套后端代码。
