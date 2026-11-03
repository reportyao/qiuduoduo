# 「解球」技术开发文档 v1.0

| 项目 | 内容 |
|---|---|
| 版本 | v1.0 |
| 日期 | 2026-11-01 |
| 配套文档 | 《解球 PRD v4.0 · 全球版》 |
| 范围 | 前端 / 后端 / 数据模型 / API / i18n 实现 / 采集与模型 / 部署运维 |

---

## 1. 技术选型总览

| 层 | 选型 | 理由 |
|---|---|---|
| 前端框架 | **Next.js 15 (React) PWA** | 一套代码出 H5（微信内置）+ PWA（全球）；App Router 原生支持 `/{locale}` 路由 |
| i18n | **next-intl**（ICU MessageFormat） | 路由级 locale、复数/性别、运行时切换 |
| 状态 | Zustand + TanStack Query | 轻量，服务端状态缓存友好 |
| 样式 | Tailwind + CSS 变量设计令牌 | 明暗双主题、文本膨胀容忍 |
| 后端 | **Python FastAPI**（模块化单体） | 数据/模型生态全在 Python；单体起步，按模块拆 |
| 数据库 | PostgreSQL 16 | JSONB、时区、约束；DuckDB 做本地回测分析 |
| 缓存/队列 | Redis | 限速、热缓存；M2 换 Celery + RabbitMQ |
| 定时任务 | APScheduler（单机）→ Celery Beat | 采集/封存/结算/重训 |
| LLM | GLM-4-Flash（文本）/ GLM-4V（截图） | 国内可用、便宜；接口抽象层可换 |
| 模型 | numpy/pandas + LightGBM + PyMC（可选） | DC 模型 20 行起步，禁止深度学习起步 |
| 部署 | Docker Compose 单机（2C4G ¥100/月）→ M2 拆分 | |
| 监控 | Sentry + uptime-kuma + 结构化日志 | |

**明确不用**：微服务（M1）、Kubernetes、深度学习、自训 LLM。

---

## 2. 系统架构

```
                    ┌────────── 采集层（cron，全部只追加）──────────┐
                    │ sporttery SP/单关/停售 │ 国际赔率(商业API)    │
                    │ 阵容伤停(付费API)      │ xG(FBref) / Elo     │
                    └───────────┬───────────────────────────────┘
                                ▼
                     原始层 parquet/表（按日分区，永不 UPDATE）
                                ▼
                     对齐层（队名映射 + 模糊匹配 → 统一 match_id）
                                ▼
        ┌───────────────────────┼──────────────────────────┐
        ▼                       ▼                          ▼
  [模型层]                 [市场层]                    [情报层]
  DC比分矩阵               Shin去水→公允价             LLM抽取阵容/动机
  校准(isotonic)           跨源分歧度                  （只出特征，不出概率）
  融合(logit加权)          官方SP时间序列
        └───────────────────────┬──────────────────────────┘
                                ▼
                     [决策层] edge·置信分级·三道闸·终审排序
                                ▼
                     [叙述层] LLM per-locale 生成（数字白名单+术语校验）
                                ▼
        ┌───────────┬───────────┴──────────┬─────────────┐
        ▼           ▼                      ▼             ▼
   [封存结算]   [API 层 FastAPI]      [推送层]      [账本]
   哈希链只追加   REST + JWT           微信/Email/   公开页+审计
                                     Web Push
```

---

## 3. 前端设计

### 3.1 工程结构

```
apps/web (Next.js)
  src/app/[locale]/            # zh-CN / en ...
    (stream)/page.tsx          # 判决流首页
    verdicts/[id]/page.tsx
    matches/[id]/cost/page.tsx
    ledger/page.tsx
    auth/login/page.tsx
    gate/page.tsx              # 年龄门
    me/...                     # 我的（preferences/notifications/discipline/
                               #   compliance/subscription/privacy/memories/alpha）
    agents/page.tsx
  src/components/              # 设计系统组件（见 3.3）
  src/lib/{api,i18n,money,odds,time}/
  messages/{zh-CN,en}.json     # 全部文案，禁止硬编码
```

### 3.2 i18n 实现规范

| 项 | 规范 |
|---|---|
| 路由 | `/{locale}/...`，`middleware` 按 `Accept-Language + cookie` 协商重定向 |
| 文案 | 全部走 `messages/*.json`，key 命名 `域.组件.槽位`（如 `verdict.card.gates`） |
| 复数/占位 | ICU：`{count, plural, ...}`；禁止字符串拼接 |
| 伪本地化 | `en-XA`（字符膨胀×1.3）纳入 CI，验证文本膨胀不破版 |
| 术语 | `glossary` 后端表下发；LLM 输出与 UI 均受约束 |
| RTL | 只用 CSS 逻辑属性（`ps/pe/ms/me`），预设 `dir=rtl` 不启用 |
| 数字/时间 | `Intl.NumberFormat` / `Intl.DateTimeFormat`；封装 `<Money>` `<MatchTime>` `<OddsText>` 三组件，全局禁手写格式 |

### 3.3 核心组件（设计系统）

| 组件 | 职责 | 关键点 |
|---|---|---|
| `VerdictCard` | 判决卡 | 默认层/为什么 L1–L3 分层；`bought/why/disagree` 三事件 |
| `GateChips` | 三关一行 chips | 价/市/模，颜色语义唯一 |
| `ConfidenceGauge` | 置信仪表 | SVG 弧线，tabular-nums |
| `CostLabel` | 成分标签 | 免费，无登录可看 |
| `LegalSlot` | 合规插槽 | `market` prop → 后端配置渲染，**不可被页面文案覆盖** |
| `OddsText` | 赔率展示 | 存储欧赔 → 按用户格式（欧/港/印尼/美式）转换 |
| `Money` | 金额展示 | 币种/单位制切换，负号 hyphen-minus |
| `MatchTime` | 比赛时间 | 绝对+相对+时区+倒计时四件套 |
| `SystemState` | 5 系统状态 | 骨架/延迟/降级/结算中/故障 |
| `SuggestionChips` | 话术层 | 可配置轮换，埋点 `chip_click` |
| `AgentCard` | 助手人格化 | 含实时状态行（WebSocket 轮询） |

### 3.4 性能预算

LCP < 2.5s（4G）；流首页 JS < 180KB gzip；图片 `next/image`；判决卡服务端渲染。微信内禁 PWA 安装提示，全球 PWA 可安装（离线看最近账本快照）。

---

## 4. 后端设计

### 4.1 模块划分（模块化单体）

```
app/
  auth/          # 注册登录、JWT、设备、年龄门
  users/         # 偏好、时区、赔率格式、订阅状态
  ingest/        # 各数据源适配器 + 限速器
  align/         # 跨源对齐（队名映射+模糊匹配）
  model/         # DC、校准、融合、影子模式
  market/        # 去水、分歧度、官方SP序列
  verdict/       # 三道闸、终审、封存、结算、CLV
  narrate/       # LLM 叙述（per-locale、白名单、术语校验）
  notify/        # 微信模板/Web Push/Email，本地时区调度
  billing/       # 微信支付、Stripe、订阅状态机
  compliance/    # LegalSlot 配置、自排除、限额、PGSI
  i18n/          # glossary、翻译管理
  audit/         # 只追加审计日志
```

### 4.2 数据模型（PostgreSQL 核心表）

```sql
-- 用户与账户
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  market TEXT NOT NULL DEFAULT 'CN',          -- CN / UK / US-XX / GLOBAL
  locale TEXT NOT NULL DEFAULT 'zh-CN',
  timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
  odds_format TEXT NOT NULL DEFAULT 'decimal',-- decimal/hk/indo/american
  currency TEXT NOT NULL DEFAULT 'CNY',
  status TEXT NOT NULL DEFAULT 'active',      -- active/excluded/deleted
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE auth_identities (
  user_id UUID REFERENCES users, provider TEXT,  -- phone/wechat/google/apple/email
  identifier_enc BYTEA,                          -- 手机号等加密存储
  PRIMARY KEY (provider, identifier_hash)
);
CREATE TABLE consents (
  user_id UUID, kind TEXT,          -- age_gate/terms_v/marketing/pgsi
  version TEXT, granted BOOL, at TIMESTAMPTZ,
  PRIMARY KEY (user_id, kind, version)
);
CREATE TABLE push_tokens (
  user_id UUID, platform TEXT, token TEXT, locale TEXT,
  PRIMARY KEY (user_id, platform, token)
);

-- 数据域（只追加铁律）
CREATE TABLE team_aliases (                 -- 跨源队名映射
  alias TEXT, source TEXT, team_canon TEXT, locale TEXT,
  PRIMARY KEY (source, alias)
);
CREATE TABLE matches (
  match_id TEXT PRIMARY KEY,                -- 内部统一ID
  market TEXT, league TEXT, kickoff_utc TIMESTAMPTZ,
  home_team TEXT, away_team TEXT,
  official_no TEXT, single_allowed BOOL, sale_close_utc TIMESTAMPTZ,
  official_handicap SMALLINT
);
CREATE TABLE odds_snapshots (
  match_id TEXT, source TEXT, market TEXT, line NUMERIC,
  p_home NUMERIC, p_draw NUMERIC, p_away NUMERIC,
  captured_at TIMESTAMPTZ,
  PRIMARY KEY (match_id, source, market, line, captured_at)
);

-- 判决与信任
CREATE TABLE verdicts (
  id UUID PRIMARY KEY, match_id TEXT, model_run_id UUID,
  market TEXT, selection TEXT,
  prob_model NUMERIC, prob_market NUMERIC, edge NUMERIC,
  confidence TEXT, gates JSONB,           -- 三关明细
  rationale_payload JSONB,                 -- 结构化数字（白名单源）
  locale_texts JSONB,                      -- {zh-CN: "...", en: "..."}
  sealed_at TIMESTAMPTZ, payload_hash TEXT,
  version INT DEFAULT 1,                   -- 变更出新版本，双公示
  settled JSONB, clv NUMERIC
);
CREATE TABLE model_runs (
  id UUID PRIMARY KEY, version TEXT, status TEXT,  -- shadow/active/retired
  params JSONB, metrics JSONB, started_at TIMESTAMPTZ
);

-- 用户行为
CREATE TABLE bets (
  id BIGSERIAL PRIMARY KEY, user_id UUID, verdict_id UUID,
  placed_at TIMESTAMPTZ, stake NUMERIC, currency TEXT,
  legs JSONB, unit_stake NUMERIC,          -- 单位制
  settled JSONB, clv NUMERIC
);
CREATE TABLE memories (
  id BIGSERIAL PRIMARY KEY, user_id UUID, kind TEXT, key TEXT,
  value JSONB, confidence NUMERIC, source TEXT,   -- user_said/inferred/system
  created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ, deleted_at TIMESTAMPTZ
);
CREATE TABLE budgets (
  user_id UUID, weekly_limit NUMERIC, spent NUMERIC,
  streak_lose INT, protection BOOL DEFAULT false,
  PRIMARY KEY (user_id)
);

-- 商业化与合规
CREATE TABLE subscriptions (
  user_id UUID PRIMARY KEY, plan TEXT, status TEXT,  -- trial/active/past_due/canceled
  provider TEXT, external_id TEXT, current_period_end TIMESTAMPTZ
);
CREATE TABLE compliance_events (
  id BIGSERIAL PRIMARY KEY, user_id UUID, kind TEXT,  -- self_exclusion/limit/pgsi
  payload JSONB, at TIMESTAMPTZ
);
CREATE TABLE glossary (
  locale TEXT, source_term TEXT, target_term TEXT, domain TEXT,
  PRIMARY KEY (locale, source_term, domain)
);
CREATE TABLE audit_log (                    -- 只追加
  id BIGSERIAL PRIMARY KEY, actor TEXT, action TEXT,
  payload JSONB, at TIMESTAMPTZ
);
```

**铁律**：`odds_snapshots`/`audit_log`/`verdicts`（封存后）只追加；时间一律 UTC 存储。

### 4.3 定时任务表

| 任务 | 频率 | 说明 |
|---|---|---|
| `ingest_odds` | 10 min；停售前 30 min 密集 60s | 多源限速，异常加密采样 |
| `ingest_lineups` | 事件驱动 | 首发公布触发重算 |
| `align_matches` | 5 min | 新场次跨源对齐，未匹配进人工队列 |
| `model_run` | T-6h / T-1h / T-15m | 概率重算，写 model_run |
| `seal_verdict` | T-30m | 封存 + 哈希 + per-locale 叙述 |
| `settle` | T+2h | 自动结算 + CLV + 归因 |
| `push_scheduler` | 每用户本地 19:00 等 | 按时区分批 |
| `weekly_retrain` | 周日 | walk-forward 重训 |
| `shadow_eval` | 每周一 | 影子模型对比，4 周晋级 |
| `fx_rates` / `glossary_sync` | 每日 | 汇率缓存 / 术语下发 |

### 4.4 LLM 叙述层

```python
def narrate(payload: dict, locale: str) -> str:
    nums = whitelist(payload)                     # payload 内全部数字
    for attempt in range(2):
        text = llm(PROMPT[locale], payload_json=payload, temperature=0)
        bad = audit_numbers(text, nums)           # 非白名单数字
        bad += audit_glossary(text, locale)       # 术语违规
        if not bad:
            return text
    return template_fallback(payload, locale)     # 兜底：模板拼接，无 LLM 也能出
```

- prompt 模板按 content_locale 存于 `messages`（代码库）+ glossary 注入
- LLM 只翻译结构为语言，**永不产生数字**
- 成本控制：Flash 级模型 + 兜底模板，日判决 < 50 条，月成本 < ¥100

---

## 5. API 规格（v1，共 30 个）

### 认证与账户
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/auth/sms/code` | 发验证码（CN） |
| POST | `/v1/auth/login` | 手机+验证码 / email+code 登录 |
| POST | `/v1/auth/oauth/{wechat,google,apple}` | OAuth 回调换取 token |
| POST | `/v1/auth/refresh` / `logout` | JWT 15min + refresh 30d |
| POST | `/v1/gate/verify` | 年龄门（年份+市场），写 consents |
| GET/PATCH | `/v1/me` | 资料+偏好（locale/timezone/odds_format/currency/market） |
| GET | `/v1/me/export` | GDPR/PIPL 导出任务 |
| DELETE | `/v1/me` | 注销（7 天冷静期） |
| POST | `/v1/devices` | push token 注册 |

### 内容与决策
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/v1/stream?cursor=` | 判决流（按 locale 渲染文案） |
| GET | `/v1/matches?date=&league=` | 场次列表 |
| GET | `/v1/matches/{id}/cost` | 成分标签（免登录） |
| GET | `/v1/verdicts/today` / `{id}` | 判决（含 why L1–L3） |
| POST | `/v1/verdicts/{id}/react` | `bought{stake,unit} / why / disagree{reason}` |
| GET | `/v1/avoid-list` / `/v1/water-rank` | 避雷榜 / 水位榜 |
| GET | `/v1/ledger` | 公开账本（免登录，公开缓存） |
| POST/GET/DELETE | `/v1/memories` | 记忆 CRUD |
| GET/PATCH | `/v1/budget` | 预算与连败保护状态 |
| POST | `/v1/chat` | 助手对话兜底（SSE） |
| POST | `/v1/vision/screenshot` | 截图鉴别（M2） |
| GET | `/v1/agents` / `/v1/agents/{id}/feed` | 助手列表/动态 |

### 商业化与合规
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/billing/wechat/prepay` / `/v1/billing/stripe/checkout` | 下单 |
| POST | `/v1/billing/webhooks/{wechat,stripe}` | 回调（验签） |
| GET | `/v1/subscription` | 状态/恢复购买 |
| POST | `/v1/compliance/self-exclusion` | 自排除（24h/7d/30d/永久） |
| POST | `/v1/compliance/self-assessment` | PGSI 提交 |
| POST | `/v1/compliance/limits` | 限额（调高 24h 冷却） |

**鉴权**：JWT Bearer；免登录白名单：`cost / ledger / stream(只读脱敏) / auth / gate / glossary`。
**限速**：Redis 令牌桶，验证码 5 次/h/IP，chat 20 次/h/用户。

---

## 6. 全球化后端实现

| 项 | 实现 |
|---|---|
| locale 协商 | 中间件：URL path > cookie > Accept-Language > market 默认 |
| market profile | `config/markets/{CN,UK,US-XX,GLOBAL}.yaml`：数据源、edge 论点、合规件文、年龄段、支付方式、联赛集、禁用词 |
| LegalSlot 内容 | 来自 market profile，API 下发，前端只渲染 |
| 三语言解耦 | UI：`messages/*.json`；内容：`verdicts.locale_texts`；数据：`team_aliases.locale` |
| 时区 | 引擎全 UTC；`MatchTime` 组件用用户 timezone 渲染；推送调度按用户时区分批 |
| 汇率 | 每日任务缓存，`Money` 组件仅显示转换 |
| 赔率格式 | 转换函数纯函数化，单元测试覆盖四格式互转 |

---

## 7. 安全与合规实现

| 项 | 实现 |
|---|---|
| 认证 | JWT access 15min + refresh 30d（旋转+复用检测）；设备表绑定 |
| 敏感数据 | 手机号/email AEAD 加密（KMS 主密钥），哈希列用于查找 |
| 年龄 | 自声明存 consents（不含精确生日）；KYC 预留 Sumsub 适配器 |
| 自排除 | 中间件级拦截：excluded 用户请求判决/记账接口返回 451 + helpline |
| 数据权利 | 导出任务 + 注销冷静期 job；审计日志支撑 |
| 支付合规 | CN 微信/支付宝"软件服务"类目；全球 Stripe + Paddle 备选（MoR） |
| 防抓取自身 | 账本页公开数据加水印 ID，便于溯源滥用 |

---

## 8. 部署与运维

```
docker-compose: web(Next) / api(FastAPI) / worker(APScheduler) / postgres / redis / caddy
```

| 项 | 方案 |
|---|---|
| 环境 | dev / staging / prod；配置走 env（见下） |
| CI | GitHub Actions：lint → test → 伪本地化检查 → build → 部署 |
| 备份 | PG 每日全量 + WAL；快照表异地同步 |
| 监控 | Sentry（前后端）、uptime、任务心跳（seal/settle 失败即告警） |
| 成本 | 单机 ¥100/月 + API（数据 ~¥500 + LLM ~¥100）≈ **< ¥1,000/月**（M1） |

**关键 env**：`DATABASE_URL / REDIS_URL / JWT_SECRET / KMS_KEY / ODDS_API_KEY / LINEUP_API_KEY / LLM_API_KEY / WX_APPID / STRIPE_KEY / MARKET_DEFAULT`。

---

## 9. 里程碑映射（对应 PRD §10）

| 里程碑 | 后端交付 | 前端交付 |
|---|---|---|
| **M1（W1–8）** | ingest/align/verdict/seal/settle/narrate(zh)/notify/账本 API | 判决流+判决详情+成本标签+避雷+预算+归因+账本+买了流程（zh-CN，匿名优先） |
| **M1.5（W9–12）** | auth 全量/users/billing(微信)/memories/i18n 基建/en 内容 | 登录注册/我的七组页/票单/SP 提醒/助手×2/en 全站 |
| **M2（W13–20）** | market profile 插拔/Stripe/compliance/vision/影子模式 | 合规中心/订阅/截图鉴别/日历/冷门/周报/es+pt-BR |

---

## 10. 附录

### 10.1 i18n key 命名规范

```
{域}.{页面|组件}.{槽位}[.{状态}]
verdict.card.gates.price        verdict.card.gates.market
stream.empty.title              stream.empty.course
me.preferences.language.label   auth.login.error.ratelimit
```

### 10.2 赔率格式转换

```
欧赔 d：港盘 h=d-1；印尼 i=±1/d'；美式 a=±100×(d-1)（d≥2 正，d<2 负）
存储恒为欧赔；<OddsText value={1.85} format={user.odds_format}/>
```

### 10.3 跨源对齐算法（对齐层核心）

1. 联赛映射表 → 2. 开球时间 ±1 天 → 3. 主客队别名精确匹配（`team_aliases`）→ 4. 未中：归一化编辑距离 ≥ 0.85 → 5. 仍未中：人工队列（日 ≤ 5 场）。**匹配率 < 98% 触发告警。**

---

*TechSpec v1.0 完 · 与 PRD v4.0 配套使用*
