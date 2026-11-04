# 运维 Runbook（当前实现）

最后更新：2026-11-04。适用于当前过渡期 `jieqiu-backend/` + 单台腾讯云 VPS；目标数据库是境内 PostgreSQL 16（**云托管优先 / 自建兜底**，见 ADR-0004），未设置 `JQ_PROD_DATABASE_URL` 时仍是旧 SQLite。

## 1. 进程与目录

| 项 | 当前值 |
|---|---|
| API | `uvicorn app.main:app --host 0.0.0.0 --port 8100`（systemd `jieqiu-backend`） |
| 代码 | `/home/ubuntu/jieqiu-backend`（部署会整体替换） |
| 数据 | `/home/ubuntu/jieqiu-data`（部署不删除） |
| 采集器 | 本机家宽运行，SFTP → VPS；API 不直接访问体彩 |
| 管理后台 | 同进程 `/console`，密码 + HttpOnly cookie + 可选 IP 白名单 |

## 2. 必配环境变量

部署前在本机导出（不要写进仓库）：

```bash
export JQ_DEPLOY_HOST='43.128.24.244'
export JQ_DEPLOY_PASSWORD='...'
export JQ_CONSOLE_PASSWORD='...'
export JQ_CONSOLE_IP_WHITELIST='203.0.113.10'   # 可选，支持 CIDR
export JQ_PROD_DATABASE_URL='postgresql+psycopg2://jieqiu:...@10.0.0.5:5432/jieqiu'  # 不设则继续旧 SQLite
```

服务端 env 文件：`/etc/jieqiu-backend.env`（root:root 0600，由 `deploy.py` 写入），包含数据库 URL、JWT、控制台密码/白名单、数据路径。生产显式 `JQ_ENV=prod`、`JQ_AUTH_STUB=false`。

认证通道未配置时（短信/邮件/OAuth）认证端点返回 503；这是 fail-closed，不是服务挂了。`JQ_ENV=dev|test` 才允许 `JQ_AUTH_STUB=true`。

## 3. 部署

```bash
cd jieqiu-backend
python deploy.py
```

顺序：上传代码 → 安装依赖 → Postgres 模式先 `alembic upgrade head`（失败即停止）→ 写 env/unit → 写入 cron → seed → systemctl restart → `systemctl is-active` + `/health`。

## 4. Cron

| 时间 | 任务 |
|---|---|
| `*/30 * * * *` | `app.seed` 导入采集器快照、重建判决 |
| `10 6 * * 1` | `app.backtest_cli weekly` |
| `0 3 * * *` | `app.purge_cli`（注销冷静期满清理） |
| `* * * * *` | `app.features.assistant.worker --once`（事件/扇出/推送） |
| `10 4 * * 0` | `app.db_maint --apply`（保留策略） |

cron 中 `JQ_DB_STATEMENT_TIMEOUT_MS=0`，避免批量任务被 API 的 15s 语句超时打断。

## 5. 健康与告警

```bash
curl -s 'http://127.0.0.1:8100/health'            # 轻量：DB ping + 延迟 + 链摘要
curl -s 'http://127.0.0.1:8100/health?detailed=1' # 额外全表 count，勿给探针高频调用
```

`/console/alerts` 自动提示：封存链断裂、采集同步延迟 >35/90 分钟、无 SP 快照、the-odds-api 未配、控制台密码未设。

## 6. 控制台

- 登录：`https://<host>/console/login`（生产必须 TLS；当前 uvicorn 直连，需在反代层补 TLS）。
- 会话只走 HttpOnly cookie，不再接受/生成 `?t=` URL token；退出用 `/console/logout`。
- 新增路由后：登录控制台调用 `POST /review/freeze/adopt` 重新采纳基线，否则 `/review/freeze` 会报新增违规。
- 多 worker 时 `_SESSIONS`/`_VARIANT_POOL` 是进程内存，需要 Redis/DB 会话后才能横向扩展。

## 7. 数据库

Postgres 模式：

```bash
cd jieqiu-backend
python -m alembic upgrade head
python -m alembic check
python -m app.db_maint --json              # dry-run
JQ_DB_STATEMENT_TIMEOUT_MS=0 python -m app.db_maint --apply --json
```

备份/PITR **尚未自动化，是上线阻塞项**：云托管形态在控制台开启自动备份 + 按时间点回档；自建形态按 [database-architecture.md §7](./database-architecture.md) 的落地步骤配置 `pg_backup.sh` + cron + WAL 归档。**两种形态都必须做一次恢复演练**。选型见 [ADR-0004](./decisions/0004-managed-postgres-preferred.md)。

## 8. 回滚

- 代码：保留上一 release 目录/包，systemd 指向旧目录或重新部署上一版本。
- 数据库：迁移必须可 downgrade；执行前备份。Postgres 切回 SQLite 仅作为短期只读回滚，不要双写。
- 配置：`/etc/jieqiu-backend.env` 变更前备份；JWT 密钥变更会使现有 access token 失效（refresh 也会失败），需接受重新登录。
- 推送：JPush 未配置时 worker dry-run；配置错误不会阻塞判决发布。

## 9. 事故排查顺序

1. `/health` 是否 200、DB latency、chain 是否 BROKEN；
2. `/console/alerts` 同步延迟/快照；
3. `systemctl status jieqiu-backend`、`journalctl -u jieqiu-backend -n 200`；
4. cron 日志：`sync.log`、`backtest.log`、`purge.log`、`assistant.log`、`db_maint.log`；
5. Postgres：`pg_stat_activity`、锁等待、`pg_stat_statements`；
6. 封存链：`/chain/verify?date=...`、`/anchor/latest`；
7. 推送：`/console/push`、`/push/health`、worker 日志。

## 10. 明确未完成

- TLS/反代、控制台 CSRF token、多进程会话；
- 备份/PITR 自动化；
- 真实 JPush、支付、OCR、服务端合规同步、真实 live feed；
- 真实 Android APK / iOS 原生构建验收。
