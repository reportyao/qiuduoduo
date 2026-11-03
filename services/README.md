# services/

后端最终迁移目标。

当前生产后端仍在 `jieqiu-backend/`，原因是避免在引入 Alembic/Postgres 前做一次性大迁移。

迁移顺序：

1. 完成 Alembic baseline；
2. 将 `jieqiu-backend/app` 迁到 `services/api/app`；
3. 保留 deploy/worker/cron 配置；
4. 旧目录保留一个 release 周期后删除。

禁止在迁移完成前同时维护两套后端代码。
