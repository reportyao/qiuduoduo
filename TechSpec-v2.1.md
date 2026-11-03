# 「解球」技术开发文档 v2.1 · 整合定稿

| 项目 | 内容 |
|---|---|
| 版本 | v2.1（自包含，不依赖任何历史版本文档） |
| 日期 | 2026-11-01 |
| 配套 | PRD v5.1 · Release-plan v1.1 · Roadmap v1.1 · OpsBlueprint v1.0 |

---

## 1. 选型定稿

| 层 | 选型 | 取代/理由 |
|---|---|---|
| App | **Expo（React Native）**，iOS+Android 一套代码 | 取代 Next.js PWA 三端方案；TS 生态对 AI 开发最友好 |
| Web | Next.js 静态两页（公开账本+下载落地）+ 免费工具页（M2 SEO） | 仅此三处 |
| Auth | **自建认证**（统一 JWT access 15min + refresh 30d）：CN = 手机号+短信验证码；Global = Email 验证码 + Google/Apple OAuth；设备令牌降级为「免登录态/换机迁移」辅助 · **登录/注册方式按 market profile 渲染（PRD F18）** | 弃 Supabase（见 §1.1 方案 B）；设备令牌 W6 已上线，W5 增补手机号/邮箱绑定 |
| 订阅 | **RevenueCat**（iOS IAP+Android 支付统一层） | 省 1 周；CN 安卓走微信/支付宝直连其 SDK |
| 推送 | CN：**JPush 聚合厂商通道**；Global：Expo Notifications（APNs/FCM）；静默推送均支持 | 厂商通道是国内安卓唯一可靠路径 |
| 模型 | **penaltyblog**（DC/贝叶斯/去水/抓取，覆盖建模核心约 35%）+ **sports-betting**（回测）+ **betfairlightweight**（交易所历史流→「势」维度回放） | 经适配层隔离，业务模块不直接 import |
| 数据校验 | **Pandera**（每表一个 DataFrameModel，ERROR/WARN 两级，CI 强制） | 防脏数据静默污染 |
| OCR | **RapidOCR**（票面字段提取，本地亚秒）+ GLM-4V（仅推荐截图语义理解） | 拆分工，零 token 成本 |
| LLM 选型依据 | **GLM-4-Flash 免费档为主力**（中文口语写作+免费+国内直连；仅用于文案/变体/截图理解，**不参与预测**——预测 100% 来自统计模型层）；**DeepSeek-V3 为质量备胎**（出戏率超标时切，~¥20-40/月）；Qwen-VL 备 GLM-4V；GPT/Claude 因合规不入主链 | 防误读：换更强的 LLM ≠ 预测更准 |
| 搜索 | Meilisearch（队名/场次，中文容错） | 替代手写模糊匹配 |
| 埋点/AB | **PostHog**（RN SDK，含 feature flag） | 取代自建 events+Unleash |
| 后端 | FastAPI 模块化单体 + PostgreSQL（分区）+ Redis | 不变 |
| 部署 | App：EAS Build/Submit；Web：Vercel；API：单 VPS systemd（deploy.py 一键：代码/数据分离 + 三 cron + 控制台同进程）→ S 阶梯 | |
| 观测 | Sentry + PostHog + uptime | |

**不用**：微服务、K8s（前 6 个月）、自训 LLM、GraphQL、深度学习、小程序。

### 1.1 决策记录：弃 Supabase，全栈改「方案 B」（2026-11-03）

**决策**：不用任何 BaaS。数据库 = 腾讯云 PostgreSQL 16（同机/同区）；认证 = 自建 JWT（CN 手机号+短信，Global Email+OAuth）；数据库管理 = editor_console（已上线）+ pgAdmin/DBeaver 只读连接。

**为什么（4 条硬理由）**
1. **延迟**：Supabase 节点在海外，CN 用户 API→DB 跨境往返 150–300ms；主库与 API 同机可压到 <2ms。
2. **数据主权**：封存链/公开账本的公信力建立在「数据在国内、可独立复核」上；用户数据出境会给提审与后续合规加变量。
3. **已有基建**：SQLAlchemy 双方言（W3 review 已适配 upsert）、deploy/备份/cron 全自动化、设备令牌认证全链路已上线——换 Supabase 反而要迁移用户体系。
4. **成本**：PG 含在同机 VPS（¥60/月）；Supabase 免费档之外 $25/月起，且仍要一台 VPS 跑 API。

**目标架构（S1）**
```
Expo App ──HTTPS──> 腾讯云 VPS: uvicorn(api) ──localhost──> PostgreSQL 16
                                    ├─ editor_console（同进程 /console，密码+IP 白名单）
                                    ├─ cron: seed 30min / backtest 周一 / purge 每日
                                    └─ 备份: pg_dump 每日 03:30 → 异地对象存储（保留 14 天）
```

**迁移步骤（SQLite → PG，停机窗口 ≤15 分钟）**
1. VPS 安装 PG 16 → 建库 `jieqiu` + 应用账号（最小权限）
2. `alembic init` + autogenerate 基线（当前 create_all 语义转为迁移脚本）
3. 数据搬运：pgloader 或自写 sqlite→COPY 脚本；校验行数 + 抽样哈希
4. 切流：systemd `JQ_DATABASE_URL=postgresql+psycopg://...` → restart → `/health` 计数对齐 → `/chain/verify` 全绿
5. 回滚预案：SQLite 文件保留只读 7 天，环境变量一行切回

**认证设计（W5 实施）**

| 区域 | 登录方式 | 实现 |
|---|---|---|
| CN | 手机号 + 短信验证码 | 腾讯云 SMS；`auth_identities(provider='sms')` |
| Global | Email 验证码 + Google/Apple OAuth | Resend/SES + 自建 OAuth client |
| 共同 | JWT access 15min + refresh 30d；设备令牌保留为「免登录态」，绑定手机号/邮箱后可换机恢复 | `refresh_tokens` 表 + 轮换检测 |

**对 W8 冻结的影响**：W5 新增的 auth/推送/支付端点会在 `/review/freeze` 报违规——这是预期行为。W5 完成后**重新 adopt 冻结基线**，并重跑 `/review/checklist` 全量回归，再进提审。

---

## 2. 部署阶梯与触发器

| 级 | 规模 | 形态 | 触发升级 |
|---|---|---|---|
| S1 | ≤5K DAU | Vercel(Web)+腾讯云 VPS(api/worker)+同机 PostgreSQL 16 | DAU>5K |
| S2 | ≤3 万 | api×2+PgBouncer+读副本+Redis 哨兵+CDN | DAU>3 万 |
| S3 | ≤10 万 | K8s 多可用区+Kafka 推送队列+ClickHouse | 事件>500 万/天 |
| S4 | 100 万 | 双区域（CN/Global 数据驻留隔离） | 监管/规模 |

---

## 3. 前端（Expo）

### 3.1 结构（Expo Router：底部四 Tab，三端同构）

```
apps/app (Expo)
  app/(tabs)/home.tsx          # 首页=判决流
  app/(tabs)/tools.tsx         # 工具宫格（9 项）
  app/(tabs)/records.tsx       # 记录（票单/周报/账本/记忆/导出）
  app/(tabs)/me.tsx            # 我的（设置六组）
  app/verdict/[id].tsx  app/matches/[id]/cost|why-not|evidence
  app/parlay/[step].tsx        # 体检流程 build→report→plans→confirm
  app/matches/[id]/live.tsx    # 实况卡
  app/gate.tsx  app/auth/login.tsx  app/me/{persona,compliance,subscription,privacy}
  components/                  # 设计系统（下表）
  lib/{api,auth,rc,jpush,i18n,money,odds,time}/
packages/web (Next.js 静态)      # 公开账本 + 落地页 + 免费工具
```
**跨端约定**：本 HTML 演示（jieqiu-app/index.html，**已部署 http://43.128.24.244:8899**，独立 systemd 服务 jieqiu-static，静态目录 /var/www/jieqiu）= 三端唯一 UI 规格基准；RN 按 1:1 组件映射；底部 TabBar 用 Expo Router `(tabs)` + 平台 safe-area；图标/间距/圆角令牌与 H5 共用一份 tokens.json。**吉祥物资产 `mascot-gen.png`（2048×1152 三联生成图）三端共用**：CSS sprite `--sx` 0/50/100% 切人设，正式版替换为三张透明 PNG。

### 3.2 设计系统组件（19 个）

`VerdictCard` · `VerdictDetail` · `CostLabel` · `EvidenceCard`(判断依据) · `LiveMatchCard`（实况卡：状态机 scheduled/live/FT/settled，折叠/展开，走盘实时计算） · `ParlayBuilder` · `ParlayReport` · `GateChips` · `ConfidenceBadge` · `LegalSlot` · `OddsText`（四格式） · `Money`（单位制） · `MatchTime`（四件套） · `SystemState`（6 态） · `SuggestionChips` · `OnSaleList`（今日在售·体彩同步状态行） · `PersonaPicker`（人设三选·行头像·试读样句） · `ShareCard`（编号+二维码） · **`MascotSprite`（吉祥物三联 sprite：`--sx` 切人格，`avround` 圆形/bust 两裁切，float+halo 动画；首页状态区中央 64px 圆形+人设名牌（RN 版注意：居中 transform 与浮动动画分离到父子两层，避免 transform 覆盖）、人设页行头像、空态 130px、归因卡头像四处复用）** · `ChatBar`（对话输入栏，固定于 TabBar 上方，仅首页显示，拦截态隐藏；圆角输入+相机按钮）

### 3.3 卡片路由注册表（对话→卡片，12 张）

`verdict / cost_label / evidence / dead_gate(为什么不推) / water_rank / parlay_digest(摘要→转交) / ticket_scan(记账确认) / screenshot_verdict(鉴别) / persona(人设切换确认) / ledger_digest / memory / empty(含教育卡)`

规则：LLM 只选卡+填参（JSON schema 校验）；每卡 ≤2 按钮；转交卡必带草稿。

### 3.4 微交互（6）

流式生成（SSE→RN 逐字）· 哈希指纹（16 位→4×4 点阵）· 数字滚动 · 骨架 stagger · 数据源状态行 · 封存轻反馈（触觉+音效，可关）。全部尊重系统减弱动效。

### 3.5 i18n

next-intl 等价物 `i18n-js`+ICU；三语言解耦（UI/内容/球队名）；伪本地化进 CI；RTL 逻辑属性预留。

### 3.6 交互基建（对应 PRD §6.5 反馈规范）

| 项 | 实现 |
|---|---|
| 触觉/Toast 令牌 | `expo-haptics` 四令牌（light/success/warning/error）+ 自建 `Toast` 组件三型（成功/中性/失败+重试），全局唯一出口 `feedback.ts`，禁止裸调 |
| 深链路由 | `jieqiu://verdict/{id} · match/{id} · parlay/{id} · ledger` 冷启动路由表进 App 构建配置；推送 payload 携带 `deeplink` 字段，点击直达并高亮目标卡（冷启动先入流再滚动定位） |
| OTA/强更 | `expo-updates`：非破坏性更新静默 OTA；破坏性版本走强制升级全屏（SystemState 第 6 态），min-version 由服务端下发 |
| 权限被拒恢复 | 通知权限拒绝后，软请求入口转为"去设置开启"深链（`Linking.openSettings`） |
| 草稿持久化 | 串关构建草稿/MMKV 本地持久化 24h，重新进入体检器自动恢复 |
| Paywall 状态机 | RevenueCat：`canBuy / purchasing / success（解锁动效）/ failed（重试）/ restored`，权益变更走 listener 即时刷新会员徽章 |
| 实况卡刷新 | 卡可见期 30s 轮询 + goal/FT 事件 silent push（content-available）触发 `refetch`；后台退栈即停轮询 |

---

## 4. 后端模块（FastAPI）

`auth(SMS 层) / users / ingest / align / model / market / verdict(封存结算) / narrate(变体池) / messaging(卡片+消息工厂) / push(JPush·Expo·Email 适配+频控) / billing(RC webhook+微信) / compliance / i18n(glossary) / risk(防薅/水印) / audit(哈希链) / **collector**(竞彩 SP 采集，已上线·本机家宽运行) / **moderation**(UGC+截图审核) / **reconciliation**(支付对账) / **leaderboard**(公开账本聚合+周报) / **feature_flags**(PostHog 封装) / **editor_console**(编辑台 API：变体池 CRUD+精选工单+日报)`

关键管道：

- **settle 管道**：逐腿判定 → 归因 → `match_facts`（含 what-if 穷举 N≤4）→ 消息工厂（模板+槽位）→ messages 落库 → push 队列
- **变体池**：每晚 LLM 批量生成人设变体（~几百次调用），数字白名单+术语校验，兜底纯模板；用户渲染=哈希选变体+填槽
- **实况卡**：live feed → timeline 追加；卡片可见期 30s 轮询 + 关键事件 silent push（不亮屏不锁屏不计频控）

---

## 4.5 管理后台架构（轻量分层，不建重后台）

**原则**：OPC 阶段不建自研重管理后台；各专业工具各管一摊，**编辑台**是唯一需要自建界面的模块（它是产品灵魂）。B 端白标（v2.5）前不升级。

> **W7 落地状态（2026-11-03）**：editor_console v0 已上线（`app/routers/console.py`，与 API 同进程）——
> `/console/login`（密码 `JQ_CONSOLE_PASSWORD`，生产必设 + 可选 `JQ_CONSOLE_IP_WHITELIST`）·
> `/console` 数据日报（计数/链状态/账本/模型评估/近期判决）· `/console/alerts`（断链/同步延迟/源未配/密码未设）·
> `/console/variants`（三人设模板 + A/Q/X 精选状态机，进程内存，v1.5 换 narrative_pool 表）·
> `/console/ops`（环境/数据源/cron 日志指引/快捷命令）。
> 后端硬化同批上线：令牌桶限流（读 120/min、写 30/min/IP，429+Retry-After）、X-Request-ID + JSON 访问日志、
> python-multipart 依赖补齐。105 测试全绿，git 版本控制就位。

### 分层架构

| 层 | 工具 | 管什么 | 频率 | 认证 |
|---|---|---|---|---|
| **统一入口页** | **editor_console**（自建单页，FastAPI+HTMX，部署同 VPS `/console`） | 变体精选/数据日报/告警/快捷运维 | 每晚 10 分钟 + 每日抽查 | **自建会话（密码 + IP 白名单，W7 已上线）** |
| **数据库管理** | **pgAdmin / DBeaver 远程连接**（只读账号为主）+ `psql` | 全表 CRUD/SQL/备份 | 按需 | SSH 隧道 + 2FA |
| **客服工单** | **Chatwoot**（开源 Docker 同 VPS） | 工单/申诉/消息 | 每日 15 分钟 | Chatwoot 账号 |
| **分析/AB/旗** | **PostHog Cloud** | 埋点/漏斗/旗/回放 | 每周 | PostHog 账号 |
| **支付对账** | RevenueCat Dashboard + reconciliation 表 | 月度 | 月 | RC 账号 |
| **LLM 观测** | **Langfuse**（开源 Docker） | 变体质量/成本/prompt 版本 | 每周 | Langfuse 账号 |
| **监控** | uptime-kuma + Sentry | 存活/异常 | 告警触发 | — |
| **服务器** | SSH + systemd | 采集器/静态站/collector | 告警才看 | SSH 密钥 |

### 编辑台（editor_console）技术规格

```
技术栈: FastAPI 子路由(/console/*) + Jinja2 + HTMX（服务端渲染，无前端框架）
认证:   自建 console 会话（密码 hmac 比对 + 可选 IP 白名单；prod 未设密码 fail-closed）
部署:   与 API 同 VPS 同进程
页面:   /console/variants    # 变体精选（今晚 300 条→逐条 A/X/Q）
        /console/daily       # 数据日报（采集/对齐/结算/CLV 自动汇总）
        /console/alerts      # 告警列表（静默合并后）
        /console/tickets     # 工单列表
数据流: narrate 管道 → narrative_pool(status=generated) → 编辑台读→改 status
        → 次日 narrate 读 status=selected 的变体投放
```

### 上线后新增管理对象（v1.0+）

| 对象 | 工具 | 频率 |
|---|---|---|
| 订阅对账 | RevenueCat Dashboard + reconciliation 表 | 月 |
| LLM 成本 | Langfuse | 周 |
| 工单 SLA | Chatwoot 报表 | 日 |
| 功能旗 | PostHog | 按发布 |

### 统一认证策略（8 个工具的账号管理）

| 阶段 | 方案 |
|---|---|
| v0.5–v1.0（1 人） | 各工具独立账号，密码管理器（Bitwarden）统一存储；2FA 全开 |
| v1.5+（2 人） | 自建 SSO（Keycloak/OIDC）复用到 editor_console · 其余工具 SSO 对接 |
| v2.5+（多人） | 统一 SSO（Auth0/Keycloak）· 按角色分权（admin/editor/support） |

### 升级触发

| 触发 | 动作 |
|---|---|
| B 端白标（v2.5） | 上 Directus（MIT，挂 Postgres）作多租户后台 |
| 日活 >3 万 | PG 主从 + PgBouncer 连接池 + 只读副本（海外边缘 API 接副本，逻辑复制） |
| 多人协作 | 编辑台加审计日志 + 细粒度角色 |

## 5. 数据模型（核心表定稿）

```sql
users(id, market, locale, timezone, odds_format, currency, data_region, status)
auth_identities(user_id, provider, identifier_enc, identifier_hash)
consents(user_id, kind, version, granted, at)          -- age_gate/terms/pgsi
push_tokens(user_id, platform, token, locale, opt_in_scopes)
matches(match_id PK, league, kickoff_utc, home, away, status)      -- 全局唯一
market_availability(match_id, market, official_no, single_allowed, sale_close_utc, official_handicap)
team_aliases(source, alias, team_canon, locale, verified_by)        -- human/ai
odds_snapshots(match_id, source, market, line, p_home, p_draw, p_away, captured_at)
  PARTITION BY RANGE(captured_at)  -- 月分区，热13月，冷归档parquet
model_runs(id, version, status shadow/active/retired, params, metrics)
verdicts(id, match_id, model_run_id, market, selection, prob_model, prob_market,
  edge, confidence, gates JSONB, rationale JSONB, locale_texts JSONB,
  sealed_at, prev_hash, payload_hash, version, settled JSONB, clv)
match_facts(match_id PK, score, timeline JSONB, attribution, sealed_prob,
  closing_prob, clv, dead_gate, whatif JSONB, facts_hash)
messages(id, user_id, kind, match_id NULL, payload JSONB, locale,
  created_at, read_at, pushed_at) PARTITION BY RANGE(created_at)
  UNIQUE(user_id, kind, match_id)                        -- 天然幂等去重
bets(id, idempotency_key UNIQUE, user_id, verdict_id NULL, source verdict/manual,
  placed_at, stake, unit_stake, currency, legs JSONB, settled JSONB, clv)
follows(user_id, match_id, created_at, PRIMARY KEY(user_id, match_id))  -- 关注场次（F21，无需购买）
memories(id, user_id, kind, key, value, confidence, source, deleted_at)
memes(id, text, persona, scene[], expires_at, score, source)        -- 梗库（TTL+评分）
parlay_reports(id, user_id, legs JSONB, health_score, subscores JSONB,
  findings JSONB, engine_version, created_at)                       -- 体检报告（编号=id 可验）
subscriptions(user_id PK, plan, status, provider, external_id, period_end)
compliance_events(id, user_id, kind, payload, at)
glossary(locale, source_term, target_term, domain, PRIMARY KEY(locale,source_term,domain))
audit_log(id, actor, action, payload, at, prev_hash)      -- 哈希链
feedback(id, user_id, verdict_id, kind, body, created_at)

-- 采集器（本机运行，30min SFTP 同步至服务器只读副本）
sp_snapshots(match_id, pool, goal_line, sp_h, sp_d, sp_a, captured_at)
sp_matches(match_no, match_id, league, home, away, kickoff, single_flag)

-- 编辑台/变体池
narrative_pool(id, template_id, match_id, locale, persona, variant_text,
  gate_scores JSONB, status TEXT,   -- generated/selected/rejected/deployed
  editor_id TEXT, selected_at TIMESTAMPTZ)

-- 工单（Chatwoot 镜像）
tickets(id, user_id, channel, subject, status, priority, created_at, resolved_at)

-- 对账
reconciliation(id, provider, external_id, amount NUMERIC, status, checked_at TIMESTAMPTZ)
```

铁律：odds_snapshots/audit_log/verdicts(封存后) 只追加；时间 UTC；金额 NUMERIC(12,2)、概率 NUMERIC(6,4)。账本每日根哈希 commit 公开仓库锚定。

---

## 6. API（v1，41 个）

**Auth/账户（9）**：`POST /auth/sms/code` · `POST /auth/login` · `POST /auth/oauth/{google,apple}` · `POST /auth/refresh|logout` · `POST /gate/verify` · `GET|PATCH /me` · `GET /me/export` · `DELETE /me` · `POST /devices`

**内容（18）**：`GET /stream?cursor=`（服务端组装 cards+messages，按时段+状态排序）· `GET /matches?date=` · `GET /matches/on-sale`（今日在售·体彩同步）· `GET /matches/{id}/cost|evidence|why-not` · `POST|DELETE /matches/{id}/follow`（F21）· `GET /verdicts/today|{id}` · `POST /verdicts/{id}/react` · `GET /verdicts/{id}/seal`（哈希详情）· `GET /avoid-list|water-rank|calendar` · `POST /parlay/check` · `GET /parlay/{id}/report` · `POST /vision/scan`（三用）· `GET /ledger` · `GET /agents/{id}/feed` · `POST /chat` · `POST /share/card`（F20）

**采集器数据（内网/只读）**：`GET /matches/on-sale`（今日在售·竞彩同步）· `GET /sp/movements?date=`（SP 移动明细）
**用户数据（6）**：`POST|GET|DELETE /memories` · `GET /bets|/bets/{id}/postmortem` · `GET /weekly-report` · `PATCH /me/persona`（人设切换）

**实时与交互补全（本次审计新增 9 个）**：`GET /matches/{id}/live`（实况卡：timeline+走盘计算）· `POST /matches/{id}/goal-alert`（进球提醒开关）· `GET /parlay/{id}/plans`（方案对比）· `POST /parlay/{id}/confirm`（拆单出票）· `POST /me/rest`（今天不看了）· `PATCH /me/discipline`（连败保护/连败关切）· `GET /analysis-log?match_id=`（分析日志弹层）· `POST /me/under18-lock`（未成年锁定）· `GET /me/comfort`（买后安抚卡内容，也可流内推）
**编辑台（IP 白名单+JWT）**：`GET /console/variants?status=generated` · `POST /console/variants/{id}/decide` (A/X/Q) · `GET /console/daily` · `GET /console/tickets` · `GET /console/alerts`
**商业化/合规（8）**：`POST /billing/rc/webhook|wechat/notify` · `GET /subscription` · `POST /compliance/{self-exclusion,self-assessment,limits}` · `POST /push/preferences` · `GET /push/health`（权限状态）

**规范**：RFC 7807；`Idempotency-Key` 全 POST；免登录白名单（cost/evidence/why-not/ledger/stream.public/gate/on-sale）；限速 chat 20/h、验证码 5/h/IP；**深链路由表随构建配置发布（§3.6）**；错误码→UI 映射：每个 problem+json 类型对应一个预置文案与重试动作，未登记类型兜底"出了点问题，正在修"。

---

## 7. 触达实现

| 项 | 实现 |
|---|---|
| 时序 | 终场 T+2min（live feed）→ 卡片终态+推送；结算 T+2h → 归因消息 |
| 结论发布 | T-3h 动态（用户关注联赛最早停售）；调度器按用户时区分桶 |
| 静默推送 | JPush/Expo content-available；唤醒刷新实况卡；不计频控 |
| 频控 | messages 触达层统一执行：追人 ≤2/日、静默时段、类型 opt-out、(user,kind,match) 唯一 |
| 变体池 | narrate 每晚批跑：10 模板×30 场×10 变体 ×3 人设（理性专家/感性老炮/萌妹萝莉），temperature 0.7–0.9 仅用于灵魂层；白名单+术语校验，兜底模板；变体按 (template, match, locale, persona) 缓存 |
| 人设卡 | 每人设一张 prompt 卡（称呼/口头禅库/情绪规则/必含/禁区/长度 + **3–5 条人手写 few-shot 金句**——灵魂来自示例不是指令）；结构层（数字/结论）与灵魂层（说法）分离：LLM 自由度只在"怎么说" |
| 梗库 | `memes(id, text, persona, scene[], expires_at, score, source)`——梗带 TTL（3 个月无好评自动退役）、用户评分、注入 prompt；与禁用词扫描联动 |
| 编辑台 | 每晚生成→四道闸（白名单/禁用词/出戏检测 LLM 盲评/查重 embedding）→**人工精选 ~120 条入池（OPC 每晚约 10 分钟，编辑台工单）**——品味即护城河 |
| 回收飞轮 | 每周挖掘用户真实对话 → 优质回话洗入 few-shot 与梗库；出戏率/重复率/👍率三指标周报 |
| 成本 | 10 万 DAU 增量 ≈¥1K/月（变体 ¥50 + 按需对话 ¥600 + 通道 ¥0–500） |

---

## 8. 模型与回测

### 8.0 依赖隔离（架构约束）

```
packages/model/           # 唯一允许 import penaltyblog 的包
  predictor.py            # 稳定接口：predict(match_id) -> ScoreMatrix
  strength.py             # 球队强度（时间衰减、跨赛季衔接）
  calibrate.py            # isotonic 分联赛分桶
  fusion.py               # logit 加权 + 每季重估
  adapters/               # 数据源适配（换源不动业务）
verdict/ ingest/ ...      # 业务层只 import packages.model
```
`penaltyblog` 锁 `~=1.13`（次版本），Python minor 版本锁于 Docker 镜像，CI 加 Cython 编译冒烟。

### 8.1 penaltyblog 能力映射与缺口

| 我们的模块 | penaltyblog 提供 | 需自建 |
|---|---|---|
| 球队强度 | DixonColes / BayesianGoalModel / Hierarchical | 时间衰减调参、跨赛季衔接 |
| 玩法概率 | home_draw_away / 亚盘 / 大小球 | 竞彩整数让球映射、总进球/半全场/比分 |
| 去水 | overround 解码（简单归一化） | Shin 法（或引 mberk/shin） |
| 历史数据 | football-data/FBref/Understat/ClubElo | 官方竞彩 SP 历史（必自采） |
| 回测 | 拟合与预测 | walk-forward、CLV、影子模式、版本管理 |
| 校准 | ❌ | isotonic（sklearn） |
| 融合权重 | ❌ | logit 加权自写 |
| 实时赔率/阵容/比分 | ❌（历史库） | 商业 API |

**结论：覆盖约 35%，省的是最难写的那部分；不得假设"模型层已完备"。**

### 8.2 数据契约（Pandera）

每张核心表一个 `DataFrameModel`，两级严重度：

```python
class OddsSnapshot(pa.DataFrameModel):
    price_home: float = pa.Field(gt=1.0, lt=1000)
    captured_at: datetime = pa.Field(le="now")          # WARN：不得为未来
    implied_sum: float = pa.Field(ge=1.0, le=1.3)       # ERROR
    match_id: str = pa.Field(str_matches="matches")     # ERROR：外键存在
    class Config: strict = True
```

ERROR 阻断入库并告警；WARN 记录并进日报。空抓取（当日 0 行）触发独立告警。

### 8.3 模型升级阶梯（实测基线：v1.1 = 0.9104 vs 市场 0.9092）

| Level | 方法 | 新增数据 | 预期 log loss | 状态 |
|---|---|---|---|---|
| v1.0 | DC + xG 强度 + 主场 | 赛果22.5k + xG10.7k + 开盘赔率 | 0.9191 | ✅ 已回测 |
| **v1.1** | **+ 收缩纪律（>8pp 场次偏差砍半）** | — | **0.9104** | ✅ 已实现（model_v1_1.py） |
| v1.2 | + LightGBM 残差模型（~40 特征：xG趋势/盘口移动/赛程密度/升班马标记） | 已有数据工程即可 | ~0.905 | W2 |
| v1.3 | + 贝叶斯层级（弱队向联赛均值收缩，治 40% 大偏差的根因） | penaltyblog 自带 | ~0.900 | W3 |
| v1.4 | + 阵容条件化（强度×上场球员权重比） | API-Football $19/月 | ~0.895 | v1.0 产品版 |
| v2.x | + 集成加权（DC/LGBM/贝叶斯按近期表现自动配权） | + 事件流(Opta $几百/月，5万DAU后) | 0.885–0.895（行业天花板） | 远期 |

**收缩纪律（v1.1 已验证有效，永久保留）**：模型 vs 市场偏差 >8pp 的场次，模型概率砍半向市场靠拢。首测：40.3% 场次触发，log loss 0.9191→0.9104。触发比例若长期 >30%，说明强度估计对实力突变队（升班马/大引援）适配差 → 进 v1.3 层级先验解决。

### 8.4 数据三层金字塔

**L1 已到手**：赛果 22,554 场(20年×5联赛) · 开/收盘赔率 120+列 · xG 10,707 场(6季) · 竞彩 SP 快照(采集中，4周后~8万)

**L2 缺口（按 ROI 排序）**：
| 数据 | 来源 | 成本 | 何时 |
|---|---|---|---|
| 阵容/伤停/停赛（首发后 60min 窗口=市场未定价增量） | API-Football | $19/月 | v1.0 |
| 更多联赛（法乙/荷甲/英冠——冷门=深水=标签更有用） | football-data 免费 | ¥0 | v1.5 |
| 裁判（红牌/点球率） · 天气（风=大球杀手） | 公开抓取 | ¥0-50/月 | v1.5 可选 |
| 事件流（传球/抢断级） | Opta/StatsBomb | $几百/月 | v2.5+（5万DAU后） |
| ~~球员身价/球迷投票/新闻情感~~ | 不买：噪声大/已被盘口消化/不如伤停名单 | — | 明确不做 |

**L2 工程难点**：多源拼接的队名映射（team_aliases 表 + Meilisearch 容错）——数据工程 80% 工作量在对齐不在抓取。

### 8.5 训练协议（铁律）

- **walk-forward 时间切分**（禁止随机切分=泄露未来）；只用收盘价评估
- 校准必须 out-of-fold；任何特征不得含赛后信息（含"全场射门"）
- 每次训练固定产出：log loss vs 市场（≤持平可接受）/ 校准曲线（<3pp）/ 大偏差占比（<20%目标）/ 分联赛 log loss
- 自动化：每周日 02:00 腾讯云定时重训 → 影子对比 4 周 → 达标晋升（§8.3 晋级线）
- golden dataset：对齐 500 场 + 回测快照，回归必跑

### 8.6 LLM 线与预测线的关系（防混淆）

- **预测准确率 100% 来自 §8.1–8.5 统计模型线（数学）**——LLM 不参与预测，换更强的 LLM ≠ 预测更准
- LLM 线（GLM-4-Flash 主力 / DeepSeek-V3 质量备胎 / 未来 SFT→7B 蒸馏）只负责：判决文案、变体池、截图理解
- LLM 升级触发：SFT 于日调用>5000；蒸馏自托管于日调用>5万（OpsBlueprint §七）
- 后训练三阶段：SFT（人设文案 3-5k 条，编辑台产出即训练集）→ DPO（诚实归因偏好对 2k 条）→ 蒸馏（GLM-4 蒸 20k 进 Qwen-7B）

---

## 9. AI 开发规范

**单一事实源**：OpenAPI 3.1 为接口唯一真相 → 双端 codegen（禁手写客户端）；DB schema 以 alembic 迁移为准。

**CI 七门禁（全部硬性）**：类型 strict 零错误 · lint 零警告 · 核心模块覆盖 ≥85%（align/model/verdict/billing/compliance）· **禁用词全仓扫描**（PRD §10 全表，阻断）· 伪本地化 en-XA 构建通过 · 契约测试快照 · golden dataset 回归（对齐 500 场 + 回测快照）。

**上下文工程**：每模块 `AGENTS.md`（职责/公共接口/不变量/已知坑）；`docs/adr/` 决策记录；单文件 ≤400 行；import-linter 禁循环依赖。

**人工把关五清单（AI 不得自主合并）**：支付回调与对账 · 自排除/限额/年龄门 · 封存哈希链与结算 · 权限中间件与免登录白名单 · 密钥/迁移/删除数据。

**发布**：PostHog flag 1%→10%→100%，每档 ≥48h；模型 PR 必附 walk-forward 回测结果。

---

## 10. 全球化实现

locale 协商 path>cookie>系统；market profile YAML（源/edge 论点/LegalSlot/龄限/支付/联赛/禁用词/KYC 开关/**auth_methods/persona_packs（3 人设 prompt 卡）**）；glossary PR+双人审批；`OddsText/Money/MatchTime` 纯函数+单测覆盖四格式。

---

## 11. 安全

AEAD 加密手机号（KMS）· refresh 旋转+复用检测 · 自排除中间件（451+helpline）· 备份 RTO 1h/RPO 5min 季度演练 · 密钥 90 天轮换 · 防薅设备指纹 · 成本标签字段水印。

---

## 11.5 SLO 与告警

| 指标 | SLO | 告警阈值 |
|---|---|---|
| API p99 | <300ms | >500ms 持续 5min |
| 封存成功率 | >99.9% | 连续 2 次失败 |
| 结算延迟 | <2h | >3h |
| 采集可用性 | >99% | 单源连续 3 次空抓 |
| 对齐匹配率 | >98% | 单日 <98% |
| 推送到达率 | >95% | 单日 <90% |
| 账本锚定 | 100%/日 | 漏锚一次 |
| 接口错误率 | <0.5% | >2% |

**告警路由**：Sentry（异常）× uptime-kuma（存活）× n8n（业务告警→值班员 runbook）× 每日数据日报进编辑台。
**静默规则**：同类告警 30min 合并；夜间仅"封存/结算/支付"三类升级叫人。

---

## 12. 成本（M1 实测口径）

| 项 | 月 |
|---|---|
| Vercel+EAS | $0–40 |
| VPS(api/pg/redis) | ¥60 |
| 数据源（赔率/阵容/比分） | ¥300–800 |
| LLM（变体+对话） | ¥50–150 |
| 短信/备份对象存储 | ¥10–40 |
| JPush/证书 | 0 |
| **合计** | **<¥1,000** |

---

## 13. 里程碑（8 周）

| 周 | 后端 | App |
|---|---|---|
| W1 | 三数验证**已跑完**（①②通过 ③换竞彩 SP 重测，见 PRD §10.5）；**竞彩 SP 采集器 v0.1（✅ 已上线·本机家宽·1887 快照/18.5h 零中断）**；Pandera 全表契约；betfair 历史流评估；**主体/软著/备案启动** | — |
| W1+ | **竞彩 SP 采集器 v0.1（已上线）**：本机家宽出口（体彩 WAF 拒机房 IP）→ SQLite → 30min SFTP 备份服务器 /home/ubuntu/jieqiu-sp/；5min 轮询，失败 20 次退出换路；**升级路径：家宽常开不稳时换 4G 热点/住宅代理** | 数据积累 3–4 周后数②③重测 |
| W2 | schema+stream 组装 API + **xG↔赛果跨源对齐**（队名映射 200 条+模糊匹配）；**采集器 v0.2（加密采样+赛果回填）** | Expo 骨架+3 屏；TestFlight/蒲公英壳 |
| W3 | 三道闸+cost/evidence/why-not | 详情页+成分标签+依据卡 |
| W4 | verdicts 哈希链+公开锚定+narrate(zh) | 流+账本 Web+流式生成 |
| W5 | messages+settle 扇出+两级推送(JPush/Expo)+PostHog+连败保护 | 实况卡+关注+通知软请求+未读线 |
| W6 | 卡片路由+vision 三用+记忆 | 串关体检全流程+拍票+对话流 |
| W7 | 稳定性+频控打磨 | 内测 30 人 |
| W8 | 修复+版本门 | 内测迭代 |

---

## 14. 附录

- 赔率四格式互转纯函数（欧/港/印尼/美式）
- 对齐：联赛映射→±1 天→别名精确→编辑距离≥0.85→人工队列（日≤5），匹配率<98% 告警
- i18n key：`域.页面.槽位[.状态]`
- 环境变量：`SUPABASE_URL/ANON/SERVICE · RC_API_KEY · JPUSH_APPKEY · ODDS_API_KEY · LINEUP_API_KEY · LIVE_SCORE_KEY · LLM_API_KEY · KMS_KEY · MARKET_DEFAULT · DATA_REGION · BETFAIR_USER/CERT/APPKEY（M2）`
- **数据源适配层接口**（换源不动业务）：
```python
class SourceAdapter(Protocol):
    name: str
    def fetch_fixtures(self, date: date) -> pd.DataFrame: ...
    def fetch_odds(self, match_id: str) -> pd.DataFrame: ...
    def fetch_lineups(self, match_id: str) -> pd.DataFrame | None: ...
    # 返回值一律经 Pandera schema 校验，不合规抛 DataContractError
```

*TechSpec v2.1 完*
