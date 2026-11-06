# 运维 Runbook（当前实现）

最后更新：2026-11-05。适用于当前过渡期 `jieqiu-backend/` + 单台腾讯云 VPS；目标数据库是境内 PostgreSQL 16（**云托管优先 / 自建兜底**，见 ADR-0004），未设置 `JQ_PROD_DATABASE_URL` 时仍是旧 SQLite。

## 1. 进程与目录

| 项 | 当前值 |
|---|---|
| API | `uvicorn app.main:app --host 0.0.0.0 --port 8100`（systemd `jieqiu-backend`） |
| 代码 | `/home/ubuntu/jieqiu-backend`（部署会整体替换） |
| 数据 | `/home/ubuntu/jieqiu-data`（部署不删除） |
| 采集器 | 本机家宽运行，SFTP → VPS；API 不直接访问体彩 |
| 管理后台 | 同进程 `/admin` + `/admin/api/*`；PBKDF2 密码、HttpOnly `admin_t`、RBAC、审计日志 |

## 2. 必配环境变量

部署前在本机导出（不要写进仓库）：

```bash
export JQ_DEPLOY_HOST='43.128.24.244'
export JQ_DEPLOY_PASSWORD='...'
export JQ_ADMIN_PASSWORD='...'          # /admin 初始 admin 密码（仅首次建号）
export JQ_ADMIN_COOKIE_SECURE=true      # HTTPS 部署建议开启
export JQ_ODDS_API_KEY='...'            # 国际盘（The Odds API）；不配则市闸全 pending，不会产出 published
export JQ_PROD_DATABASE_URL='postgresql+psycopg2://jieqiu:...@10.0.0.5:5432/jieqiu'  # 不设则继续旧 SQLite
```

服务端 env 文件：`/etc/jieqiu-backend.env`（root:root 0600，由 `deploy.py` 写入），包含数据库 URL、JWT、管理员初始密码、数据路径。生产显式 `JQ_ENV=prod`、`JQ_AUTH_STUB=false`。

> 变量命名：`deploy.py` 的输入是 `JQ_PROD_DATABASE_URL`，部署时写入服务 EnvironmentFile 的变量名是 `JQ_DATABASE_URL`；本地直接运行只认 `JQ_DATABASE_URL`。两者不是同一个层的变量。
>
> 可选功能密钥（LLM/persona/API-Football/the-odds/短信/邮件/OAuth/`JQ_ADMIN_COOKIE_SECURE`）只从部署者显式 `export` 的环境变量透传到 EnvironmentFile；不会从仓库 `.env` 自动上传。未导出的项按降级路径运行。部署时会先读取远端 `/etc/jieqiu-backend.env` 与 `cron.env` 并合并保留已有 key；覆盖 `cron.env` 前自动备份最近 5 份（`cron.env.bak-时间戳`）。

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
| `*/30 * * * *` | `app.seed` 导入采集器快照、重建判决；随后 `app.recommendations_cli run` 走 snapshot→review→publish |
| `5 19 * * *` | `app.persona_cli warm`（预生成三套人设文案） |
| `10 6 * * 1` | `app.backtest_cli weekly` |
| `0 3 * * *` | `app.purge_cli`（注销冷静期满清理） |
| `* * * * *` | `app.features.assistant.worker --once`（事件/扇出/推送） |
| `10 4 * * 0` | `app.db_maint --apply`（保留策略） |
| `15 6 * * *` | `app.api_football_cli sync --next-day`（今天+明天 fixtures；**仅配置了 key 的部署自动安装**） |
| `0 0-4,10-23 * * *` | `app.api_football_cli sync-enrich`（每小时限量补 2 场阵容 + 1 场伤停） |

cron 中 `JQ_DB_STATEMENT_TIMEOUT_MS=0`，避免批量任务被 API 的 15s 语句超时打断。

API-Football 同步：配置了 `JQ_API_FOOTBALL_KEY` 的部署，`deploy.py` 会自动安装两条 cron：每日 06:15 `sync --date today --next-day`，以及 0–4/10–23 点每小时 `sync-enrich`（单次最多 2 场阵容 + 1 场伤停）。免费档 90/日、10 次/分钟；代码内 7 秒节流，避免 429。也可手动 `python -m app.api_football_cli sync --date $(date +%F) --next-day`。

## 5. 健康与告警

```bash
curl -s 'http://127.0.0.1:8100/health'            # 轻量：DB ping + 延迟 + 链摘要
curl -s 'http://127.0.0.1:8100/health?detailed=1' # 额外全表 count，勿给探针高频调用
```

`/admin` 运维页自动提示：SP 数据不可用或延迟（`sync_lag` 为空或 >1800s=30 分钟）、封存链异常、复核失败条数、API-Football 未配置，以及**国际盘未配置/0 条、市闸全部 pending、今日无已发布预测**。告警为请求时现算，尚无持久化/确认/外发（见 §10）。

**聚焦决策流（前后端已接通）**：`GET /stats/pulse` 与 `/admin` 数据源页同口径；源延迟/覆盖率告警复用本节阈值。数据点展示系数（默认 3、上限 5）只乘字段/数据点，不乘场次/封存数；后台同时展示 raw/display。契约见 [focused-decision-flow.md](./focused-decision-flow.md)。

### 内容供给排障（为什么没有 published）

市闸要求「竞彩官方 + 至少一条国际盘」两个去水口径；国际盘为空时，所有判决停在 `pending_data`，不会 `promoted`，也不会有任何 published 内容。先在服务器上跑诊断：

```bash
cd /home/ubuntu/jieqiu-backend
venv/bin/python -m app.odds_cli status          # 人类可读
venv/bin/python -m app.odds_cli status --json   # 机器可读
```

看四个数：
- `intl_odds.configured=false` → `JQ_ODDS_API_KEY` 未配置；
- `intl_odds.total=0` → 同步未跑或源失败；
- `market_gate.pending_data == verdicts.total` → 市闸全部 pending；
- `blocked_reason` → 后台「数据源/运维」页与 `/admin/api/data` 的 `supply` 字段同口径展示。

修复：

```bash
export JQ_ODDS_API_KEY='...'          # 部署时写入 /etc/jieqiu-backend.env
venv/bin/python -m app.odds_cli sync  # 手动同步一次（受 6h 节流；可用 JQ_ODDS_SYNC_MIN_INTERVAL_HOURS 调整）
venv/bin/python -m app.recommendations_cli run
venv/bin/python -m app.odds_cli status
```

`seed` 每 30 分钟会调用一次 `sync_the_odds_api`（有 key 且过 `JQ_ODDS_SYNC_MIN_INTERVAL_HOURS` 节流时）。sport key **按当日竞彩联赛动态选择**（英超/西甲/德甲/意甲/法甲/欧冠/欧联/欧协联等），不会为无关联赛烧配额；`JQ_ODDS_SPORTS` 仅作兜底。免费档 500 次/月时建议 `JQ_ODDS_SYNC_MIN_INTERVAL_HOURS=18` 或更高。**不要在没有国际盘时用单源硬发**——这会把“市闸”变成装饰，也会破坏“永远对照市场”的产品承诺。

### 模型闸排障（市闸过了为什么还没有 promoted）

- 让球 `hhad` 的市闸现在用 **had 快照** 对照 Pinnacle h2h（同口径）；精确 `spreads` 让球盘尚未接入，`market_gate.detail.market_pool` 会标 `had`。
- 静态 `xg_matches.csv` 只到 2024-25；Understat 对云服务器返回挑战页，`penaltyblog` 解析失败。
- 兜底：`app.results_sync` 从 football-data.co.uk 下载五大联赛历史比分，写成 `xg_extra_dir/footballdata_*.csv`（进球代理 xG，24h 节流）；证据层会标 `football-data 进球代理`，不是真 xG。
- 若模型闸仍 `pending_data`：看 `/admin` 推荐主链的 `model` 闸 `reason`；要提升覆盖率/质量，需要 **API-Football 付费 key** 或可用的当前 xG 源（Understat 直连已被拦截）。
- 2026-11-05 实测：国际盘覆盖 11/12，市闸 pass 10 / fail 1 / pending 1，模型闸 pass 1 / fail 1 / pending 10，已产出首条 published（水晶宫 vs 霍芬海姆，hhad 客胜）。

### 赛后归因 / 未采纳复盘 / 赛前提醒（P0 已实现）

- **CLV**：`settle_verdicts` 结算时取停售前最后一条同池 `SPSnapshot`（`captured_at <= kickoff`），写 `verdicts.closing_sp_h/d/a`、`closing_at`、`clv = 1/收盘 - 1/入场`。没有同池快照时留空，不猜。迁移 `20261105_13`。
- **周报**：`app.modules.postmortem` 增加 `clv` 汇总（样本数/均值/正 CLV 占比）与 `you.clv_n/you.clv_avg`；只统计有收盘快照的已结算判决。
- **概率区间**：`app.modules.calibration.interval` 用已结算 promoted 判决的预测残差做经验分桶；样本 <20 返回 `interval_status="accumulating"`，不返回伪造区间。`SnapshotPublic` 暴露 `prob_low/prob_high/interval_status/interval_n/interval_method`。
- **未采纳复盘**：`GET /stream`（登录）的 `unattended` 返回“看过判决但没下注”的已结算场次；移动端首页用独立卡片展示，文案只做事实复盘，不诱导下注。
- **赛前提醒**：`assistant/monitors.py::scan_prematch` 在 T-3h / T-30m 扫描 promoted 判决，按 `dedupe_key` 去重；`run_monitors` 返回 `prematch_t3h` / `prematch_t30m`，`render.py` 使用中性文案（不写赔率/投注/结果），`fanout.py` 已加入默认事件。
- **验证**：`tests/test_calibration.py`、`tests/test_unattended.py`、`tests/test_assistant.py::test_prematch_reminders_dedupe`、`tests/test_w4.py` 的 CLV 断言。

真实推送仍缺客户端与厂商凭证：JPush AppKey/Master Secret、华为/小米/OPPO/vivo 通道、Android 原生或 EAS 构建、客户端 token 注册/通知权限/点击深链。后端 dry-run 和站内信已可用，不会因未配置 JPush 阻塞判决发布。

## 6. 管理后台

- **入口**：`/admin`（新版运营台，当前唯一推荐入口）；登录 `POST /admin/api/login`，会话 cookie `admin_t`，HttpOnly + SameSite=strict。
- **首个管理员**：首次登录时用 `JQ_ADMIN_PASSWORD` 创建 `admin`；未配置时回退 `JQ_CONSOLE_PASSWORD`（dev/test 回退 `dev`）。建号后密码以 PBKDF2-SHA256 落 `admin_users`。
- **RBAC**：
  - `viewer`：只读总览/模型/用量/人设/推荐/数据/运维/审计；
  - `operator`：额外可运行主链、复核、发布、撤回、测试模型/LLM 连接；
  - `admin`：额外可改文案模型池、LLM 接入配置、人设 profile/槽位、创建/停用账号、重置密码。
- **合规（服务端强制）**：`GET /compliance/state`、`POST /gate/verify`、`POST /me/under18-lock`、`POST /compliance/self-exclusion`、`POST /compliance/self-assessment`；`POST /bets` 与 `focus.capabilities` 同时检查未成年锁定/自排除/休息中，重装或换设备不能绕过。客户端本机自排除先持久化，服务端同步失败时保留 `syncPending` 并在下次前台/登录自动补写。
- **旧 `/console` 已全部下线**：`/console` 及 `/console/*` 一律 302 到 `/admin`，不再提供登录或页面；W8 `/review/*` 也改用 `admin_t` + RBAC。
- **新版页面**：
  - 总览：KPI + 今日待办（待复核/复核失败/待发布/模型降级/SP 延迟/未配 Key）；
  - **接入中心**：按“用途”分组，不按厂商堆列表。AI 能力（对话问答 fast / 发布前复核 deep / 人设文案 / 单场实时分析未接入）、数据源（API-Football / The Odds API / 竞彩 SP）、推送（JPush）；fast/deep 可在页面直接上传 Base URL、Model、Key，保存后优先于环境变量，Key 加密存储；
  - 调用用量：fast/deep profile、任务路由（标记已接入/未接入）、今日成本/缓存/最近调用；
  - 文案模型池：只服务人设文案（每日 19:05 预生成），不服务 `/chat`；增删改、优先级、启停、Key 轮换、单模型测试；
  - 人设文案：三套 profile、槽位、翻译测试；
  - 推荐主链：运行 build→review→publish、逐条/批量复核、发布、撤回、搜索、分页；
  - 组合预览、数据源、运维（告警/API-Football/通知队列/Push/24h 互动）、账号、审计、日志。
- **LLM 配置优先级**：`llm_profiles`（后台，加密）→ 环境变量 `JQ_LLM_FAST_*` / `JQ_LLM_DEEP_*` → `degraded` 模板兜底；后台显式停用不回退 env。迁移 `20261106_14_llm_profiles`。
- **审计**：`admin_audit` 记录 actor/role/action/target/before/after/IP；登录、模型、人设、推荐发布、账号变更均写入；`/admin/api/audit?limit=&offset=` 读取。
- **分页**：`/admin/api/recommendations?limit=&offset=` 返回 `page.has_more/next_offset`；审计同样 limit/offset；日志只读尾部 256KB。
- **GET 只读**：`/admin/api/*` 与 `/recommendations/today` 只读不写库；过期由 30 分钟 cron 的 `run_pipeline → expire_due` 处理，`/recommendations/today` 只按 `expires_at` 过滤。公开详情 `GET /recommendations/{id}`、`/recommendations/plans/{id}` 仍会惰性 `expire_due`（读时顺带过期），属预期。
- **会话/横向扩展**：`admin_t` 会话在进程内存；多 worker 前需换 Redis/DB 会话。
- **W8 冻结**：新增路由后登录后台调用 `POST /review/freeze/adopt`；当前基线 **145 路由**。2026-11-06 新增 3 条 admin 接入路由（LLM profiles 查询/保存/测试），部署后必须重新 adopt。

### API-Football（免费档）

> 2026-11-05 当前生产状态：已配置 API-Sports `apisports` Free（100/日、10/分钟）。当天+次日 fixtures、已链接场次的 lineups/injuries 已跑通；当前赛季 standings 被 Free 档拒绝。`sync-enrich` 每小时限量补临场阵容，代码内 7 秒节流。

```bash
export JQ_API_FOOTBALL_PROVIDER='apisports'
export JQ_API_FOOTBALL_KEY='...'
export JQ_API_FOOTBALL_DAILY_LIMIT=90
export JQ_API_FOOTBALL_MIN_INTERVAL_S=7
cd /home/ubuntu/jieqiu-backend
python -m app.api_football_cli status --json
python -m app.api_football_cli sync --date $(date +%F) --next-day --json
python -m app.api_football_cli sync-enrich --lineups-max 2 --injuries-max 1 --json
```

- `apisports` 用 `x-apisports-key`；RapidAPI 用 `x-rapidapi-key` + host，需在同一账号订阅。
- Free 档 100 请求/日、10 次/分钟；代码默认 90/日 + 7 秒节流。`401` 是 key 错，`403` 是订阅未生效，`429` 是分钟限流。
- fixtures 每日 1 次（今天+明天）；lineups/injuries 按窗口补；**当前赛季 standings 被 Free 档拒绝**，生产已关闭 standings 请求，升级付费档后开启。
- 未配 key 时 `/admin` 运维页显示未配置，同步命令返回 `configured: false`，不影响判决主链。
- `/admin` 数据源/运维页的 API-Football 卡片显示目标链接、阵容/伤停、积分榜、今日额度条和 warnings；Free 档 standings 通过 `JQ_API_FOOTBALL_STANDINGS_ENABLED=false` 关闭。
- 详见 [api-football.md](./api-football.md)。

### 人设语气翻译（TokenRhythm）

```bash
export JQ_PERSONA_LLM_BASE_URL='https://tokenrhythm.studio/v1'
export JQ_PERSONA_LLM_API_KEY='...'
export JQ_PERSONA_LLM_ENC_KEY='...'   # Fernet key，用于加密 DB 中的模型 Key
export JQ_PERSONA_LLM_TIMEOUT_S=20
export JQ_PERSONA_LLM_MAX_TOKENS=800
export JQ_PERSONA_LLM_TEMPERATURE=0.4

# 查看模型池 / 测试 / 预生成当日三套文案
python -m app.persona_cli models
python -m app.persona_cli test --persona laopao --text "..."
python -m app.persona_cli warm --date $(date +%F)
```

- 后台 `/admin` 人设文案页可添加/排序/启停/测试模型；默认 `egg-alpha` → `neohorse-1-9b`。
- `egg-alpha` 当前上游 409 时自动切 `neohorse-1-9b`；连续失败进入 120s 冷却。
- 用户请求只读 `persona_copy_cache`，不同步等 LLM；缓存未命中回退模板。
- 建议 cron：每日 19:05 跑一次 `warm`；首发更新后按需再跑。
- Key 在 `.env`（0600）或部署 EnvironmentFile；DB 中为 Fernet 加密，后台只显示“已配置”；后台每行可更新 Key 做轮换。

### LLM Gateway（Phase 1）

```bash
export JQ_LLM_FAST_API_KEY='...'      # 可选；未配置则 /chat fallback 走固定引导
export JQ_LLM_DEEP_PROVIDER='tokenrhythm'
export JQ_LLM_DEEP_BASE_URL='https://tokenrhythm.studio/v1'
export JQ_LLM_DEEP_API_KEY='sk_tr_...'
export JQ_LLM_DEEP_MODEL='deepseek-v4.1-flash-1017'
export JQ_LLM_TIMEOUT_S=60
export JQ_LLM_REVIEW_MAX_TOKENS=1600  # 推理模型 reasoning tokens 会吃额度；400/800 会返回空 content
export JQ_LLM_DAILY_BUDGET_CNY=50
export JQ_LLM_TASK_BUDGET_CNY=20
export JQ_LLM_USER_DAILY_CALLS=50
```

- 固定意图 0 LLM；匿名固定引导；只有登录用户的 `/chat` fallback 进入 `open_chat → fast`。
- `decision_review`/`plan_review` 已接 deep 模型；复核只发送压缩后的必要字段（~1KB），避免推理模型把 token 全花在 reasoning 上。2026-11-05 实测 `rules+deepseek-v4.1-flash-1017`、`llm_degraded=false`、`llm_review=pass`。
- `match_analysis` 已接单场解读（`POST /matches/{id}/analysis`，`ai_analyses` 缓存）；异步 `analysis_jobs` 与情报表仍未做；`adversarial_review` 已删除。
- 无 Key/超预算/超时/schema 失败均 `degraded`，不会阻塞判决，也不会返回 5xx。
- LLM Key 可走 env 或后台加密存储（`llm_profiles`）；`/admin` 只显示“已配置/未配置”与来源，不回显明文。
- `/admin` 模型池/人设写操作均已接入 `admin_audit`；写操作强制 CSRF（`admin_csrf` + `X-CSRF-Token`），角色/启停/改密/删除会撤销该账号全部会话。
- 详见 [llm-gateway.md](./llm-gateway.md)。

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
2. `/admin` 运维页同步延迟/快照；
3. `systemctl status jieqiu-backend`、`journalctl -u jieqiu-backend -n 200`；
4. cron 日志：`sync.log`、`backtest.log`、`purge.log`、`assistant.log`、`db_maint.log`；
5. Postgres：`pg_stat_activity`、锁等待、`pg_stat_statements`；
6. 封存链：`/chain/verify?date=...`、`/anchor/latest`；
7. 推送：`/admin` 运维页、`/push/health`、worker 日志。

## 10. 明确未完成

- TLS/反代、多进程会话；
- 备份/PITR 自动化；
- 真实 JPush、支付/权益、OCR、真实 live feed/进球提醒、持久化告警/任务中心；
- 真实 Android APK / iOS 原生构建验收。

> 合规服务端同步已于 2026-11-05 闭环（年龄门/未成年/自排除/PGSI + `/bets`、focus 硬拦截），不再列入未完成。
