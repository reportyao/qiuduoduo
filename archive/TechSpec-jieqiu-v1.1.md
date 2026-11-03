# 「解球」技术开发文档 v1.1

| 项目 | 内容 |
|---|---|
| 版本 | v1.1（吸收深度审查报告 v1.0 全部技术修复） |
| 日期 | 2026-11-01 |
| 配套 | PRD v4.1、Roadmap v1.0、Review v1.0 |
| 基准 | 100 万注册（DAU 15–20 万）终态、全 AI 开发流程 |

---

## 1. 技术选型总览

| 层 | 选型 | 理由 |
|---|---|---|
| 前端 | Next.js 15 PWA（App Router） | H5（微信）+ PWA（全球）一套代码；`/{locale}` 原生 |
| i18n | next-intl（ICU） | 复数/性别、运行时切换 |
| 状态 | Zustand + TanStack Query（SWR 缓存策略防刷新风暴） | |
| 样式 | Tailwind + CSS 变量令牌 | 双主题、文本膨胀容忍 |
| 后端 | Python FastAPI 模块化单体（无状态，水平扩展） | 数据/模型生态；单体≠单机 |
| API 契约 | **OpenAPI 3.1 单一事实源 → 双端 codegen** | AI 开发核心（§12） |
| 数据库 | PostgreSQL 16（分区）+ PgBouncer + 读副本 | 读写分离路径明确 |
| 分析库 | ClickHouse（**阶段引入**，触发器见 §2.3） | 事件/指标 |
| 缓存/队列 | Redis（哨兵）→ Kafka（阶段引入） | |
| 定时 | APScheduler（单机锁）→ Celery Beat → K8s CronJob | |
| LLM | GLM-4-Flash（文本）/ GLM-4V（截图）；分层路由 | 成本可控 |
| 模型 | numpy/pandas + LightGBM + isotonic + 影子模式 | 禁止深度学习起步 |
| 观测 | **Prometheus + Grafana + OpenTelemetry + Sentry** | 指标/追踪/错误三线 |
| 部署 | Docker Compose → K8s（多可用区）→ 双区域（CN/Global） | §2 阶梯 |
| CI/CD | GitHub Actions + 禁用词扫描 + 伪本地化 + 契约快照 | |

**不用**：微服务（至 10 万 DAU 前）、Kubernetes（前 6 个月）、自训 LLM、GraphQL。

---

## 2. 规模架构（本次重构核心）

### 2.1 四级架构阶梯

| 级 | 规模 | 架构 | 估月成本 |
|---|---|---|---|
| **S1** | ≤5K DAU | 单机 compose：web/api/worker/pg/redis/caddy | <¥1K |
| **S2** | ≤3 万 DAU | 2×api（4C8G）+ PgBouncer + PG 读副本 + Redis 哨兵 + CDN | ¥3–6K |
| **S3** | ≤10 万 DAU | K8s 多可用区：api×N 无状态 / PG 主从+分区 / Kafka / ClickHouse(事件) / 推送 worker 池 | ¥15–30K |
| **S4** | 100 万注册/20 万 DAU | 双区域（CN 栈 + Global 栈，数据驻留隔离）+ 全站 CDN + 灰度发布 + SRE 值班 | ¥60–120K |

### 2.2 双区域数据驻留（PIPL/GDPR）

```
CN 栈（境内云，ICP 备案）          Global 栈（EU/US）
  *.jieqiu.cn  ──网关分流──  *.jieqiu.com
  CN 用户数据不出境               EU/US 用户数据
  users.data_region='cn'          data_region='global'
  账号不互通；跨区访问只读公开账本（无个人信息）
```

落库时定区；跨区仅同步**公开内容**（判决文案/账本，无 PII）。

### 2.3 规模触发器（升级条件表，运维 SOP）

| 触发指标 | 阈值 | 动作 |
|---|---|---|
| DAU | >5K | 上 PgBouncer + 读副本 + Redis 哨兵（S1→S2） |
| API p99 | >300ms 持续 3 天 | api 横向扩容 / 慢查询专项 |
| DAU | >3 万 | K8s + Kafka（S2→S3） |
| events 行数 | >500 万/天 | 迁 ClickHouse |
| odds_snapshots | >5000 万行 | 归档管道上线（parquet） |
| LLM 月费 | >¥5K | 分层路由审计 + 缓存命中率专项 |
| 推送队列积压 | >10 分钟 | 推送 worker 分片扩容 |
| PG 主库 | >200GB | 纵深评估分库（按 data_region 已天然切分） |

---

## 3. 系统架构图

```
┌─ 采集层（只追加；限速；事件驱动加密采样）──────────────┐
│ 竞彩SP/单关/停售 │ 国际赔率(商业API) │ 阵容伤停 │ xG/Elo │
└────────────┬───────────────────────────────────┘
             ▼ 原始层（分区表+parquet，永不 UPDATE）
      对齐层（team_aliases + 模糊匹配 → 全局唯一 match_id）
             ▼
   ┌─────────┼──────────┐
   ▼         ▼          ▼
 模型层     市场层      情报层
 DC/校准/   Shin去水/   LLM抽取
 融合/影子  分歧度/SP序列 （只出特征）
   └─────────┼──────────┘
             ▼ 决策层：三道闸·edge·置信·终审
             ▼ 叙述层：LLM per-locale（白名单+术语校验+模板兜底）
             ▼ 封存结算：哈希链 + 每日根哈希锚定公开仓库
   ┌─────────┬─────────┬──────────┐
   ▼         ▼         ▼          ▼
 API层     推送层      账本       审核/风控
 (public:CDN  (企微/WebPush/ （公开页     (UGC审核/
  private:JWT) Email/短信)   +审计)     反爬/防薅)
```

---

## 4. 前端设计

### 4.1 结构（不变，补两点）

- `GET /stream` 拆分：`/stream/public`（CDN 可缓存，per-locale，TTL 5min）+ `/stream/private`（记忆/票单/拦截，JWT）
- SSE 仅 `/chat` 助手对话使用：单用户并发 1，服务端限总连接（>阈值自动降级短轮询）；判决流刷新一律 SWR + 条件请求

### 4.2 i18n（同 v1.0，增补）

- `MatchTime` 相对时间（"40 分钟后"）由前端 30s 定时器驱动重渲染，避免跨分钟不更新
- 术语表治理：`glossary` 变更走 PR + 双人审批（域负责人 + 本地化负责人），CI 校验 UI 文案与 LLM 输出均合规

### 4.3 组件清单（同 v1.0：VerdictCard/GateChips/ConfidenceGauge/CostLabel/LegalSlot/OddsText/Money/MatchTime/SystemState/SuggestionChips/AgentCard）

性能预算：LCP<2.5s(4G)、流页 JS<180KB gzip、判决卡 SSR + CDN。

---

## 5. 后端模块划分

```
app/
  auth/ users/ ingest/ align/ model/ market/ verdict/ narrate/ notify/
  billing/ compliance/ i18n/ audit/
  events/        # 埋点（批量上报，分区表，WAV 计算源）
  moderation/    # 截图/聊天内容审核（审核API+敏感词），工单与申诉
  risk/          # 防薅（设备指纹/试用风控）、付费接口防爬、字段水印
```

---

## 6. 数据模型（v1.1 修正版）

### 6.1 核心修正（对齐审查 P0-4）

**match 全局唯一，行情与市场属性分离：**

```sql
CREATE TABLE matches (              -- 一场比赛一行，跨市场共享
  match_id TEXT PRIMARY KEY,        -- {league}_{date}_{home}_{away}
  league TEXT, kickoff_utc TIMESTAMPTZ, home_team TEXT, away_team TEXT,
  status TEXT DEFAULT 'scheduled'
);
CREATE TABLE market_availability (  -- 各市场对该场的挂盘属性
  match_id TEXT REFERENCES matches,
  market TEXT,                      -- 'cn_jc' / 'intl'
  official_no TEXT, single_allowed BOOL,
  sale_close_utc TIMESTAMPTZ, official_handicap SMALLINT,
  PRIMARY KEY (match_id, market)
);
-- odds_snapshots.source 承载具体行情方（sporttery/pinnacle/betfair/ah）
```

### 6.2 修正与新增表（差异列出）

```sql
-- odds_snapshots：按月 RANGE 分区；热 13 个月，冷归档 parquet
CREATE TABLE odds_snapshots ( ... ,
  PRIMARY KEY (match_id, source, market, line, captured_at)
) PARTITION BY RANGE (captured_at);

-- verdicts / audit_log：哈希链（不可篡改的技术支撑）
ALTER TABLE verdicts  ADD COLUMN prev_hash TEXT, root_of_day DATE;
ALTER TABLE audit_log ADD COLUMN prev_hash TEXT;
-- 每日 job：账本根哈希 commit 到公开仓库（第三方时间戳锚定）

-- bets 幂等与自主下注
CREATE TABLE bets (
  id BIGSERIAL PRIMARY KEY,
  idempotency_key UUID UNIQUE,          -- 客户端生成，防重复提交
  user_id UUID, verdict_id UUID NULL,   -- 可空
  source TEXT NOT NULL,                 -- verdict / manual
  placed_at TIMESTAMPTZ, stake NUMERIC(12,2), unit_stake NUMERIC(6,2),
  currency TEXT, legs JSONB, settled JSONB, clv NUMERIC(6,4)
);

-- users 增数据驻留
ALTER TABLE users ADD COLUMN data_region TEXT NOT NULL DEFAULT 'cn';

-- 埋点（WAV 北极星数据源）
CREATE TABLE events (
  id BIGSERIAL, user_id UUID NULL, anon_id TEXT,
  name TEXT, props JSONB, received_at TIMESTAMPTZ
) PARTITION BY RANGE (received_at);

-- 反馈（"不同意"理由、复盘反馈 → 产品迭代闭环）
CREATE TABLE feedback (id BIGSERIAL, user_id UUID, verdict_id UUID,
  kind TEXT, body TEXT, created_at TIMESTAMPTZ);

-- team_aliases 增来源可信度
ALTER TABLE team_aliases ADD COLUMN verified_by TEXT;  -- human / ai + 操作者

-- push_tokens 增订阅范围
ALTER TABLE push_tokens ADD COLUMN opt_in_scopes TEXT[];
```

### 6.3 精度规范

| 字段类 | 类型 |
|---|---|
| 概率/edge/CLV | NUMERIC(6,4) |
| 金额 | NUMERIC(12,2) |
| 单位注 | NUMERIC(6,2) |
| 赔率 | NUMERIC(5,2) |

### 6.4 增长估算与保留

| 表 | 5 联赛 | 30 联赛 | 策略 |
|---|---|---|---|
| odds_snapshots | 1000 万行/年 | 8000 万行/年 | 月分区 + 13 个月热 + parquet 归档 |
| events | — | — | >500 万/天迁 ClickHouse，PG 只留 30 天 |

---

## 7. API（v1，增补规范）

### 7.1 增补端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/v1/stream/public` | CDN 缓存（per-locale，TTL 5min） |
| GET | `/v1/stream/private` | JWT：记忆/票单/拦截状态 |
| POST | `/v1/events` | 埋点批量上报（≤50 条/批，异步落库） |
| POST | `/v1/moderation/report` | 举报；GET `/v1/support/tickets` 工单 |

### 7.2 全局规范

- **错误**：RFC 7807 `application/problem+json`，错误码表 `域.类别.序号`（如 `auth.ratelimit.01`）
- **幂等**：所有 POST 接受 `Idempotency-Key` 头；webhook 按 `event_id` 去重
- **版本**：URL 版本；sunset 提前 90 天响应头公告
- **限速**：免登录白名单（cost/ledger/stream.public/auth/gate）IP 级 60 r/min；chat 20/h/用户；验证码 5/h/IP
- **SLO**：API p99 <300ms；seal 成功率 >99.9%；结算延迟 <2h；公开账本 CDN 命中 >90%

---

## 8. 定时任务（增补三项）

| 任务 | 频率 | 说明 |
|---|---|---|
| `anchor_root_hash` | 每日 02:00 | 账本根哈希 commit 公开仓库 |
| `archive_cold_partitions` | 每周日 | 快照冷分区 → parquet |
| `push_staggered` | 19:00 起 30 分钟 | **按用户注册尾号分 6 桶错峰**；队列化，worker 池可扩 |

原有任务不变（ingest/align/model_run/seal/settle/weekly_retrain/shadow_eval/fx/glossary）。

**影子模式晋级线（v1.1 定义）**：连续 4 周 log loss 均值改善 ≥0.003、CLV 不劣化、且无单周恶化超 2σ → 自动晋级，否则退役并出报告。

---

## 9. LLM 层（成本分级）

| 用途 | 模型 | 缓存 | 成本控制 |
|---|---|---|---|
| 判决叙述 | Flash | key=(match_id, verdict_version, locale)，命中率>90% | 极低 |
| 助手对话 | Flash 优先，复杂问题升大模型 | 会话级 | 月度用量上限 + 分层路由 |
| 截图鉴别 | GLM-4V | 无 | 付费功能，天然限流 |
| 兜底 | 模板拼接 | — | LLM 全挂也能出判决 |

**数字白名单 + 术语校验 + 2 次重写 + 模板兜底**管线不变。

---

## 10. 全球化后端（增补）

- locale 协商：path > cookie > Accept-Language > market 默认
- market profile：`config/markets/{cn_jc,uk,us-xx,global}.yaml`（数据源/edge 论点/LegalSlot/年龄/支付/联赛集/禁用词/KYC 触发开关）
- **KYC 触发市场清单**：DE/SE（牌照要求）、US 部分州（21+ 核验）、其他默认自声明
- 双栈数据驻留（§2.2）；跨区仅公开内容同步
- 汇率每日缓存；`Money`/`OddsText` 纯函数转换，四格式互转全覆盖单测

---

## 11. 安全与合规实现（增补）

| 项 | 实现 |
|---|---|
| 认证 | JWT 15min + refresh 30d 旋转 + 复用检测 + Redis 撤销名单 |
| 幂等 | §7.2 规范全链路落地 |
| 内容审核 | 截图/聊天文本过审核 API + 敏感词库；命中即拦截并记 moderation |
| 风控 | 设备指纹（试用防薅）、免费接口限速、成本标签字段级水印溯源 |
| 密钥 | KMS 主密钥 + 数据密钥分层；90 天轮换；secrets 不入仓（CI 扫描） |
| 备份 | PG 每日全量 + WAL；**RTO 1h / RPO 5min**；每季演练恢复 |
| 篡改防护 | 哈希链 + 外部锚定（§6.2） |

---

## 12. AI 开发工程规范（新增整章）

> 前提：本项目 95% 代码由 AI 产出。工程规范的首要目标从"人读懂"变为"**可验证、可复现、上下文可携带**"。

### 12.1 单一事实源

- OpenAPI 3.1 是接口唯一事实源 → `openapi-typescript` / `fastapi-code-generator` 双端生成，**禁止手写客户端**
- DB schema 以迁移文件为准（alembic），模型注释即文档

### 12.2 可验证性门禁（CI 全部硬性）

| 门禁 | 标准 |
|---|---|
| 类型 | TS strict / pyright strict，零错误 |
| Lint | ruff + eslint 零警告 |
| 测试 | 核心模块（align/model/verdict/billing/compliance）覆盖率 ≥85% |
| 契约 | 契约测试快照，接口变更必须显式更新 |
| **禁用词扫描** | 仓库全量扫描 PRD 禁用词表（合规，CI 阻断） |
| 伪本地化 | en-XA 构建通过（文本膨胀不破版） |
| golden dataset | 对齐层（历史 500 场跨源对齐答案）与模型层（回测快照）入库，回归必跑 |

### 12.3 上下文工程

- 每模块 `AGENTS.md`：职责、公共接口、不变量、已知坑（AI 改码前必读）
- 架构决策记录 `docs/adr/`：决策/背景/后果三段式
- 文件 ≤400 行；公共接口显式 `__all__`/`export`；import-linter 禁循环依赖

### 12.4 人工把关清单（AI 不得自主合并，必须人审）

1. 支付回调与对账
2. 自排除/限额/年龄门逻辑
3. 封存哈希链与结算
4. 权限中间件与免登录白名单
5. 密钥、迁移、删除数据的操作

### 12.5 AI 开发流水线

```
spec(PRD条目) → 契约测试(golden) → AI实现 → AI自审(bot review)
→ CI门禁 → 人工把关清单命中则人审 → 合并 → 影子/灰度上线
```

- 每日自动跑 walk-forward 回测，模型相关 PR 必须附回测结果，无结果不合并
- 灰度：feature flag（S1 env 开关 → S3 Unleash）按 1%→10%→100%

---

## 13. 部署与运维（分级）

| 级 | 环境 | 组件 |
|---|---|---|
| S1 | dev/staging/prod 单机 | compose：web/api/worker/pg/redis/caddy + uptime-kuma |
| S2 | 双机+托管副本 | api×2、PgBouncer、PG 只读副本、Redis 哨兵、CDN、Prometheus |
| S3 | K8s 多可用区 | HPA、Kafka、ClickHouse、Unleash、Grafana 全量 |
| S4 | 双区域 | CN/Global 双栈，跨区只读公开内容，SRE 值班与故障演练季度化 |

关键 env 不变：`DATABASE_URL/REDIS_URL/JWT_SECRET/KMS_KEY/ODDS_API_KEY/LINEUP_API_KEY/LLM_API_KEY/WX_APPID/STRIPE_KEY/MARKET_DEFAULT/DATA_REGION`。

---

## 14. 里程碑映射（对齐 Roadmap v1.0）

| 版本 | 后端交付 | 前端交付 |
|---|---|---|
| v0.5 | ingest/align/verdict/seal/narrate(zh)/账本+锚定 | 判决流+成本标签+避雷+账本（无账户） |
| v1.0 | auth/users/events/notify(企微)/moderation 基础 | 登录/我的/票单/预算/归因/快捷方式引导 |
| v1.5 | billing(微信)/memories/en 内容/i18n 基建 | 订阅/时间门控/助手×2/en 全站 |
| v2.0 | market profile 插拔/Stripe/compliance/vision/双栈 | 合规中心/截图鉴别/日历/周报/es+pt-BR |
| v2.5 | K8s/Kafka/ClickHouse/AB 平台/B 端 beta | 灰度发布体系 |
| v3.0 | 多区域/成本优化/开放 API 分层 | App（原生推送）/Agent 生态 |

---

*TechSpec v1.1 完 · 变更摘要：P0×7 修复（触达归 PRD/其余本文）+ P1×15 + P2×8，详见 Review v1.0 §六映射*
