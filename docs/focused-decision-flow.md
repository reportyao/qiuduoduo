# 球多多 · 聚焦决策流 / 数据脉搏 / 情报层

> **状态：部分实现。** 前端已实现 `focusStore`、头像/首页选择器选中后回首页聚焦、聚焦卡（复用现有判决）、详情页“让助理看这场”；**后端 `/stats/pulse`、`/matches/{id}/focus`、`/interactions` 已实现**；`intel_items`/`match_coverage`/`pulse_daily` 仍未建表；前端已接 `/stats/pulse`、`/matches/{id}/focus` 与在售 coverage；`GET /matches/on-sale` 已带 `coverage`。当前 OpenAPI 为 **128 路径 / 143 方法**、Alembic head `20261105_12`。
>
> 目标：把首页从“12 张判决卡 + 常驻输入框”改成 **数据脉搏 + 一场聚焦 + 客观情报 + 动作按钮**；用户点头像选比赛，选中后回首页围绕这一场展开，而不是跳详情页。
>
> 当前前端已完成“选中 → 回首页聚焦”的导航和聚焦卡壳；后端 focus/pulse/interactions 已接；数据脉搏首屏、客观情报卡与 intel 固化表仍是下一阶段。
>
> 2026-11-05 口径修订：产品允许经审核的方向判断/参考组合/串关参谋，见 [recommendation-product.md](./recommendation-product.md)。
>
> 关联：[PRD-v5.1](../PRD-v5.1.md) · [TechSpec-v2.1](../TechSpec-v2.1.md) §8 · [Intelligence-Layer-v1.0](../Intelligence-Layer-v1.0.md) · [Feature-API-Mapping-v1.0](../Feature-API-Mapping-v1.0.md) · [数据库架构](./database-architecture.md)

## 1. 交互状态机

```text
idle（未选场）
  → picker（头像/“选一场”）
  → focused（已选场）
      → why（展开闸门/死因）
      → detail（看完整账）
      → bet（记一注）
      → watch（加入关注）
      → switch（换一场）
      → rest（今天不看了）
  → locked（已停售）
  → settled（已结算，转复盘）
```

规则：

- 一次只保留一个聚焦场；其他场次进“今日全部”。
- 头像/选择器选中比赛后：**设置 focus + 回首页**，不直接跳 `/verdict/[id]` 或 `/match/[id]`。
- “看完整账”才跳详情；返回时保留聚焦和滚动位置。
- 05:00 竞彩日切换：清空 focus，刷新数据脉搏。
- screening → promoted/killed：聚焦卡原地更新，提示“结论已更新”。
- 停售/开赛/结算：状态切换，动作随 `capabilities` 变化。
- 未登录、未成年、自排除、休息中：动作按拦截态降级，不能只靠前端隐藏。

## 2. API 契约

所有新接口为 additive；现有 `/stream`、`/verdicts/{id}`、`/matches/{id}/why-not` 保持兼容。移动端 `packages/api-client` 从 OpenAPI 快照重新生成，禁止手写类型。

> 字段命名：实现遵循现有后端约定使用 **snake_case**（如 `trade_date`、`data_points`、`requires_auth`）；下面示例为便于阅读的语义字段，最终以 `packages/api-client/openapi.json` 为准。

### 2.1 `GET /stats/pulse?date=YYYY-MM-DD`

首页“数据脉搏”。公开聚合数据，不含用户隐私。

```json
{
  "trade_date": "2026-11-04",
  "as_of": "2026-11-04T19:02:00+08:00",
  "stale_seconds": 128,
  "counts": {
    "matches": 12,
    "sp_snapshots": 144,
    "intl_odds": 36,
    "model_runs": 72,
    "verdicts": 12,
    "revisions": 3,
    "intel_items": 48,
    "sealed_links": 12
  },
  "data_points": 660,
  "display": { "data_points": 3300, "factor": 5, "unit": "数据点" },
  "all_time": { "data_points": 128400, "matches": 2400, "sealed": 2400 },
  "stages": [
    { "key": "ingest", "label": "接入", "count": 12, "status": "ok" },
    { "key": "clean", "label": "清洗", "count": 12, "status": "ok" },
    { "key": "align", "label": "对齐", "count": 11, "status": "partial" },
    { "key": "model", "label": "模型", "count": 4, "status": "partial" },
    { "key": "gate", "label": "三闸", "count": 12, "status": "ok" },
    { "key": "seal", "label": "封存", "count": 12, "status": "ok" }
  ],
  "sources": [
    { "key": "sporttery", "label": "竞彩官方", "status": "ok", "last_sync": "2026-11-04T19:00:00+08:00", "coverage": 1.0 },
    { "key": "intl", "label": "国际盘", "status": "partial", "last_sync": "2026-11-04T18:55:00+08:00", "coverage": 0.42 },
    { "key": "xg", "label": "xG 模型", "status": "partial", "last_sync": "2025-05-17T00:00:00+08:00", "coverage": 0.25 },
    { "key": "lineups", "label": "阵容/伤停", "status": "missing", "last_sync": null, "coverage": 0.0 }
  ],
  "outcomes": { "promoted": 0, "screening": 12, "killed": 0 },
  "excluded": 0,
  "definition": "data_points = sp_snapshots*3 + intl_odds*3 + model_runs + intel_items；display.data_points = data_points × 展示系数"
}
```

约定：

- `counts`/`data_points` 是真实原始口径；`display.data_points` 是营销展示口径，只允许乘在可解释的“数据点/字段”上，不允许乘场次、封存数、用户数、准确率。
- `display.factor` 由 `JQ_PULSE_DISPLAY_FACTOR` 配置，默认 3，硬上限 5；后台可改但必须审计。展开口径可查，不隐藏 raw。
- 只返回真实计数，不允许前端伪造或按固定值跳动。
- `stale_seconds` 取最旧关键源（SP/国际盘）的延迟；超过 35 分钟 `status=stale`。
- `status`：`ok | partial | stale | missing | error`。
- 结果缓存 15–30 秒；公开接口做限流。
- 无数据时返回真实 0 和 `missing`，不要造数。

阶段口径（固定）：

| stage | 计数 |
|---|---|
| `ingest` | 当日窗口内 `sp_matches` 数 |
| `clean` | kickoff/队名/联赛非空且格式合法的场次 |
| `align` | 队名已对齐、无未解析别名的场次 |
| `model` | 有模型预测的场次 |
| `gate` | 有 `verdicts` 三闸的场次 |
| `seal` | `sealed_at` 非空的判决数 |
| `excluded` | 当日 killed 场次（不是数据清洗失败） |

`all_time` 优先读 `pulse_daily` 聚合，不在每次请求里全表 COUNT；`pulse_daily` 由每日任务重算，后台可回填。

### 2.2 `GET /matches/{match_id}/focus?date=YYYY-MM-DD&persona=zhuanjia`

选中一场后，首页只请求这一个接口，避免 verdict/intel/coverage 三次请求。

```json
{
  "match": {
    "match_id": "m123",
    "match_no": "周三001",
    "league": "英超",
    "home": "曼城",
    "away": "曼联",
    "kickoff": "2026-11-04 20:30:00",
    "sale_close": "2026-11-04 20:30:00",
    "single": true
  },
  "verdict": {
    "id": "v2026-11-04-周三001",
    "status": "screening",
    "pick": null,
    "rake": 0.121,
    "rake_threshold": 0.13,
    "probs": { "home": 0.56, "draw": 0.23, "away": 0.21 },
    "gates": { "price": "pass", "market": "pending_data", "model": "pending_data" },
    "payload_hash": "…",
    "sealed": true
  },
  "state": "screening",
  "trade_date": "2026-11-04",
  "request_id": "f34b…",
  "as_of": "2026-11-04T19:02:00+08:00",
  "data_cutoff": "2026-11-04T18:50:00+08:00",
  "seal": { "hash": "…", "sealed_at": "2026-11-04T19:01:00+08:00", "revision": 2 },
  "coverage": {
    "score": 55,
    "level": "partial",
    "deep_eligible": false,
    "missing": ["model", "lineups", "standings"],
    "sources": [
      { "key": "price", "status": "ok", "last_sync": "…" },
      { "key": "market", "status": "partial", "last_sync": "…" },
      { "key": "model", "status": "missing", "last_sync": null }
    ]
  },
  "intel": {
    "facts": [
      {
        "id": "f1",
        "kind": "form",
        "label": "近 5 场",
        "value": "3 胜 1 平 1 负",
        "detail": "主队近 5 场正式比赛战绩；样本小，只作参考",
        "source": "football-data",
        "captured_at": "2026-11-04T17:00:00+08:00",
        "status": "confirmed",
        "confidence": 0.8,
        "evidence_ref": "ev-…"
      }
    ],
    "unknowns": ["首发/伤停未确认", "积分榜战意未接入"]
  },
  "interpretation": {
    "text": "价闸过了，但市场已经把体能和德比热度定价；模型没覆盖，当前没有额外 edge。等首发。",
    "persona": "zhuanjia",
    "model": "deepseek-chat",
    "prompt_ver": "focus-v1",
    "generated_at": "2026-11-04T18:00:00+08:00",
    "facts_used": ["f1", "f2"],
    "stale": false
  },
  "capabilities": {
    "can_bet": false,
    "can_watch": true,
    "can_why_not": true,
    "can_view_detail": true,
    "can_share": false,
    "can_rest": true,
    "can_remind_lineup": true,
    "can_refresh": true
  },
  "actions": [
    {
      "id": "why_not",
      "enabled": true,
      "primary": true,
      "requires_auth": false,
      "reason": null
    },
    {
      "id": "detail",
      "enabled": true,
      "primary": false,
      "requires_auth": false,
      "reason": null
    },
    {
      "id": "watch",
      "enabled": true,
      "primary": false,
      "requires_auth": true,
      "reason": null
    },
    {
      "id": "switch",
      "enabled": true,
      "primary": false,
      "requires_auth": false,
      "reason": null
    }
  ]
}
```

约定：

- `actions` 只给稳定 ID；文案、图标、人设语气由移动端 i18n/Persona 映射。
- `capabilities` 是服务端业务规则：sealed、settled、休息/自排除、未登录、未成年等都在后端判断，前端不能自行放开。
- `verdict` 可为 `null`（仅在售、还没判决）；此时 `state=on_sale`，`can_why_not=false`。
- `interpretation` 可为 `null`；缺失时客户端用模板解释，不阻塞页面。
- 404：比赛不存在；`stale=true`：仍返回上次结果，客户端标“未刷新”。
- 只对 `state` 匹配的 action 返回；服务端不返回用户隐私。
- 详情页仍走 `/verdicts/{id}`、`/matches/{id}/why-not`；focus 不替代它们。
- `persona` 只影响解读外层文案，不影响事实/数字；深读事实按比赛共享，人设壳单独缓存。
- `focus` 是可选登录接口：公开部分可缓存；含 `capabilities`/个人状态时响应 `Cache-Control: private, no-store`，不按匿名缓存。
- `actions[].requires_auth=true` 时，未登录点击应引导登录，不应只灰掉；`reason` 给前端展示禁用原因。
- 客户端用 `session_id + request_seq` 防止快速切换比赛时旧响应覆盖新焦点；服务端可返回 `request_id` 回显。
- 刷新节奏：前台每 60s + 回到前台时刷新；不做假实时 tick。结论变化用 `verdict.status` 与 `data_cutoff` 判断。
- 05:00 竞彩日界：若聚焦场次仍在赛前/未结算，保留焦点直到该场结束；否则清空回 idle。不要机械清空正在进行的凌晨场。
- `focus` 响应建议带 `ETag`/`as_of`，客户端用 `If-None-Match` 减少刷新流量。

### 2.3 扩展 `GET /matches/on-sale`

保持向后兼容，新增可选字段：

```json
{
  "match_id": "m123",
  "sale_close": "2026-11-04 20:30:00",
  "coverage": { "score": 68, "missing": ["lineups"] },
  "intel_status": "partial",
  "has_interpretation": false
}
```

用途：比赛选择器显示覆盖徽章，默认排序“promoted → 情报完整 → 其他”，不再只按开赛时间。

### 2.4 `POST /interactions`

匿名/登录都可上报；用于聚焦漏斗、动作点击、WAV 分析，不参与结算。请求体：

```json
{
  "event": "focus_select | action_click | action_result | free_text_open | free_text_send | pulse_open | intel_expand | source_open",
  "event_id": "uuid",
  "schema_ver": 1,
  "session_id": "uuid",
  "match_id": "m123",
  "verdict_id": "v…",
  "action": "why_not",
  "metadata": { "source": "home_focus", "persona": "zhuanjia" }
}
```

- `user_id` 从登录态取；匿名只存 `session_id`/设备哈希，不存原始设备号。
- 事件白名单 + 长度限制；按 IP 120 次/分钟限流；返回 200 JSON。
- `event_id` 幂等去重；`schema_ver` 便于后续改字段；不接受自由文本/PII。
- 新事件返回 `200 {"ok": true, "duplicate": false}`；同 `event_id` 重放返回 `200 {"ok": true, "duplicate": true}`；超限 429。
- 事件只做漏斗，不参与结算/记忆/推荐；与 `user_events` 的用途分开，避免重复计数。

### 2.5 复用现有接口

| 动作 | 接口 |
|---|---|
| 看完整账 | `GET /verdicts/{id}`、`GET /verdicts/{id}/evidence`、`/seal` |
| 为什么不推 | `GET /matches/{id}/why-not` |
| 记一注 | `POST /bets`、`DELETE /bets/{id}` |
| 关注 | `GET/POST /me/watch`、`DELETE /me/watch/{id}` |
| 今天不看了 | `POST /me/rest` |
| 分享 | `POST /share/verdict/{id}` |
| 聊天兜底 | `POST /chat`（固定意图优先，LLM 仅 fallback） |

## 3. 数据模型

### 3.1 现有可复用

| 表 | 用途 |
|---|---|
| `sp_matches` / `sp_snapshots` | 赛程、官方 SP、赔率变化 |
| `intl_odds` | 国际盘、离散度 |
| `verdicts` / `verdict_revisions` | 判决、闸门、封存、修订 |
| `model_runs` | 每场每闸审计日志 |
| `match_results` | 赛果、近期战绩 |
| `team_aliases` | 队名对齐 |
| `user_events` | 登录用户行为（现有） |

`verdicts.payload.evidence` 继续作为封存证据；`focus.intel` 是面向 UI 的规范化视图，不替代封存 payload。

### 3.2 新增表（部分实现）

```text
# ✅ 已实现（迁移 20261104_05）
interaction_events
  id, event_id, schema_ver, actor_type, actor_id, session_id,
  event, match_id, verdict_id, action, metadata_json, created_at
  unique(event_id)
  index(event, created_at), index(match_id, created_at)

# ⏳ 目标态
intel_items
  id, match_id, trade_date, kind, label, value_json, detail,
  source, source_ref, captured_at, status, confidence,
  coverage, evidence_ref, created_at
  index(match_id, trade_date, kind), index(source, captured_at)

match_coverage
  match_id, trade_date PK, score, level, missing_json,
  sources_json, computed_at

analysis_jobs
  id, match_id, trade_date, input_hash, status, attempts,
  priority, not_before, locked_at, started_at, finished_at,
  last_error, created_at
  unique(input_hash)
  index(status, priority, not_before)

ai_analyses
  id, match_id, trade_date, input_hash, prompt_ver, provider,
  model, output_json, status, tokens_in, tokens_out, cost_cny,
  latency_ms, created_at
  unique(input_hash, prompt_ver, provider, model)
  -- output_json 是“事实分析”，人设无关；不存三个人设的三份深读

narrative_pool
  id, verdict_id, persona, prompt_ver, text,
  status (draft/published/retired), source (fast/template/editor),
  facts_used_json, expires_at, created_at
  unique(verdict_id, persona, prompt_ver, source)
  -- 只存外层文案；数字由渲染器注入

pulse_daily
  trade_date PK, raw_counts_json, raw_data_points,
  display_factor, display_data_points, computed_at
  -- 累计/历史脉搏聚合，避免每次 COUNT 全表

# ✅ 已实现（迁移 20261105_11_admin_rbac_audit；不再属于目标态）
admin_audit
  id, actor, role, action, target_type, target_id,
  before_json, after_json, ip, created_at
  index(created_at), index(actor), index(action)
```

说明：

- `intel_items.status`：`confirmed | inferred | unknown | stale`；`unknown` 也要展示“缺什么”，不能省略；`stale` 表示有值但超过新鲜度阈值。
- `match_coverage` 可先由 service 实时计算；有性能压力再物化。
- `interaction_events` 与 `user_events` 分开：后者要求 `user_id` 非空，前者支持匿名/会话级漏斗。
- `analysis_jobs` / `ai_analyses` 只在深读解读阶段启用；不阻塞 focus 接口。
- `ai_analyses` 只存一份事实分析；`narrative_pool` 存每个人设的外层文案，避免 DeepSeek ×3。
- `pulse_daily` 用于“累计/历史”脉搏；当日实时计数仍可实时算，后台可重算。
- `admin_audit` 记录展示系数、路由、预算、情报发布等后台变更。
- 迁移需可 up/down；Postgres 生产只走 Alembic。
- 已落迁移：`20261104_05_interaction_events.py`（head 从 `20261104_04` 前进到 `20261104_05`），随后 `20261104_06_api_football.py` 把 head 推进到 `20261104_06`；`20261104_07_llm_gateway.py` 再推进到 `20261104_07`；`20261104_08_persona_llm.py` 推进到 `20261104_08`；`20261104_09_persona_profiles.py` 推进到 `20261104_09`；`20261105_10_recommendation_pipeline.py` 推进到 `20261105_10`；`20261105_11_admin_rbac_audit.py`（admin_users/admin_audit）推进到 `20261105_11`；`20261105_12_user_compliance.py`（users 合规列）推进到 `20261105_12`（当前 head）。intel 表仍待后续迁移。

### 3.3 覆盖率与数据点口径

覆盖率权重建议（可在配置中调）：

| 源 | 权重 | 说明 |
|---|---:|---|
| 官方 SP / 价闸 | 25 | 必须有 |
| 国际盘 / 市闸 | 20 | 缺则市闸 pending |
| 模型 / xG | 25 | 缺则模闸 pending |
| 阵容/伤停 | 15 | API-Football 已接；未同步时按 missing 计 |
| 赛程/休息 | 10 | 可从 matches 派生 |
| 积分榜/战意 | 5 | API-Football 积分榜已接；战意信号未建 |

`score = Σ(权重 × 可用且新鲜)`，0–100。  
`level`：`full ≥ 70`、`partial 50–69`、`insufficient < 50`。

新鲜度阈值（建议，配置可调）：

| 源 | 新鲜阈值 | 过期处理 |
|---|---:|---|
| 官方 SP | 15 分钟 | `stale`，价闸需重算 |
| 国际盘 | 15 分钟 | `partial/stale`，市闸 pending |
| xG/球队状态 | 24 小时 | 只作背景，不支撑深读 |
| 阵容/伤停 | 6 小时/停售前 | `unknown`，深读不开放 |
| 赛程/休息 | 1 小时 | 可派生 |
| 积分榜 | 24 小时 | 可缺省 |

`deep_eligible` 单独计算，不等同于 `level=full`：

```text
deep_eligible =
  price 有值 && market 有值 && model 有值
  && data_cutoff 新鲜
  && 距停售 >= 30 分钟
  && (阵容已确认 || 距开赛 >= 12 小时且明确标注“首发未知”)
  && coverage.score >= 70
```

不满足就返回 `deep_eligible=false`，前端只展示事实/模板解读，不排队 DeepSeek。  
`level` 用于 UI 数据完整度，`deep_eligible` 用于是否允许 deep profile，两者不能混用。

`data_points` 口径固定写入 `/stats/pulse.definition`，避免每个页面一套数字。

展示系数：

```text
raw_data_points = sp_snapshots*3 + intl_odds*3 + model_runs + intel_items
display_data_points = round(raw_data_points * JQ_PULSE_DISPLAY_FACTOR)
```

- 默认 `3`，硬上限 `5`；营销文案用“数据点（按字段计）”，并保留 tooltip/后台 raw。
- 累计口径可展示 `all_time` 真实累计，不需要把单日系数调得离谱。
- 绝不能把“12 场”乘成“120 场”，也不能把封存数/准确率乘系数。

### 3.4 数据补齐优先级

当前真实状态（2026-11-04）：

- xG 仅五大联赛 2019-08 至 2025-05，共 10,708 场、137 队；当前竞彩中的 K/J 联赛等不在覆盖内，模型闸大量 pending。
- 首发/伤停/积分榜已接 API-Football（免费档 90 请求/日，配置 `JQ_API_FOOTBALL_KEY` 后启用；见 [api-football.md](./api-football.md)）。
- 未链接的 fixture 需要 `/admin` 运维页 人工确认；没有英文队名别名时自动链接率会低。
- 无裁判/天气、实时 feed；国际盘依赖可选 the-odds-api key。

优先级：

1. 当前赛季、竞彩覆盖联赛的 xG/攻防数据；
2. 首发/伤停/停赛（API-Football 已接，继续补别名/覆盖）；
3. 积分榜/战意、赛程密度；
4. 实时比分/赛果；
5. 国际盘第二源与盘口变动历史。

没有 1–3 时，`coverage.level` 最高只能到 `partial`，深读解读不开放；前端明确展示“情报不足”，不调用 DeepSeek 生成泛泛分析。

## 4. 后端模块

目标 feature slice：

```text
app/features/intel/
  router.py        /stats/pulse, /matches/{id}/focus
  service.py       聚合 focus、计算 coverage、拼装 intel
  repository.py    查询现有表 + 新表
  schemas.py       Pydantic 响应
  models.py        intel_items / match_coverage（逐步迁移）
  jobs.py          刷新 intel/coverage
  tests/
```

原则：

- `router.py` 不写业务；`service.py` 不拼 SQL；`repository.py` 不做业务规则。
- `focus` 复用 catalog/verdict service，不复制闸门逻辑。
- `/stats/pulse` 只读、聚合、缓存；不暴露用户/注单。
- `capabilities` 由 service 统一计算；前端不得自行推导。
- 先做只读 focus + pulse，再做 intel 持久化，再做 AI 解读。

## 5. 管理后台

现有 `/admin` 已是 RBAC 多角色运营台（viewer/operator/admin + CSRF + 会话撤销 + `admin_audit` 审计）；只读/运维/推荐主链/模型/人设/账号/审计页已上线，编辑台变体精选仍是后续。

### `/admin` 数据源页

- 数据脉搏同口径计数、源新鲜度、覆盖率。
- 按联赛/球队看：模型覆盖、国际盘覆盖、阵容缺失、别名未对齐。
- 告警：源延迟 >35/90 分钟、覆盖率骤降、未对齐队名、无快照。
- 操作：重跑 coverage/intel 刷新（幂等）、导入 xG/阵容、查看失败原因。
- 展示系数：查看/修改 `JQ_PULSE_DISPLAY_FACTOR`，同屏显示 raw 与 display，修改写审计。

### `/admin` 运维页

- 聚焦漏斗：选择场次 → action_click → detail → bet → watch → rest。
- 按比赛/人设/来源拆：动作 CTR、WAV、自由提问展开率。
- 只看聚合，不展示用户下注明细。
- 与 `/admin` 模型用量页 联动：深读解读的打开率、成本。
- 漏斗口径（必须固定）：
  - `focus_select`：按 `session_id + match_id + 日期` 去重；
  - `action_click`：按 `event_id` 去重；
  - `bet_recorded`：以 `bets` 成功写入为准，不信前端事件；
  - `WAV`：结算确认后的采纳数 / 周，不以点击代替；
  - 自由提问：`free_text_open` 与 `free_text_send` 分开，后者才计入 LLM 成本。

### `/admin` 运维页

- 每场情报列表：coverage、facts、unknowns、来源、时间。
- 审核 `confirmed/inferred/unknown/stale`；人工补充必须带来源与操作者。
- 发布状态：draft / published / stale；数据更新后自动标记 stale。
- 不允许把“推测”改成“已确认”而不留审计。

### `/admin` 模型用量页

沿用多模型网关方案，但先做最小集：

- fast/deep provider 状态、测试、任务路由、预算、熔断。
- 只允许内置适配器，不允许任意 base_url；Key 只走 env/KMS。
- 深读解读任务队列：eligible 场次、生成、预览、发布、重跑。
- 用量：调用数/tokens/成本/缓存命中/失败率。

### 权限与审计

- 已落地 RBAC（viewer/operator/admin）+ CSRF + 会话撤销；任何路由/预算/情报/账号修改写 `admin_audit`（操作者、角色、时间、旧值、新值、IP）。
- POST 已加 CSRF；测试按钮已审计；错误信息不回显 Key。
- 新路由上线前按 AGENTS.md 重新采纳 W8 冻结基线。

## 6. AI 解读与成本

> 多模型 Gateway、fast/deep 路由、预算、缓存、后台配置的完整方案见 [llm-gateway.md](./llm-gateway.md)。

- 事实层不进 LLM；`intel.facts` 全部由确定性代码生成。
- 解读层只对 `coverage.level=full` 的场次生成；数据不足直接返回模板“数据不够，先看三闸/成本”。
- 深度分析按 `match_id + data_cutoff + prompt_ver + model` 缓存，所有用户共享；不按用户生成。
- 一份深度分析 + 三个人设外层改写；不要让 DeepSeek 跑三遍。
- 解读不得改数字、不得给预测/推荐；输出过数字白名单、禁用词、概率语法校验。
- 动作按钮永远不调用 LLM；自由提问默认收起，只做 fallback。
- 预算原子预占、超时/失败回模板；`ai_status=unavailable` 不阻塞 focus。

### 6.1 用户层级与额度

LLM 成本必须跟用户层级走，不能匿名无限问：

| 用户 | 固定意图 | 开放问答 | 深读解读 |
|---|---|---|---|
| 匿名 | 模板/卡片，0 LLM | 固定引导，0 LLM | 不提供 |
| 注册免费 | 0 LLM | fast，严格日配额（如 10 次/日） | 不提供或每日 1 次体验 |
| 订阅会员 | 0 LLM | fast，较高配额 | deep，按 eligible 场次 + 次数 |
| 后台/批量 | — | fast 文案变体 | deep 预生成/审核 |

- 匿名/免费额度在 `/chat` 入口先检查，不等到 LLM 调用后。
- 额度用 `llm_budgets` + 用户/设备维度计数；不能只靠前端。
- 订阅未上线前，deep 只做内部预生成/影子，不向免费用户开放。
- `focus` 的 `capabilities` 要返回当前用户是否能触发深读/自由提问的原因。

## 7. 兼容、迁移与发布

### 前端

1. ✅ `focusStore`（`FocusTarget`）已加到 `apps/mobile/src/features/home/focusStore.ts`。
2. ✅ `GlobalMatchPicker` 和首页 `MatchPickerSheet` 选中后 `setFocus → close → 回首页`，不再直接 push 详情；详情页增加“让助理看这场”。
3. ◐ 首页已有聚焦区（复用 `VerdictMessage`/`FocusPending`）+ `FocusPanel`（覆盖率/事实/未知项/拦截原因）；但无聚焦时的 `idle` 数据脉搏独立首屏尚未做；`empty/rest/error` 仍是旧逻辑。
4. ◐ 真实数据脉搏指标（`Metrics`/`DataStatusSheet`）与聚焦事实/未知项展示已接；`ActionStack`、输入框默认收起尚未做。
5. ✅ 动作点击写 `POST /interactions` 已接（`focus_select`/`action_click`/`free_text_send`/`pulse_open`，见 `src/features/telemetry/interactions.ts`）。

### 后端

1. ✅ `/stats/pulse`（现有表聚合）与 `/matches/{id}/focus`（复用 verdict/evidence；intel 动态生成）。
2. ✅ `interaction_events` 表 + `POST /interactions`（幂等/白名单/限流）。
3. ✅ `/admin` 数据源页、运维页、模型用量页、推荐主链页等后台页面（RBAC+CSRF+审计）。
4. ✅ API-Football fixtures/lineups/injuries/standings + 免费额度 + 人工链接。
5. ⏳ `intel_items` / `match_coverage` / `pulse_daily` 持久化。
6. ⏳ `analysis_jobs` / `ai_analyses` 与 `/admin` 模型用量页。
6. 每步保持旧 `/stream` / 详情接口不变。

### 数据库

- 新表用 Alembic 迁移；生产只 `alembic upgrade head`，禁止 `create_all`。
- 迁移必须可 down；新增索引按热路径：`match_id+trade_date`、`source+captured_at`、`event+created_at`。
- Postgres 上大表加索引注意锁；按现有 `lock_timeout` 约定执行。
- 回填脚本幂等：按比赛/日期重算 coverage/intel，可重复执行。

### 发布顺序

1. 只读 pulse + focus API + 前端聚焦（feature flag）。
2. 动作栈 + 收起输入框 + 互动事件。
3. 覆盖率 + 选择器徽章 + 数据脉搏扩展。
4. intel 持久化 + 后台数据/情报页。
5. AI 解读异步 + `/admin` 模型用量页 + 预算。
6. 影子/灰度后全量。

## 8. 验收标准

- 选中比赛后回首页聚焦，不跳详情；跨 Tab 保留 focus；05:00 清空。
- focus 首屏包含：结论、三闸、数据完整度、3 条事实、动作。
- `capabilities` 正确拦截未登录/自排除/休息/已结算。
- 数据脉搏所有数字可由 SQL 复现；无数据时显示 0/missing，不造假。
- 情报每条有来源、时间、confirmed/inferred/unknown；缺失项明确展示。
- 动作按钮均有确定性结果，点击有埋点；不出现“按钮只是发一句话给 LLM”。
- 自由提问默认收起；展开不自动聚焦；有配额/限流。
- `typecheck` / `lint` / 后端测试 / 前端测试 / OpenAPI 快照 / Alembic up-down 全绿。
- 308dp 窄屏、长队名、减少动态效果、断网/超时均可接受。
- 新增路由后 W8 freeze 基线已重新采纳。

### 8.1 测试矩阵

| 用例 | 期望 |
|---|---|
| 快速选 A→B | A 的迟到响应不能覆盖 B（request_id/session 校验） |
| 选中比赛 | 回首页聚焦，不跳详情 |
| 未登录点关注/深读 | `requires_auth=true` 引导登录，不静默失败 |
| 自排除/休息中 | `can_bet=false` 且有原因 |
| 05:00 + 凌晨场未结束 | 保留焦点，不强制清空 |
| 停售/结算 | 状态和动作切换，旧“记一注”不可点 |
| 数据 stale | 绿色变黄/红，不让旧数据伪装实时 |
| 脉搏计数 | 与 SQL 对拍；raw/display/factor 一致 |
| 展示系数 | 不乘场次/封存/准确率；改系数写审计 |
| 情报缺失 | 显示 unknown，不生成“完整分析” |
| 动作重复点击 | 幂等/loading，不重复写注单/关注 |
| 自由提问收起 | 默认不弹键盘、不自动聚焦 |
| 308dp/长队名 | 按钮不挤压、文字不溢出 |
| 后台改系数/路由 | 写 `admin_audit`，可回滚 |

## 9. 未决问题

1. 是否解除 W8 功能冻结，或先用现有路由做只读聚焦。
2. 阵容/伤停数据源选型（API-Football 等）与授权成本。
3. 当前赛季 xG 覆盖哪些联赛；未覆盖联赛是否只做价/市。
4. `coverage` 阈值与深读资格由谁配置、是否按联赛不同。
5. 匿名互动事件保留周期与隐私口径。
6. 聚焦状态是否跨设备同步（当前建议只本地保存）。
7. 自由提问的配额与订阅权益如何绑定。
8. “今日在售”/比赛列表是否也统一走 `selectFocus`，还是只头像/首页选择器聚焦。
9. 分享深链 `/match/{id}` 打开时是否自动设置 focus，还是只开详情。
10. 展示系数上限 5 是否足够营销口径；若不够，优先扩 `all_time` 真实累计而不是继续调系数。
11. 数据源（xG/阵容/积分榜）的授权成本与可商用范围。
12. 免费模型/DeepSeek 的数据条款、数据地域与是否训练；个人数据是否允许出境。
