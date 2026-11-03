# 解球 · 数据库架构（自建 PostgreSQL）

> 状态：生产目标架构。**不使用 Supabase**，也不依赖任何托管 BaaS。主库是自建 PostgreSQL 16（腾讯云 CVM + Docker volume / 云硬盘），SQLite 只用于纯单元测试和一次性本地工具。

## 1. 拓扑

```text
Android / iOS (Expo)  ──HTTPS──►  FastAPI (systemd/uvicorn)
                                      │
                                      ├─ SQLAlchemy 2.x 同步连接池
                                      ▼
                             自建 PostgreSQL 16
                             ├─ 主库（读写）
                             ├─ 每日 pg_dump -Fc（对象存储/异机）
                             ├─ WAL 归档 → PITR（上线前补齐）
                             └─ 只读副本（规模上来后）
```

- 应用与数据库在同一 VPC；5432 **不暴露公网**，安全组只放应用机内网 IP。
- 迁移由一个受控进程执行（`alembic upgrade head`），不由每个 API worker 各自执行。
- 当前单机足够 MVP；多 API 实例时在应用与 Postgres 之间加 PgBouncer，或提高 `max_connections` 并缩小每个实例的连接池。

## 2. 为什么是自建 Postgres，而不是 Supabase

| 维度 | 自建 Postgres | Supabase |
|---|---|---|
| 数据位置 | 腾讯云中国境内外可控 | 海外托管为主，跨境/合规复杂 |
| 成本 | CVM + 云盘，可预算 | 订阅 + 用量，增长后不可控 |
| 连接 | 内网直连，低延迟 | 受网络与连接池限制 |
| 自主性 | 版本、备份、扩展、审计全可控 | 受平台版本和策略约束 |
| 迁移 | 标准 `pg_dump` / 逻辑复制 | 平台锁定风险 |

本项目选择自建，数据库代码保持标准 PostgreSQL，不写任何 Supabase 专有 API。

## 3. 连接与事务

`app/db.py`：

- Postgres 使用 `QueuePool`：`pool_size=10`、`max_overflow=20`、`pool_timeout=30s`、`pool_recycle=1800s`、`pool_pre_ping=True`。
- 连接级 `statement_timeout=15000ms`、`lock_timeout=5000ms`、`application_name=jieqiu-api`，避免慢查询/锁等待拖垮 API。
- SQLite 使用 `NullPool` + WAL + `busy_timeout=5000`，仅测试/本地。
- `get_db()` 捕获异常先 `rollback()` 再关闭，失败事务不会带着脏连接回到池。
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
| `ix_verdicts_status_settled_kickoff` | verdicts | 结算扫描 / 公开账本 |
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

原则：**先有查询再有索引**。没有出现在 `EXPLAIN` 热路径里的索引不加；新增索引必须同时出现在 ORM `__table_args__` 与 Alembic migration，保证 `alembic check` 无漂移。

## 6. 数据保留

`python -m app.db_maint` 默认 dry-run；`--apply` 才删除：

| 数据 | 默认保留 | 原因 |
|---|---|---|
| 已扇出 events | 90 天 | 通知内容已落 notifications；事件本身可回收 |
| 已送达/失败 notifications | 180 天 | 收件箱历史 |
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

建议低峰执行：

```bash
cd jieqiu-backend
python -m app.db_maint --json            # 先看将删多少
JQ_DB_STATEMENT_TIMEOUT_MS=0 python -m app.db_maint --apply --json  # 备份后执行；批量删除放宽超时
```

规模再上一个量级时，优先把 `sp_snapshots` / `events` / `notifications` 按月分区（Postgres declarative partitioning），再做归档表；当前不做分区，避免过早复杂化。

## 7. 备份 / 恢复 / 迁移

### 备份

```bash
# 每日 03:20，压缩自定义格式
pg_dump -Fc -h 127.0.0.1 -U jieqiu -d jieqiu -f /backup/jieqiu-$(date +%F).dump
# 校验
pg_restore --list /backup/jieqiu-2026-11-04.dump | head
```

- 保留 14 天日备 + 每月 1 份月备；至少一份异机/对象存储。
- 上线前配置 WAL 归档（`archive_mode=on` + `archive_command`/pgBackRest），目标 RPO ≤ 5 分钟、RTO ≤ 1 小时。
- 每季度做一次恢复演练：恢复到临时库，跑 `alembic current`、关键表 count、`/health` 链路。

### SQLite → Postgres 切换

1. 停写（或进入维护窗口），备份 SQLite。
2. 建空 Postgres，`alembic upgrade head`。
3. 用一次性导入脚本按表迁数据（先父表后子表；或 `pgloader`）。
4. 校验行数、`payload_hash`、`bets.sp`、`users.phone/email` 唯一。
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
- 密码只放 systemd EnvironmentFile/密钥管理，不进仓库；`.env` 已 gitignore。
- 只允许 VPC 内网；开启云盘加密与备份加密；审计登录与 DDL。
- `statement_timeout`/`lock_timeout` 已在连接级配置；慢查询不会无限占用连接。

## 11. 当前迁移版本

```text
71af760b1e99  baseline W8（24 表）
20261104_02   bets.sp 赔率快照（正确 P&L）
20261104_03   热路径索引 + 手机/邮箱部分唯一索引
```

验证命令：

```bash
cd jieqiu-backend
python -m alembic upgrade head
python -m alembic check
python -m app.db_maint --json
```
