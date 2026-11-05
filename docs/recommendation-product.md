# 赛前判断与串关参谋（产品方案 v2）

> 状态：**主链已实现，商业化/完整后台待做。** 2026-11-05 完成：
> `decision_snapshots` / `recommendation_plans` / `review_runs` / `recommendation_events` 四表，
> build → L1–L5 review → publish → expire/withdraw 生命周期；`GET /recommendations/today` 只读 published；
> `/admin` 推荐主链页可运行主链、复核、发布、撤回；Today Hero 已优先消费 published snapshot，
> 旧后端 404 才回退 stream；persona 模型请求已统一走 Gateway 传输层。
>
> 待开发：`recommendation_copies` 三套人设文案、付费墙/权益、完整发布 UI（组合页已优先 published，preview 仅回退）、复盘/CLV 消费层。

## 1. 定位

> 每天 2 分钟，给你一个看得懂、跟得上的赛前判断和组合思路。

不是“算清成本”的工具，也不是“保证命中”的卖料号，而是：

- 今天主看哪场
- 方向是什么
- 把握度多少
- 成立条件 / 不成立条件
- 如果要串，怎么配
- 什么时候该撤
- 赛后怎么复盘

### 1.1 红线修订

| 旧口径 | 新口径 |
|---|---|
| 不预测赢家 | 提供**经 AI 复核**的方向判断/概率区间；不承诺结果 |
| 不推荐买 | 付费用户可看**参考方向、参考组合、参考预算**；免费给一条完整试读 |
| 不输出串关方案 | 输出**组合思路**：2–3 腿、成本、相关性、失效条件 |
| 推送不出现赔率/投注/结果 | 推送只写“今日判断已更新/有 N 条 AI 复核观点” |
| 不实现“稳赚/回本/推荐买”文案 | “稳赚/必中/包赢”保留为**文案风控词**，不是功能禁区 |
| 不绕过自排除/连败保护/年龄确认 | 保留为**支付/上架合规能力**，不是内容禁区 |

原则：

> **可以预测、可以推荐、可以给组合；但必须有依据、有 AI 复核、有条件、有边界。**

“委婉”用于公开文案/推送/商店素材；付费详情必须明确方向、条件、成本和失效条件，不能含糊到用户不知道在说什么。

## 2. 用户旅程

```text
19:02 推送：今日判断已更新（3 条观点，2 个组合）
  ↓
首页：今日主看（免费完整 1 条）
  ↓
“为什么”展开：三闸 + 情报 + 条件 + 不成立条件
  ↓
“参考组合”入口：看到组合腿、成本、把握度
  ↓
付费墙：解锁全部观点 + 组合 + 临场更新
  ↓
复制方案 / 设提醒
  ↓
赛后：昨日方案复盘 + CLV
  ↓
续费
```

## 3. 免费 vs 付费

| 能力 | 免费 | 付费 |
|---|---|---|
| 今日主看 1 条 | 完整方向 + 2 条理由 + 1 条风险 | ✅ |
| 今日其他观点 | 仅显示“还有 N 条已复核” | 全部 |
| 三闸 / 成本 | ✅ | ✅ |
| 参考组合 | 显示“有 N 个组合”，腿/成本模糊 | 完整腿、成本、返还、条件 |
| 参考预算 | ❌ | ✅ |
| 临场更新 / 失效提醒 | ❌ | ✅ |
| 赛后复盘 / CLV | 基础 | 完整 |
| 历史观点 | 最近 3 天 | 全部 |

免费必须给一次“完整、有逻辑”的判断，先建立信任，再锁“更多、组合、临场更新”。

## 4. 首页信息架构

```text
首页
├─ 今日判断（最重要）
│   ├─ 助理倾向：主队方向 / 客队不败 / 观望
│   ├─ 把握度：强 / 中 / 弱
│   ├─ AI 复核 · 18:30 · v3
│   └─ 免费 1 条，其余锁定
├─ 聚焦卡
│   ├─ 三闸
│   ├─ 关键情报
│   └─ 参考组合（付费）
├─ 今日全部
│   ├─ 每场：方向标签 + 把握度 + 抽水
│   └─ 有已复核观点的场次打标
└─ 数据脉搏
```

首屏只回答：**今天最值得看什么？**

## 5. 串关参谋 3.0

### 5.1 双模式

入口从“串关体检”改为“串关参谋”：

```text
[帮我配]  [自己体检]
```

- **帮我配（主模式）**：从已复核观点自动生成 1–3 个组合。
- **自己体检（第二模式）**：保留现有四维体检，用户自己选腿。

### 5.2 组合类型

| 类型 | 腿数 | 目标 |
|---|---|---|
| 保守型 | 2 腿 | 高把握度、低成本、低相关性 |
| 均衡型 | 2–3 腿 | 把握度与成本平衡 |
| 进取型 | 3 腿 | 更高赔率，明确标高波动 |

候选池规则：

- 只取 `approved` 且未过期观点
- 排除已停售/已结算、coverage 不足
- 排除同一比赛/同一球队
- 同联赛/同时段降权
- 候选不足 2 条时，明确“今日不建议硬串”

### 5.3 组合卡片

```text
┌─ 保守型 · 2串1 ───────────────┐
│ 曼城 主胜 @1.85   把握度 中    │
│ 皇马 客队不败 @1.72 把握度 中  │
│                               │
│ 组合赔率 3.18 · 成本 21.4 元   │
│ 组合把握度：中                 │
│ AI 复核 · 18:30 · v3            │
│                               │
│ 成立条件：两场首发均无大幅轮换 │
│ 不成立：曼城两主力缺阵/盘口跌破 │
│                               │
│ [看为什么] [复制] [设提醒]     │
│ [只看单关]                    │
└───────────────────────────────┘
```

必须回答“为什么不是 3 串 1”：

> 多一腿成本 +8.4 元，组合把握度从“中”降到“弱”，第三腿与其他两场同联赛同时段，相关性偏高。

### 5.4 文案映射

| 旧说法 | 新说法 |
|---|---|
| 推荐买主胜 | 助理倾向：主队方向 |
| 主推 | 优先关注 |
| 串关方案 | 参考组合 / 组合思路 |
| 命中率 | 历史支持度 / 校准区间 |
| 稳 | 条件成立时 |
| 博取 | 高波动 / 进取型 |
| 不建议买 | 暂不纳入组合 |

## 5.5 人设文案

三种人设（`zhuanjia` / `laopao` / `meng`）只改变语气，不改变方向、概率、条件、成本、腿数。发布前由便宜 fast LLM 批量翻译成三套槽位文案，再由 AI 复核；模板只做兜底。配置与示例见 [persona-system.md](./persona-system.md)。

## 6. AI 复核流水线

```text
模型生成草稿
  → L1 硬规则（coverage/新鲜度/概率和/禁用词/组合约束）
  → L2 事实校验（每个数字映射 fact_id）
  → L3 人设/表达复核（三种 persona 分别检查）
  → L4 对抗复核（找反例/矛盾）
  → L5 组合复核（腿/成本/相关性）
  → 通过：自动发布（复核模型/时间/版本/哈希）
  → 失败：rewrite 1–2 次；仍失败则不发布
  → 停售自动过期
  → 数据变化自动失效
```

### 6.1 数据表（已实现首版）

```text
decision_snapshots
  id, match_id, trade_date, data_cutoff
  model_version, prompt_ver
  direction, confidence, prob_low, prob_high
  conditions, invalidators, rationale
  status: draft|reviewing|approved|review_failed|published|expired|withdrawn
  review_run_id, published_at, expires_at, payload_hash

recommendation_plans
  id, trade_date, risk_profile
  legs_json, combo_odds, cost, confidence
  rationale, conditions, invalidators
  status: draft|reviewing|approved|review_failed|published|expired|withdrawn
  review_run_id, published_at, expires_at, payload_hash

recommendation_copies            # ⏳ 待建（当前无此表；三套人设推荐文案未实现）
  draft_id, persona_id, text
  review_status, review_run_id, prompt_ver

review_runs
  id, subject_type, subject_id, status
  layers_json (L1–L5 + optional LLM), reviewer, prompt_ver, llm_degraded, created_at
```

### 6.2 API（部分实现）

```text
GET  /recommendations/today        仅 published + 未过期（已实现）
GET  /recommendations/{snapshot_id}      单条 published 详情（已实现；读时惰性 expire）
GET  /recommendations/plans/{plan_id}    单个 published 组合详情（已实现；读时惰性 expire）
POST /tools/parlay/plan            帮我配（已实现：确定性组合，不调用 LLM；preview 入口）
POST /tools/parlay/check           自己体检（已实现）
POST /recommendations/{id}/view    ⏳ 待做（浏览上报）
POST /recommendations/{id}/remind  ⏳ 待做（设提醒）
```

### 6.3 后台（部分实现）

```text
/admin 推荐主链页    主链运行/复核/发布/撤回（已实现）
/admin 组合预览页    组合预览（已实现只读；发布走推荐主链）
/admin 人设文案页    模型池 + 人设/槽位配置（已实现；三套文案预览待做）
/admin（规划）       CLV/校准/转化（规划）
```

AI 复核徽章对用户展示：

> AI 复核 · 11-05 18:30 · v3

## 7. 开源项目融合

| 项目 | 新角色 |
|---|---|
| `sahuan14/worldcup-betting-analyst-skill` | **输出模板核心**：比赛原型、角色分层、风险语言、组合建议结构；把“主推/可选/博取/跳过”改为“优先/关注/高波动/观望” |
| `JetQiao/football-prediction-skill` | 预测/回测方法论：walk-forward、champion/challenger、预测时点隔离 |
| `Johnserf-Seed/SportteryAPI` | 组合数学：M串N、单关/过关、500万封顶、void；作为 Python oracle |
| `magicjordan33/sports-betting-claude` | Kelly/CLV/anti-bias → 参考预算、复盘、失效条件 |
| `strumideld-bit/Football-Prediction-skill` | 场地切分战绩、同场地 H2H、支持度 → 判断依据（只借结构） |
| `infersports` / The Odds API | 低抽水市场基线 → “市场倾向 vs 模型倾向” |
| `penaltyblog` / `soccerdata` | 模型校准/离线历史数据 |
| `API-Football` | 首发/伤停/积分榜 |
| LLM Gateway | 只做委婉化/结构化，不产生方向或概率 |

`sahuan14` 的停售时间规则不采用，继续以官方 `sale_close = kickoff` 为准。

## 8. 指标与阶段

### 指标

- 免费 → 付费转化率
- 今日判断卡打开率、组合查看率、复制率
- 订阅续费率
- AI 复核通过率、重写率、方案撤回率
- CLV / 校准（Brier/log loss）
- 投诉/退款率

### 阶段

**Phase 1（2 周）**
- 首页“今日主看”卡（✅ 已消费 published snapshot；旧后端回退）
- 免费 1 条完整观点（✅ 前端已展示）
- `decision_snapshots` + AI 复核流水线（✅ 已实现）
- 文案词表替换（部分完成）
- `GET /recommendations/today`（✅ 仅 published）

**Phase 2（4 周）**
- 串关参谋“帮我配”（✅ 已实现未复核预览）
- 保守/均衡/进取三套组合（✅ 已实现）
- 组合 AI 复核/复制/提醒（复制 ✅；复核 ✅；提醒待做）
- 付费墙 + 订阅（待做）

**Phase 3**
- 临场更新/失效提醒
- 复盘/CLV
- 参考预算/仓位
- A/B 定价
