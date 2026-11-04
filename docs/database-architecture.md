# 解球 · 数据库架构（境内 PostgreSQL：云托管优先 / 自建兜底）

> 状态：生产目标架构。**不使用 Supabase**，也不依赖任何托管 BaaS。主库是境内 PostgreSQL 16，**首选云托管（腾讯云数据库 PG / TDSQL-C），纯自建（CVM + 云盘）作为低成本兜底**；SQLite 只用于纯单元测试、一次性本地工具，以及尚未切换的旧部署回退。
>
> 选型决策：[ADR-0004](decisions/0004-managed-postgres-preferred.md)。深审记录：[docs/reviews/2026-11-04-database.md](reviews/2026-11-04-database.md)。

## 1. 拓扑

```text
Android / iOS (Expo)  ──HTTPS──►  FastAPI (systemd/uvicorn)
                                      │
                                      ├─ SQLAlchemy 2.x 同步连接池
                                      ▼
                             境内 PostgreSQL 16（云托管优先 / 自建兜底）
                             ├─ 主库（读写）
                             ├─ 备份：云托管自动备份+PITR / 自建 pg_dump（§7 落地步骤，尚未运行）
                             ├─ WAL 归档 → PITR（自建形态按 §7 配置；云托管由平台提供）
                             └─ 只读副本（规模上来后）
```

- 应用与数据库在同一 VPC；5432 **不暴露公网**，安全组只放应用机内网 IP。云托管形态用内网地址连接，同样不开公网。
- 迁移由一个受控进程执行（`alembic upgrade head`），不由每个 API worker 各自执行。
- 当前单机足够 MVP；多 API 实例时在应用与 Postgres 之间加 PgBouncer，或提高 `max_connections` 并缩小每个实例的连接池。

## 2. 选型决策：境内 PostgreSQL，云托管优先 / 自建兜底，不用 Supabase

> 正式决策记录见 [ADR-0004](decisions/0004-managed-postgres-preferred.md)。本节是结论与对比；代码保持标准 PostgreSQL，不写任何 Supabase / 云厂商专有 API。

三条候选路线对比：

| 维度 | 云托管 Postgres（腾讯云数据库 PG / TDSQL-C） | 纯自建 Postgres（CVM + 云盘） | Supabase |
|---|---|---|---|
| 数据位置 / 合规 | 境内节点，数据不出境 | 境内节点，数据不出境 | **无中国大陆节点**，跨境 + PIPL 出境评估 |
| CN 用户延迟 | 同 VPC 内网，低 | 同机 / 同 VPC，最低 | 跨境约 150–300ms |
| 备份 / PITR / 高可用 | 平台托管，自动 | 全自己搭（**当前缺口**） | 平台托管（付费档） |
| 运维负担 | 低 | 高 | 低 |
| 成本 | 几十~几百/月，可预算 | 含在 CVM，最省 | 免费层有限，用量增长不可控 |
| 控制权 / 扩展 | 受限但够用，标准 PG | 完全可控 | 受限 + 平台锁定 |
| 迁移自由度 | 标准 PG，随时 `pg_dump` 迁走 | 标准 PG | PostgREST / RLS / Auth / SDK 锁定 |
| 与现有栈契合 | 无缝（换 `JQ_DATABASE_URL` 即可） | 无缝 | 需引入 SDK / RLS，和 FastAPI 冲突 |

**决策**：

1. **首选云托管 Postgres**（腾讯云数据库 PostgreSQL / TDSQL-C）：保留境内 + 标准 PG + 无 BaaS 锁定的全部优点，把备份 / PITR / 主备切换 / 监控交给云厂商——正好补上纯自建当前最大的运维缺口。对单人 OPC、不想半夜处理备份 / 故障切换的场景，这是更稳的默认。
2. **纯自建作为低成本兜底**：预算极紧或需要完全控制（自定义扩展 / 参数）时用；但**必须先把 §7 的备份 / PITR 落地**，否则等于承担自建风险却没拿到可靠性，不允许上生产。
3. **不用 Supabase**：无中国大陆节点（延迟 + 数据出境双重问题）、内置 Auth 不贴合中国手机号 / 微信、PostgREST / SDK 与现有 FastAPI + OpenAPI codegen 重复且冲突、用量成本不可控。

**不变量**：无论云托管还是自建，都是标准 PostgreSQL 16；连接只走 `JQ_DATABASE_URL`，schema 只走 Alembic。**切换形态不改一行业务代码**（云托管 ↔ 自建只是换连接串 + 运维责任归属）。

## 3. 连接与事务

`app/db.py`：

- Postgres 使用 `QueuePool`：`pool_size=10`、`max_overflow=20`、`pool_timeout=30s`、`pool_recycle=1800s`、`pool_pre_ping=True`。
- 连接级 `statement_timeout=15000ms`、`lock_timeout=5000ms`、`application_name=jieqiu-api`，避免慢查询/锁等待拖垮 API。
- SQLite 使用 `NullPool` + WAL + `busy_timeout=5000`，仅测试/本地以及尚未切换的旧部署。
- `get_db()` 捕获异常先 `rollback()` 再关闭，失败事务不会带着脏连接回到池。
- **生产 Postgres 启动不跑 `create_all`/`ALTER`**：`init_db()` 在 Postgres 方言下直接返回，schema 只由部署阶段的 `alembic upgrade head` 管理，避免多 worker 并发 DDL 和绕过迁移审计。SQLite（本地/测试/尚未切换的旧部署）仍保留 `init_db()` 兼容旧库；旧 SQLite 表已存在时，`init_db()` 还会补建模型里新增、但 `create_all` 不会自动补的索引。
- **Alembic 迁移连接**用 `NullPool` + `application_name=jieqiu-migrate`；`statement_timeout=0`（大表建索引不被 API 的 15s 超时打断），`lock_timeout` 仍取 5s，避免长时间排队锁。
- 所有时间列统一 **naive UTC**（`models.utcnow()` 去 tzinfo）；竞彩业务时间（开赛/停售/trade_date）用中国时间字符串。两者不混用。

连接数估算：

```text
总连接 ≈ API 实例数 × (pool_size + max_overflow) + worker 数 + 运维连接
单实例上限 30；4 个 API 实例 = 120，仍在 Postgres 默认 100 以上需调 max_connections 或上 PgBouncer。
```

## 4. 表与职责

| 域 | 表 | 说明 |
|---|---|---|
| 赛事/赔率 | `sp_matches` / `sp_snapshots` | 官方在售场次与 SP 追加快照 |
| 对齐 | `team_aliases` | 队名归一化 |
| 判决 | `verdicts` | 赛前封存结论、三关、概率、结算 |
| 修订/链 | `verdict_revisions` / `daily_anchors` | 追加式修订、跨日锚 |
| 赛果 | `match_results` | 结算输入 |
| 模型 | `model_runs` / `model_evals` | 每场每闸审计日志；评估结果 |
| 用户 | `users` | 设备/JWT 账户、偏好、注销冷静期 |
| 认证 | `auth_identities` / `verification_codes` / `refresh_tokens` | 自建认证，不依赖第三方用户表 |
| 注单 | `bets` | 金额 + 下注时赔率快照 `sp` |
| 记忆/关注 | `memories` / `watch_targets` | 用户私有数据 |
| 助理 | `events` / `notifications` / `push_tokens` / `notify_settings` / `user_events` / `assistant_state` | 事件→扇出→站内信/推送 |
| 分享 | `share_cards` | 分享内容哈希，可独立验真 |

**刻意不做外键级联**：用户注销采用 7 天冷静期 + `purge_cli` 显式清理；判决/事件/分享是审计资产，不能被一次级联误删。唯一性由 `UNIQUE` 索引保证，跨表一致性由 service 层事务保证。

## 5. 索引设计与热路径

新增迁移：`20261104_03_hot_path_indexes.py`。

| 索引 | 表 | 服务的查询 |
|---|---|---|
| `ix_verdicts_trade_status_rake` | verdicts | 判决流按日期 + 状态 + 抽水排序 |
| `ix_verdicts_match_trade` | verdicts | 一场比赛跨竞彩日的最新判决回退 |
| `ix_verdicts_trade_kickoff` | verdicts | 公开账本按日期 + 开赛时间 |
| `ix_verdicts_status_settled_kickoff` | verdicts | 已推判决按开赛时间（结算/复盘） |
| `ix_verdict_revisions_verdict_created` | revisions | 封存页取修订史 |
| `ix_bets_user_created` | bets | 我的票单 / 周报 |
| `ix_notifications_user_channel_opened` | notifications | 收件箱未读 |
| `ix_notifications_status_scheduled` | notifications | worker 取待发送 |
| `ix_events_pending` | events | worker 取未扇出事件 |
| `ix_events_type_created` | events | 事件按类型排查 |
| `ix_watch_targets_type_target` | watch_targets | 事件按比赛找关注者 |
| `ix_user_events_user_created` | user_events | 用户行为时间线 |
| `ix_model_runs_match_date_gate` | model_runs | 分析日志按场/日/闸 |
| `ix_verification_codes_target_purpose_expires` | codes | 验证码校验/限流 |
| `ix_refresh_tokens_user_revoked` | refresh_tokens | 登出/复用检测 |
| `ix_refresh_tokens_expires_at` | refresh_tokens | 过期清理 |
| `uq_users_phone` / `uq_users_email` | users | 手机/邮箱唯一；Postgres 部分唯一索引，NULL 不参与 |

原则：**先有查询再有索引**。没有出现在 `EXPLAIN` 热路径里的索引不加；新增索引必须同时出现在 ORM `__table_args__` 与 Alembic migration，保证 `alembic check` 无漂移。Postgres 由 Alembic 建索引；旧 SQLite 由 `init_db()` 的 `_ensure_indexes()` 补建（`create_all` 对已存在表不会补索引）。

## 6. 数据保留

`python -m app.db_maint` 默认 dry-run；`--apply` 才删除：

| 数据 | 默认保留 | 原因 |
|---|---|---|
| 已扇出/已过期 events | 90 天 | 通知内容已落 notifications；事件本身可回收；未扇出且未过期的事件保留；仍被 notification 引用的 event 延后到引用清掉后的下一轮 |
| 已送达/失败/被抑制 notifications | 180 天 | 收件箱历史 |
| model_runs | 365 天 | 复盘/审计一年 |
| user_events | 180 天 | 行为信号 |
| verification_codes | 7 天 | 已过期验证码 |
| refresh_tokens | 过期即删 | 安全与体积 |

**永不自动删除**：verdicts / verdict_revisions / daily_anchors / bets / share_cards / sp_snapshots。判决与账本是产品承诺，SP 快照是模型和滞后验证的数据底座。

**当前刻意不入库**：

- 自排除/PGSI 自评：前端本机强制拦截（`compliance` 本地存储），服务端合规表和接口尚未实现；已登录时会尝试暂停服务端通知。多设备同步是上线前阻塞项。
- 个人头像：本机 `documentDirectory`，不上传、不入库。
- 串关体检/赔率/仓位/回本线：纯本地计算，无 `parlay_reports` 等服务端表。
- 订阅/支付：尚未接入，不建空表，避免出现与接口不一致的“假 schema”。

部署 cron 默认每周日 04:10 执行 `--apply`（日志 `db_maint.log`）。手动演练先 dry-run：

```bash
cd jieqiu-backend
python -m app.db_maint --json            # 先看将删多少
JQ_DB_STATEMENT_TIMEOUT_MS=0 python -m app.db_maint --apply --json  # 备份后执行；批量删除放宽超时
```

规模再上一个量级时，优先把 `sp_snapshots` / `events` / `notifications` 按月分区（Postgres declarative partitioning），再做归档表；当前不做分区，避免过早复杂化。

## 7. 备份 / 恢复 / 迁移

### 备份 / PITR 落地步骤（部署时执行；当前尚未运行）

> **云托管形态**：备份 / PITR / 主备由控制台开启即可（腾讯云数据库 PG 默认自动备份 + 按时间点回档），下面第 1–4 步的手写部分主要用于**纯自建兜底**；云托管只需确认备份策略 + 异机副本 + 第 5 步恢复演练。
>
> **目标**：RPO ≤ 5 分钟、RTO ≤ 1 小时；14 天日备 + 每月 1 份月备 + 至少一份异机 / 对象存储。
> **前提**：运维机装 `postgresql-client`（`pg_dump` / `pg_restore` / `psql`），且能走内网连到主库。

**第 1 步：逻辑备份脚本**（保存为 `jieqiu-backend/ops/pg_backup.sh`，`chmod 700`）：

```bash
#!/usr/bin/env bash
set -euo pipefail
# 从 root-only env 读取连接（与 systemd 同源）；去掉 SQLAlchemy 驱动后缀
source /etc/jieqiu-backend.env
DB_URL="${JQ_DATABASE_URL/postgresql+psycopg2:/postgresql:}"
DB_URL="${DB_URL/postgres:/postgresql:}"
mkdir -p /backup
OUT="/backup/jieqiu-$(date +%F).dump"
pg_dump --dbname="$DB_URL" -Fc -f "$OUT"
pg_restore --list "$OUT" >/dev/null                    # 校验备份可读
find /backup -name 'jieqiu-*.dump' -mtime +14 -delete  # 保留 14 天
```

> 安全提示：`--dbname="$DB_URL"` 会把含密码的 URI 短暂暴露在进程列表；单机单租户风险低，多用户主机请改用 `~/.pgpass`（0600）+ `pg_dump -h ... -U ... -d ...`，不要把密码写进脚本。脚本由 root cron 执行（env 文件是 root:root 0600）。

**第 2 步：cron**（root crontab，每日 03:20，避开 03:00 purge / 周日 04:10 db_maint）：

```cron
20 3 * * * /home/ubuntu/jieqiu-backend/ops/pg_backup.sh >> /home/ubuntu/jieqiu-backend/backup.log 2>&1
```

**第 3 步：异机 / 对象存储**（至少一份离开本机；以腾讯云 COS `coscmd` 为例，也可用 rclone）：

```bash
coscmd upload "/backup/jieqiu-$(date +%F).dump" backup/jieqiu/
# 月备：每月 1 号额外拷一份到 backup/jieqiu/monthly/，不被 14 天清理删掉
```

**第 4 步：WAL 归档 → PITR**（自建 `postgresql.conf`；云托管由平台提供，跳过）：

```conf
archive_mode = on
archive_command = 'test ! -f /wal_archive/%f && cp %p /wal_archive/%f'
# 生产建议直接用 pgBackRest 管理全量+增量+WAL，替代手写 archive_command
```

配合一次基础备份即可按时间点恢复；`/wal_archive` 同样要异机。

**第 5 步：恢复演练（每季度；上线前必做一次，云托管也不可省）**：

```bash
createdb jieqiu_drill
pg_restore -d jieqiu_drill --no-owner /backup/jieqiu-YYYY-MM-DD.dump
psql jieqiu_drill -c "select count(*) from verdicts;"
JQ_DATABASE_URL=postgresql://.../jieqiu_drill python -m alembic current
# 关键表 count 与生产对齐；抽查 payload_hash / bets.sp；记录 RTO；演练库用完即删
```

**当前状态**：以上为落地步骤，**尚未配置运行**；备份 / PITR 仍是生产上线阻塞项。不要因为文档写了命令就认为已经在跑。后续可把 `pg_backup.sh` 纳入 `deploy.py` 的 cron 安装（与 `db_maint` 同批），实现部署即生效。

### SQLite → Postgres 切换

1. 停写（或进入维护窗口），备份 SQLite。
2. 建空 Postgres，`alembic upgrade head`。
3. 用一次性导入脚本按表迁数据（先父表后子表；或 `pgloader`）。
4. 校验行数、`payload_hash`、`bets.sp`、`users.phone/email` 唯一；迁移前先跑重复检查：
   `select phone, count(*) from users where phone is not null group by phone having count(*) > 1;`
   （email 同理）。部分唯一索引遇到重复行会拒绝创建，必须先人工归并，不能删数据了事。
   旧 SQLite 启动补索引时也会遇到同样的唯一冲突，升级前同样先查重。
5. 切 `JQ_DATABASE_URL`，启动 API，跑 `/health`、`/stream`、`/me/inbox`、worker `--once`。
6. 旧 SQLite 保留一个 release 周期，只读回滚。

## 8. 迁移纪律（AI 修改数据库时必须遵守）

- 只通过 Alembic 改 schema；生产禁止 `create_all` 加列。
- 先 expand（加列/加索引/双写），再 migrate，最后 contract（删旧列）；单次迁移必须可 `downgrade`。
- 大表加索引用 `CREATE INDEX CONCURRENTLY`（迁移需 `transaction_per_migration`/`autocommit_block`；执行前单独评审）。
- 迁移前必须备份；迁移脚本不得包含业务数据删除。
- ORM 与 migration 必须同源：模型 `__table_args__` 与迁移索引名/列顺序一致，`alembic check` 必须 clean。
- 新增查询先 `EXPLAIN (ANALYZE, BUFFERS)`，禁止凭感觉加索引。

## 9. 监控与容量

关键 SQL：

```sql
-- 连接使用
select state, count(*) from pg_stat_activity group by 1;
-- 慢查询（需 pg_stat_statements）
select calls, mean_exec_time, query from pg_stat_statements order by mean_exec_time desc limit 10;
-- 表膨胀/体积
select relname, n_live_tup, pg_size_pretty(pg_total_relation_size(relid))
from pg_stat_user_tables order by pg_total_relation_size(relid) desc limit 10;
-- 锁等待
select pid, wait_event_type, wait_event, query from pg_stat_activity where wait_event_type='Lock';
```

容量粗估：

- SP 快照：47 场 × 2 池 × 288 次/日 ≈ 2.7 万行/日，约 1000 万行/年；主要是数值列，索引后约 1–2 GB/年。
- 判决/修订：每日几十到几百行，年度百万级以内。
- 通知/事件：按关注量线性增长；用 90/180 天保留 + 月分区控制。
- 单机 2C4G + 100GB SSD 可承载 MVP；读多写少时先加索引/缓存，再考虑只读副本。

## 10. 安全

- 角色分离：`jieqiu_app`（DML）、`jieqiu_migrator`（DDL）、`jieqiu_readonly`（报表）；应用不使用超级用户。
- 数据库 URL/控制台密码/JWT 密钥写 `/etc/jieqiu-backend.env`（root:root 0600），systemd unit 只引用 `EnvironmentFile`，不把密钥写进 world-readable 的 unit。
- 密码只放 systemd EnvironmentFile/密钥管理，不进仓库；`.env` 已 gitignore。
- 只允许 VPC 内网；开启云盘加密与备份加密；审计登录与 DDL。
- `statement_timeout`/`lock_timeout` 已在连接级配置；慢查询不会无限占用连接。

## 11. 当前迁移版本

```text
71af760b1e99  baseline W8（24 表）
20261104_02   bets.sp 赔率快照（正确 P&L）
20261104_03   热路径索引 + 手机/邮箱部分唯一索引
20261104_04   verdicts.settled_at 索引（结算监控）
```

验证命令：

```bash
cd jieqiu-backend
python -m alembic upgrade head
python -m alembic check
python -m app.db_maint --json
```
