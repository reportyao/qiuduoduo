# 球多多后端 · W8 + Assistant（当前实现；W8 冻结基线需随 API 变更重新采纳）

认证（方案 B·自建）：
`/auth/sms/send|verify`（CN 手机号）· `/auth/wechat/callback|bind-phone`（微信后强制绑手机）·
`/auth/email/send|verify`（GL）· `/auth/oauth/google|apple`（GL）· `/auth/refresh|logout` ·
`/auth/providers?region=`（登录页清单）。JWT access 15min + refresh 30d（轮换+复用检测→撤销家族）；
验证码 6 位/HMAC/5min/5 次/单次消费；同目标 60s + 10 条/日。生产缺真实通道时 503 fail-loud。

---

# 2026-11-04 API 补全（当前 128 路径 / 143 方法）

补齐 Feature-API-Mapping 中有数据支撑但未暴露的接口：`/matches`、`/verdicts/today`、
`/matches/{id}/cost|evidence|live`、`/avoid-list`、`/water-rank`、`/calendar`、`/sp/movements`、
`/agents/sentinel/feed`、`/me/comfort`、`/verdicts/{id}/react`、`/share/card`，以及
`/devices`、`/push/preferences|health`、`/matches/{id}/follow`、`/memories`、`/me/persona` 兼容别名。
完整对账与未实现项见 [docs/reviews/2026-11-04-api-audit.md](../docs/reviews/2026-11-04-api-audit.md)。

**聚焦决策流（前后端已接通）**：`GET /stats/pulse`、`GET /matches/{id}/focus`、`POST /interactions`，以及 `interaction_events` 表；`GET /matches/on-sale` 已带逐场 `coverage`。移动端首页已接真实脉搏/聚焦面板/覆盖筛选与最小互动埋点；管理后台 `/admin`（数据源/运维/模型用量/人设文案/推荐主链/组合预览）已接入。`intel_items`/`match_coverage`/`pulse_daily` 仍是后续表。

**串关四维体检（已实现）**：`POST /tools/parlay/check`，2–4 腿返回成本/信息/模型/结构、逐腿 facts/coverage/unknowns、组合模型概率（仅全腿覆盖时）、风险与结构优化项；移动端串关页已接入，缺模型不伪造组合概率。

**推荐主链（已实现）**：`decision_snapshots` + `recommendation_plans` + `review_runs` + `recommendation_events`；build → L1–L5 复核（L1 含 24h 数据新鲜度、L2 含来源哈希校验）→ publish → expire/withdraw。`GET /recommendations/today` 只返回 published 且未过期；公开契约带方向/把握度/成立条件/失效条件/AI 复核徽章。`POST /tools/parlay/plan` 仍是**未复核预览**（UI 标注"参考·未复核"），组合页 published 优先、preview 回退。付费/权益待做。见 [docs/recommendation-product.md](../docs/recommendation-product.md)。

**合规闭环（已实现）**：`GET /compliance/state` · `POST /gate/verify`（年龄门）· `POST /me/under18-lock` · `POST /compliance/self-exclusion` · `POST /compliance/self-assessment`。`users` 表新增合规列（迁移 `20261105_12`）；`POST /bets` 与 focus capabilities 服务端硬拦截未成年锁定（403）/自排除（423）/休息中（423），重装/换设备不能绕过。

**API-Football（已接入，默认关闭）**：fixtures/lineups/injuries/standings 同步、免费额度持久化、队名/开赛时间自动链接与后台人工链接；未配置 `JQ_API_FOOTBALL_KEY` 时保持 missing，不伪造；配置了 key 的部署会自动安装每日 fixtures cron。见 [docs/api-football.md](../docs/api-football.md)。

**LLM Gateway Phase 1（已实现）**：`open_chat` fallback → fast，`llm_usage`/`llm_cache`/`llm_budgets`、原子预算、PII 脱敏与 `/admin` 模型用量页只读看板；deep 分析与 focus 解读待 Phase 2。见 [docs/llm-gateway.md](../docs/llm-gateway.md)。当前 OpenAPI 为 128/143。

**管理后台（`/admin`，已上线）**：旧 `/console/*` 全部 302 到 `/admin`，W8 `/review/*` 也改用 `admin_t` 会话。
- 认证/RBAC：`admin_users` + PBKDF2；`viewer` 只读 / `operator` 可复核发布 / `admin` 可改模型/人设/账号；登录 5 次失败锁 10 分钟。
- CSRF：写操作强制 `admin_csrf` cookie + `X-CSRF-Token`；改角色/停用/改密/删除会撤销该账号全部会话。
- 审计：`admin_audit` 记录登录/失败登录/登出/模型/人设/推荐/账号/冻结采纳，含 before/after/IP。
- 推荐主链页：运行主链、逐条/批量复核、发布、撤回（填理由）、plan 级操作、offset 分页；GET 只读，过期由 cron 处理。
- 页面：总览/模型池/用量/人设文案/推荐主链/组合预览/数据源/运维/账号/审计/日志。

> **W8 冻结纪律**：新增路由后需登录 `/admin` 调用 `POST /review/freeze/adopt` 重新采纳基线，
> 否则 `/review/freeze` 会把本次新增路由报为违规。这是预期行为，不是运行时 bug。当前基线 145 路由。

---

# 球多多后端 · W8（提审基建）

W8 提审基建：`/review/checklist` 提审检查单（自动聚合）· `/review/banned-words/scan` 即席文案扫描 · `/legal/disclosure` 隐私+SDK+权限契约 · `/app/version` OTA · `/review/freeze` 功能冻结（基线以最近一次 `/review/freeze/adopt` 为准，新增即违规）。禁用词 21 词表 + 反空格/标点/全角绕过，后端库扫描零命中。

---

# 球多多后端 · W7

FastAPI 模块化单体。W2-W4：流/判决三关/封存链/账本/叙述/校准。W6：用户域（保护/归因/记忆/路由）。**W7：F20 分享体系 · F18 双区域 · 数据导出 · 注销清除**。

## W7 交付

| 端点 | 功能 |
|---|---|
| `POST /share/verdict/{id}?persona=` | 判决分享卡（公开） |
| `POST /share/weekly` / `/share/streak` | 周报卡 / 连败卡（需登录） |
| `GET /share/{share_id}` | **编号可验**：content_hash = sha256(payload)，编号 = hash 前 12 位；篡改即暴露；幂等（同内容同编号）；深链 `jieqiu://share/{id}` |
| `GET /s/{share_id}` | 公开 HTTPS 分享落地页；无 App 也能查看/核验 |
| `GET /shares/mine` | 我的分享列表 |
| `GET /me/market-profile` | **F18** 双区域配置（cn：CNY/热线/18+中文；global：USD/BeGambleAware） |
| `GET /me/export` | 用户数据导出（JSON；设备/推送 token 原值绝不导出；通知/行为事件最多最近 1000 条） |
| `python -m app.purge_cli` | 注销期满（7 天）清除：用户+bets/memories/shares；每日 03:00 cron |

登录分流：`POST /auth/device` 带 `region: cn|global`（非法 422）。

## API 全景（128 路径 / 143 方法）· 测试 251

W8 + assistant 的实际契约以 `packages/api-client/openapi.json` 为准；新增目录/成本/日历/哨兵/实况与兼容别名见上节。

## 运行

```bash
pip install -r requirements.txt
JQ_DB_STATEMENT_TIMEOUT_MS=0 python -m app.seed ../sp-collector/sp_data.db   # 批量导入；放宽 API 的 15s 超时
JQ_DB_STATEMENT_TIMEOUT_MS=0 python -m app.backtest_cli   # 校准回测（批量）
JQ_DB_STATEMENT_TIMEOUT_MS=0 python -m app.purge_cli        # 注销期满清除
python -m app.odds_cli status        # 内容供给诊断：国际盘/市闸/published 卡在哪
python -m app.odds_cli sync          # 手动同步国际盘（需 JQ_ODDS_API_KEY）
uvicorn app.main:app --port 8100
```

## 部署

```bash
# 密码不再写进代码；部署前导出
export JQ_DEPLOY_PASSWORD='...'
export JQ_ADMIN_PASSWORD='...'          # /admin 初始管理员密码
export JQ_ADMIN_COOKIE_SECURE=true      # HTTPS 部署建议开启
# 可选：切境内 Postgres（云托管优先 / 自建兜底；不设则继续旧 SQLite）
export JQ_PROD_DATABASE_URL='postgresql+psycopg2://jieqiu:...@10.0.0.5:5432/jieqiu'
# 说明：deploy.py 读取 JQ_PROD_DATABASE_URL，写入服务的 JQ_DATABASE_URL；本地直接运行只认 JQ_DATABASE_URL。

python deploy.py   # VPS：数据代码分离；cron：同步/回测/purge/助理 worker/人设预生成/每周日数据保留
```

生产认证默认 fail-closed：`deploy.py` 写入 `JQ_ENV=prod`、`JQ_AUTH_STUB=false`；未配置真实短信/邮件/OAuth 时认证端点返回 503，不会再回显 `dev_code`。管理员初始密码/JWT 密钥写入 `/etc/jieqiu-backend.env`（0600），unit 只引用 EnvironmentFile。

---

## 数据库（境内 PostgreSQL：云托管优先 / 自建兜底，非 Supabase）

生产目标：境内 PostgreSQL 16，首选云托管（腾讯云数据库 PG / TDSQL-C），纯自建（CVM + 云盘）作低成本兜底（ADR-0004）；SQLite 只用于单元测试/一次性工具。
完整架构、选型对比、索引、连接池、备份/PITR 落地步骤、容量与切换见
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

## 文档入口

- 全栈深审与残余风险：[docs/reviews/2026-11-04-full-stack.md](../docs/reviews/2026-11-04-full-stack.md)
- API 对账：[docs/reviews/2026-11-04-api-audit.md](../docs/reviews/2026-11-04-api-audit.md)
- 数据库：[docs/database-architecture.md](../docs/database-architecture.md)
- 前端交接：[apps/mobile/ARCHITECTURE.md](../apps/mobile/ARCHITECTURE.md)
