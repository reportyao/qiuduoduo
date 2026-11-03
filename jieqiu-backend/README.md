# 解球后端 · W5 认证已上线（W8 冻结基线需随 API 变更重新采纳）

认证（方案 B·自建）：
`/auth/sms/send|verify`（CN 手机号）· `/auth/wechat/callback|bind-phone`（微信后强制绑手机）·
`/auth/email/send|verify`（GL）· `/auth/oauth/google|apple`（GL）· `/auth/refresh|logout` ·
`/auth/providers?region=`（登录页清单）。JWT access 15min + refresh 30d（轮换+复用检测→撤销家族）；
验证码 6 位/HMAC/5min/5 次/单次消费；同目标 60s + 10 条/日。生产缺真实通道时 503 fail-loud。

---

# 2026-11-04 API 补全（当前 92 路径 / 105 方法）

补齐 Feature-API-Mapping 中有数据支撑但未暴露的接口：`/matches`、`/verdicts/today`、
`/matches/{id}/cost|evidence|live`、`/avoid-list`、`/water-rank`、`/calendar`、`/sp/movements`、
`/agents/sentinel/feed`、`/me/comfort`、`/verdicts/{id}/react`、`/share/card`，以及
`/devices`、`/push/preferences|health`、`/matches/{id}/follow`、`/memories`、`/me/persona` 兼容别名。
完整对账与未实现项见 [docs/reviews/2026-11-04-api-audit.md](../docs/reviews/2026-11-04-api-audit.md)。

> **W8 冻结纪律**：新增路由后需用控制台登录调用 `POST /review/freeze/adopt` 重新采纳基线，
> 否则 `/review/freeze` 会把本次新增路由报为违规。这是预期行为，不是运行时 bug。

---

# 解球后端 · W8（提审基建）

W8 提审基建：`/review/checklist` 提审检查单（自动聚合）· `/review/banned-words/scan` 即席文案扫描 · `/legal/disclosure` 隐私+SDK+权限契约 · `/app/version` OTA · `/review/freeze` 功能冻结（基线以最近一次 `/review/freeze/adopt` 为准，新增即违规）。禁用词 21 词表 + 反空格/标点/全角绕过，后端库扫描零命中。

---

# 解球后端 · W7

FastAPI 模块化单体。W2-W4：流/判决三关/封存链/账本/叙述/校准。W6：用户域（保护/归因/记忆/路由）。**W7：F20 分享体系 · F18 双区域 · 数据导出 · 注销清除**。

## W7 交付

| 端点 | 功能 |
|---|---|
| `POST /share/verdict/{id}?persona=` | 判决分享卡（公开） |
| `POST /share/weekly` / `/share/streak` | 周报卡 / 连败卡（需登录） |
| `GET /share/{share_id}` | **编号可验**：content_hash = sha256(payload)，编号 = hash 前 12 位；篡改即暴露；幂等（同内容同编号）；深链 `jieqiu://share/{id}` |
| `GET /shares/mine` | 我的分享列表 |
| `GET /me/market-profile` | **F18** 双区域配置（cn：CNY/热线/18+中文；global：USD/BeGambleAware） |
| `GET /me/export` | 全量数据导出（JSON；设备令牌绝不导出） |
| `python -m app.purge_cli` | 注销期满（7 天）清除：用户+bets/memories/shares；每日 03:00 cron |

登录分流：`POST /auth/device` 带 `region: cn|global`（非法 422）。

## API 全景（33 端点）· 测试 99

## 运行

```bash
pip install -r requirements.txt
JQ_DB_STATEMENT_TIMEOUT_MS=0 python -m app.seed ../sp-collector/sp_data.db   # 批量导入；放宽 API 的 15s 超时
JQ_DB_STATEMENT_TIMEOUT_MS=0 python -m app.backtest_cli   # 校准回测（批量）
JQ_DB_STATEMENT_TIMEOUT_MS=0 python -m app.purge_cli        # 注销期满清除
uvicorn app.main:app --port 8100
```

## 部署

```bash
# 密码不再写进代码；部署前导出
export JQ_DEPLOY_PASSWORD='...'
export JQ_CONSOLE_PASSWORD='...'
# 可选：切自建 Postgres（不设则继续旧 SQLite）
export JQ_PROD_DATABASE_URL='postgresql+psycopg2://jieqiu:...@10.0.0.5:5432/jieqiu'

python deploy.py   # VPS：数据代码分离；cron：同步/回测/purge/助理 worker/每周日数据保留
```

---

## 数据库（自建 PostgreSQL，非 Supabase）

生产目标：腾讯云 CVM 上自建 PostgreSQL 16；SQLite 只用于单元测试/一次性工具。
完整架构、索引、连接池、备份、容量与切换步骤见
[docs/database-architecture.md](../docs/database-architecture.md)。

```bash
# 本地 Postgres（端口 5433）
docker compose up -d postgres

# 迁移（空库）
cd jieqiu-backend
python -m alembic upgrade head
python -m alembic check

# 保留策略：默认 dry-run，--apply 才删
python -m app.db_maint --json
JQ_DB_STATEMENT_TIMEOUT_MS=0 python -m app.db_maint --apply --json

# 健康检查：默认轻量；?detailed=1 才做全表计数
curl -s 'http://127.0.0.1:8100/health?detailed=1'
```

部署时设置 `JQ_PROD_DATABASE_URL=postgresql+psycopg2://...`，`deploy.py` 会上传
`alembic.ini`/`migrations/` 并在 Postgres 模式下先执行 `alembic upgrade head`。
