# 运维 Runbook（当前实现）

最后更新：2026-11-14。适用于当前过渡期 `jieqiu-backend/` + 单台腾讯云 VPS；目标数据库是境内 PostgreSQL 16（**云托管优先 / 自建兜底**，见 ADR-0004），未设置 `JQ_PROD_DATABASE_URL` 时仍是旧 SQLite。

> **v4.1 部署状态**：2026-11-12 11:38 CST 已用 `deploy.py` 部署到 `43.128.24.244`，`systemctl is-active jieqiu-backend` = active，`/health` 200，OpenAPI 158/174，管理后台静态资源 `v=20261112e`；生产仍为 SQLite（`/home/ubuntu/jieqiu-data/jieqiu.db`，约 40M）。部署前备份：`/home/ubuntu/backups/jieqiu-backend-20261112-113522.tar.gz`（代码）与 `jieqiu-20261112-113522.db`（库）。回滚：停服务 → 解压代码备份到 `/home/ubuntu/jieqiu-backend` → 用 `sqlite3` 的 `.backup` 恢复库（或先保留现库为 `.bak`）→ `systemctl start jieqiu-backend`。v4 新增计划/会员/结算/OPC 表已在生产 SQLite 建表；后续观察 `settle_pending`、`settle_open_cycles`、会员到期 job 与 seed 是否正常写 `ops_jobs/ops_exceptions`。
>
> **2026-11-12 13:44 CST 数据更新**：Sportmonks 新订阅生效后，生产重新同步欧国联 6/6 场（fixture、Pinnacle 去水赔率、1X2 预测、正确比分分布、AI 情报）；判决链在 DC 缺阵时使用 Sportmonks 1X2/正确比分推导的后备模型，并标注 `model_source=sportmonks`。重建后 1 场 verified、3 场市场参考、2 场不建议；重算前库备份 `/home/ubuntu/backups/jieqiu-20261112-134211-pre-rebuild.db`。
>
> **2026-11-12 17:00 CST 情报层部署**：生产应用 Alembic `20261112_24`，新增 `sportmonks_fixture_intel/predictions/markets`；6/6 场已同步 11 人首发、阵型、教练、裁判、伤停、积分榜、H2H、天气/场地和 25 维预测。聚焦覆盖从 55 提升到 100（价格新鲜时），`deep_eligible=true`；AIResearch 已包含阵容/伤停/积分榜/环境。部署前库备份 `/home/ubuntu/backups/jieqiu-20261112-162055-pre-sm-intel.db`。回滚：停服务 → `alembic downgrade 20261112_23` → 恢复上述库/旧代码 → 启动。
>
> **2026-11-13 13:11 CST 比赛中心部署**：生产应用 Alembic `20261113_26`，新增 `sp_pool_snapshots / sportmonks_live_state / sportmonks_prediction_snapshots / sportmonks_prediction_settlements / match_result_details`；管理后台静态资源 `v=20261113a`。首次 `freeze` 生成 12 场赛前快照（4 场锁定），`enrich` 补齐 6 场 actuals，`settle` 写入 4 场 × 26 项对照；`/matches/live`、`/matches/results`、`/predictions/history` 均返回 200。部署前备份：`/home/ubuntu/backups/jieqiu-backend-20261113-131018.tar.gz`（代码）与 `jieqiu-20261113-131018-pre-match-board.db`（库，46M）。回滚：停服务 → `alembic downgrade 20261112_24` → 解压代码备份 → 用 Python `sqlite3` 的 `.backup` 恢复库 → 启动。

> **2026-11-14 H5 白屏事故与修复（无数据库变更，后端代码已上生产）**：当日两次 H5 部署误用 `rm -rf` 全删服务器 h5 目录再拷最新，叠加两个既有隐患造成缓存用户白屏：① 浏览器缓存的旧 index.html 仍引用被删除的旧 entry JS；② `/h5/{path}` 路由把不存在的资源也回退成 index.html（200 + text/html），浏览器把 HTML 当 ES 模块加载因 MIME 校验失败直接白屏。**修复（`c3f7e31`/`56a01bf`/`c018dec`，已部署）**：`/h5/*` 对缺失 js/css/字体等资源返回真 404；`_expo/`、`assets/` 哈希产物 `Cache-Control: immutable` 长缓存；index.html 保持 no-cache；服务器恢复 6 代 entry 宽限缓存用户（`da90cb83` 最新 + 5 代回退）；`deploy.py` 打包跳过 `app/static/h5`、部署时滚动保留 `h5_prev/h5_prev2` 合回。后端为 scp 单文件 `app/main.py` + `systemctl restart`（非全量 deploy），重启后 `/health`、`/matches/live`、`/admin`、`/h5/` 全 200，journalctl 无 error；后端全量 **366 tests** 通过。管理后台本日未改动（静态资源 `v=20261113b`）。
>
> **H5 发布纪律（长期有效）**：① 只做合并式发布（`just h5-publish` 或 scp 覆盖），**严禁在服务器 `rm -rf` h5 目录**——旧 entry 是缓存用户的回退路径；② 手动 `expo export` 必须带完整 `EXPO_PUBLIC_API_BASE_URL/APP_ENV/ALLOW_HTTP` 前缀（漏带会让 env 校验 fail-closed 在启动时抛错 → H5 黑屏，2026-11-14 实际发生过，靠浏览器捕获 unhandledrejection 定位）；③ 验证方式：`curl /h5/` 取 entry 哈希应等于本地 `index.html` 引用，`curl 旧entry` 应 200 + javascript MIME，`curl 不存在.js` 应 404。

> **2026-11-14 OPC 运营控制面补全（已部署，无数据库变更）**：commit `271ff27`，管理后台静态资源 `v=20261113b→20261114a`，后端全量 **369 tests** 通过。改动：① OPC 任务生产者补全——`settle_open_cycles`（plan 结算）、`membership_expire`（会员到期）、`seed_daily`（每日 seed）接入 `ops_jobs`/`ops_exception`（此前仅 `settle_pending` 有记录），失败记 exception 后吞掉异常不让调度链被单次失败拖死；② `/admin/api/ops-v4` 新增 `summary`（按 job_key 聚合最近 200 次：最近状态/耗时/失败数/最近错误）；③ `/admin/api/app-users` 新增合规巡检字段（年龄门/未成年锁定/自排除/连败保护开关/休息至/今日 AI 额度）；④ 管理后台 UI：异常队列页新增「任务健康汇总」卡、用户与会员表新增「合规/额度」列。部署方式：scp 7 个文件（admin_api/ops/plan_service/membership/seed/admin.js/index.html）+ `systemctl restart`，冒烟 active、`/health` 200、admin shell 引用 `v=20261114a`、`/admin/api/ops-v4` 未认证 401、journalctl 无 error。回滚：`git checkout 271ff27~1 -- app/routers/admin_api.py app/modules/ops.py app/modules/plan_service.py app/modules/membership.py app/seed.py app/static/admin/` 后重启。

> **2026-11-14 工作台并入 OPC（已部署，无数据库变更）**：commit `c39731e`，后端全量 **371 tests**。① `build_workbench` 新增 **ops 阶段**（key=`ops`）：聚合 seed_daily/settle_pending/settle_open_cycles/membership_expire 四个核心任务的健康汇总与未处理异常——核心任务最近失败或 sev≥3 异常 → `blocked`（工作台 headline 自动点名主卡点），管理员首屏即可定生死，无需跳异常队列页；② `run_action` 的一键动作（重启采集器/同步国际盘/同步 Sportmonks/同步情报/测 LLM/跑主链）全部接入 `ops_jobs`（`action_*`），业务失败记 error+sev2 异常、崩溃记 sev3——每个按钮可追溯、失败自动进异常队列；③ diagnose 上下文带 ops 摘要，LLM 诊断可读任务失败原因。部署：scp `app/features/ops/workbench.py` + restart，冒烟 active/`/health` 200/workbench 未认证 401/journalctl 无 error。回滚：`git checkout c39731e~1 -- app/features/ops/workbench.py` 后重启。

> **数据源完整性已知限制（Sportmonks 事件覆盖）**：低档订阅的 fixture events 不保证全量——实测 2026-11-14 周五003（保加利亚 0-5 冰岛）终场 5 球但 API 仅返回 3 条 type_id=14 进球事件（缺 0-1/0-3）。前端 MatchTimeline 已做容错（）：事件进球数 < 终场总进球时显示琥珀提示「数据源仅记录 N 个进球事件…比分以终场为准」。同期终场比分/xG 数据完整，仅事件时间线受限；若订阅升级到全事件档，时间轴自动变完整，无需改代码。

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
| `*/30 * * * *` | `app.seed` 导入采集器快照、重建判决、结算、会员到期、重建每日战绩、自动结算计划并确保当日三期计划；随后 `app.recommendations_cli run` 走 snapshot→review→publish |
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

`seed` 每 30 分钟会调用一次 `sync_the_odds_api`（有 key 且过 `JQ_ODDS_SYNC_MIN_INTERVAL_HOURS` 节流时）。sport key **按当日竞彩联赛动态选择**；先调免费的 `/sports/{sport}/events`，只把与 `SPMatch` 队名 + 开赛时间（±4h）匹配的 `eventIds` 传给 `/odds`；没有匹配赛事就不请求 odds，不花 credit。默认 `JQ_ODDS_API_REGIONS=eu`、1 市场 = 1 credit/sport。免费档 500 次/月时建议 `JQ_ODDS_SYNC_MIN_INTERVAL_HOURS=18` 或更高。**不要在没有国际盘时用单源硬发**——这会把“市闸”变成装饰，也会破坏“永远对照市场”的产品承诺。

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
  - **用户与会员（v4）**：搜索 App 用户、查看当前会员/额度、手动开通/撤销 Pro/Max（7/30/90 天或自定义）、备注；手机/邮箱脱敏；写 membership event + admin audit；
  - **AI 计划（v4）**：按 risk 查看/生成当前期与历史期、查看投注结构与 legs、手动结算入口；计划只展示，不做跟单；
  - **异常队列（v4）**：`ops_jobs` 运行记录 + `ops_exceptions` 未解决异常，可 ack/resolved；异常带 dedupe_key，避免重复刷屏；
  - **引擎配置（v4）**：`version / markets_monitored / models_reviewing / data_points_factor`，直接控制首页 HeaderMetrics 展示；改动写审计；
  - **采集器**：查看家宽采集器在线/离线、最后心跳、SP 文件年龄、轮次/场次/错误，一键下发重启（采集器下一次心跳退出并由本地 watchdog 拉起）。
  - **接入中心**：按“用途”分组，不按厂商堆列表。AI 能力（对话问答 fast / 发布前复核 deep / 人设文案 / 单场 AI 解读）、数据源（API-Football / The Odds API / 竞彩 SP）、推送（JPush）；fast/deep 可在页面直接上传 Base URL、Model、Key，保存后优先于环境变量，Key 加密存储；
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
- 真实 JPush、真实支付/订单/回调、OCR、真实 live feed/进球提醒、持久化告警外发/任务编排；
- 生产 Postgres 切库与恢复演练；
- 真实 Android APK / iOS 原生构建验收；
- v4 的多盘口完整数据、计划自训练模型、计划更新提醒/收藏。

> 合规服务端同步已于 2026-11-05 闭环（年龄门/未成年/自排除/PGSI + `/bets`、focus 硬拦截），不再列入未完成。
> 会员权益、后台手动开通、计划分级已于 2026-11-12 实现；**只有支付仍是假 UI**，不要写成“支付已接”。
