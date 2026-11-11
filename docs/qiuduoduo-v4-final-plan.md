# 球多多 · 完整产品与技术方案（v4.1 唯一有效版）

> 2026-11-12  
> **本文是唯一有效的产品/技术方案。**  
> 之前所有产品方案文档已标记作废，见文末「作废文档」。
>
> 结论：
>
> **产品方向成立，但必须先立三个事实源：赛果结算、人设文案、助理记忆。**  
> **会员只不做“充值支付”，权益、额度、计划分级、后台手动开通全部要做。**  
> **计划只展示方案，不做跟单、不自动记注、不代购。**

---

## 实现状态（2026-11-12）

本方案已按 v4.1 落到当前分支 `feat/v4-plan-settlement`，验证基线：后端 **338 passed**、移动端 **47 passed**、OpenAPI **158 路径 / 174 方法**、Alembic head `20261112_23`。以下区分“代码已实现”和“仍属下一阶段”，避免把方案当现状：

| 能力 | 状态 | 说明 |
|---|---|---|
| 4 Tab（助理/比赛/计划/我的） | ✅ 已实现 | 原记录 Tab 移入“我的 → 我的记录” |
| HeaderMetrics 四项指标 | ✅ 已实现 | 读 `engine_config`；无数据点显示“今日数据同步中” |
| 每日 AI 战绩 | ✅ 已实现 | `/stats/record/summary`，只统计 published + settled |
| 4 场定投计划 | ✅ v1 已实现 | `plan_cycles/plan_bets/plan_bet_legs`；三种风险结构；不足 4 场不硬凑 |
| 选场评分 | ✅ v1 已实现 | 只处理 1X2/让球；正 edge、正 EV、数据质量；同联赛 ≤2 场 |
| 多市场计划 | ❌ 未实现 | 大小球/BTTS/半全场等尚未完整入库，计划仍是竞彩 1X2/让球 |
| 自训练模型 | ⚠️ 脚手架 | `feature_snapshots/model_registry/training_runs` 已建表；训练、回测、影子上线未实现 |
| 会员等级/额度/计划门控 | ✅ 已实现 | 免费 1 场/日；Pro/Max 不限；Max 看完整计划 legs |
| 后台手动开通 | ✅ 已实现 | 开通/撤销写 `membership_events` + `admin_audit` |
| 充值/支付 | ⚠️ 仅假 UI | 不建订单、不接支付、不伪造支付成功 |
| 90 分钟结算 | ✅ 已实现 | FT90；整数亚盘 void/push；AET/PEN 不混入 1X2 |
| 计划自动结算 | ✅ 已实现 | `settle_open_cycles` 随赛果同步/seed 执行 |
| 人设 chat 接入 | ✅ 已实现 | `ChatBody.persona` + `assistant_copy` + DB slots |
| OPC 后台 | ✅ 基础版 | 用户/会员、AI 计划、异常队列、引擎配置已接 |
| 计划更新提醒/收藏 | ❌ 未实现 | 不做跟单；提醒只允许中性文案 |
| 生产 Postgres / v4 正式包 | ❌ 未完成 | 未切库；本轮只做 bundle 与模拟器验收 |

---

## 一、产品定位与总原则

### 1.1 定位

**一个 AI 足球助理，不是专家市场，不是数据终端。**

用户每天打开：

- 看昨天 AI 表现；
- 看今天值得看的比赛；
- 让助理分析自己选的一场；
- 看 AI 计划方案；
- 关注比赛，收到赛前/赛后消息。

### 1.2 四条原则

1. **事实由系统算，语气由人设说。**
2. **没有数据就明说，不编。**
3. **计划只展示方案，不做跟单、不代购、不自动记注。**
4. **系统自动跑，人只看异常。**

### 1.3 4 个 Tab

```text
助理 · 比赛 · 计划 · 我的
```

| Tab | 职责 |
|---|---|
| **助理** | 对话、选场、分析、盯盘、复盘、每日战绩 |
| **比赛** | 在售雷达、筛选、详情、串关入口 |
| **计划** | AI 计划方案、累计模拟收益、历史方案；免费/Pro 看历史摘要，Max 看今日完整方案 |
| **我的** | 会员、我的记录、人设、记忆、通知、合规、助理技能 |

原“记录”Tab 删除，个人票单/周报/公开账本移到“我的 → 我的记录”。  
没有正式推广，不存在老用户迁移问题，按新结构直接设计。

---

## 二、首页

### 2.1 顶部结构

保留：

- 全局悬浮头像，点击选比赛，选中后回首页聚焦分析；
- 右侧 HeaderMetrics，不点击、不展开；
- 不显示源状态、不显示今日场次。

HeaderMetrics 展示：

```text
● 已为你稳定运行 128 小时
预测引擎 V3.21
今日采集全网 23,045 条数据点
◉ 5 个盘口动态监控 · 7 大模型实时复审中
```

规则：

- `X 小时` 从用户注册时间计算，`max(1, floor(now - created_at))`；
- `已为你` 明确是个人陪伴时长，不是系统无故障时长；
- `23,045` 来自 `pulse.display.data_points`，后端系数控制，前端只格式化；
- `5 个盘口 / 7 大模型` 来自 `engine_config`，前端不写死；
- 只保留一个缓慢闪烁绿点，放在“5 盘口 / 7 模型”行；
- `reduceMotion` 时绿点静止；
- 无数据时显示“今日数据同步中”，不显示 0。

### 2.2 “5 个盘口 / 7 大模型”的真实性边界

这是展示口径，不是前端随意写死。  
必须在后台有真实映射：

```text
5 个盘口 = 1X2 + 让球 + 大小球 + BTTS + 半全场
7 大模型/复审层 = DC + SM + 市场 + 校准 + 规则 + LLM 复核 + 发布门
```

如果当前只接了 1X2，必须二选一：

**A. 先做真实接入**，再显示 5 个盘口。  
**B. 改成“5 路盘口信号 / 7 层模型复审”**，避免被用户问倒。

`engine_config` 必须有：

```text
version
markets_monitored
models_reviewing
data_points_factor
updated_at
updated_by
```

后台改动写 `admin_audit`。

### 2.3 每日战绩

每日第一次打开，助理先说：

```text
早上好。昨天 3 场，2 中 1；最近 30 天，24 天有命中。
```

三种人设：

- 理性专家：`昨天 3 场，2 中 1；最近 30 天，24 天有命中。`
- 感性老炮：`兄弟，昨天 3 场中了 2 场；最近 30 天，24 天有收获。`
- 元气搭子：`昨天 3 场中 2 场～最近 30 天有 24 天命中。`

规则：

- 只统计已发布 + 已结算；
- 昨天按竞彩日；
- 最近 30 天命中天数 = 有已发布推荐且至少 1 场命中的天数；
- 没有数据就返回 `null`，前端不硬写；
- 同一天只出现一次，本地记录已读；
- 用户问“最近准吗”，聊天回答同一套数字，可展开最近 20 场。

### 2.4 第一屏

```text
早上好。昨天 3 场，2 中 1；最近 30 天，24 天有命中。
今天 6 场，我只看好 1 场。
已发布 1 · 复核中 2 · 在售 6

[曼城 vs 利物浦  20:30  主胜 74%]

[看今天这场]  [换一场]
```

入口收敛：

- 悬浮头像 = 唯一“选比赛”主入口；
- “看今天这场” = 主按钮；
- “换一场” = 次按钮；
- 快捷回复最多 2 个：为什么不出 / 串关参谋；
- “今日在售”并入比赛 Tab。

---

## 三、比赛与详情

### 3.1 比赛页

```text
比赛                    ●            [串关 2]
[全部] [单关] [关注]               [更多]

20:30  曼城 vs 利物浦          ● 已发布
       停售 20:30 · 12 分钟后
       英超 · 抽水 9.2%
```

- 行内只保留时间、主客、停售倒计时、状态点；
- 联赛/抽水放第二行小字；
- 筛选默认只留全部/单关/关注；
- 串关参谋入口：比赛页右上角、详情页底部、我的技能。

### 3.2 详情页

第一屏：

```text
曼城 vs 利物浦
20:30 · 英超 · 让球 -1

主胜 74%
风险：客队近 3 轮进 12 球。

三条依据
· 主队近 5 场 xG 2.1 > xGA 0.8
· Pinnacle 主让半球，水位下调
· 客队两名主力伤缺

[关注] [加入串关] [记一注]
```

折叠：

- AI 深度解读
- 数据与三闸
- 更多玩法（Max）
- 证据与封存

---

## 四、计划 Tab：4 场定投组合

### 4.1 v1 范围

v1 的“AI 计划”不是一张竞彩串关票，而是：

```text
AI 定投计划
每期目标 4 场
每场基准 100
总预算 400
支持单关 + 2 串 1
期末结算整期总收益
```

不是全市场计划；全市场要等多市场数据和结算能力都齐了再开。

`RecommendationPlan` 继续保留，但只作为“串关组件/校验器”，不再作为计划本体。  
计划本体使用：

```text
plan_cycles
plan_bets
plan_bet_legs
```

### 4.2 三种模式

| 模式 | 结构 | 总投入 | 波动 | 默认 |
|---|---|---:|---|---|
| **稳健定投** | 4 场单关（100×4） | 400 | 低 | ✅ |
| **平衡定投** | 1 个 2 串 1（200，来自两场各 100）+ 2 单关（100×2） | 400 | 中 |  |
| **进取定投** | 2 个 2 串 1（200×2） | 400 | 高 |  |

关键：

- 每场预算 100；
- 串关不是额外加钱，而是把两场的 100 合并成 200；
- 总预算始终 400；
- 稳健模式默认 4 场全单关；
- 目标 4 场，但不足 4 场合格就少做，不硬凑。

### 4.3 页面结构

```text
AI 计划
[稳健定投] [平衡定投] [进取定投]

第 12 期 · 稳健定投
预算 400 · 4 场 · 3 注
已结算 2/4 · 暂计 +85

A 曼城 vs 利物浦   单关 100 @1.85   待结算
B 皇马 vs 巴萨     单关 100 @1.90   已中
C 拜仁 vs 多特     单关 100 @1.80   已中
D 巴黎 vs 马赛     单关 100 @1.95   待结算

本期总投入 400 · 当前回报 270 · 盈亏 +85

历史期数
第 11 期  +155
第 10 期  -25
第 9 期   +350
```

- 第一屏放当前期、累计模拟收益、历史期数；
- 净值曲线/回撤/CLV 放第二屏；
- 没有计划时显示“本期方案还没生成，一般 12:00 前更新”，不显示 +0.0%。

### 4.4 权限

| 用户 | 能看到 |
|---|---|
| 免费 | 历史期数摘要、累计模拟收益、当前期入口；当前期注单锁定 |
| Pro | 同上；AI 计划正文仍锁定 |
| Max | 当前期完整注单、串关结构、历史期数完整 legs |

明确：

```text
历史期数摘要（日期/结果/收益/注数）可见；
具体 legs / 方向 / 赔率仅 Max 可见。
```

Pro 点击“查看本期”时，提示：

```text
Pro 含竞彩分析，不含 AI 计划；Max 可看完整方案。
```

### 4.5 收益口径

- 按 `risk_level` 分开算，**不能三套相加**；
- 只统计 `plan_cycles.status=published`；
- 同一周期多版本，只取最新 published；
- 只算已结算注单；
- 单关收益 = `(赔率 - 1) × 100`；
- 2 串 1 收益 = `(两腿赔率乘积 - 1) × 200`；
- 期收益 = 所有 `plan_bets.pnl` 之和；
- 缺赔率/未结算的注单不计收益；
- 页面统一写“模拟收益 / 模拟本金”。

### 4.6 选场引擎：不能只看低水位

低赔率不是买点。  
**低赔率 + 没有 edge = 低回报 + 高抽水，是最差的组合。**

选场必须综合：

#### 1. 候选池硬过滤

只进入候选池的场次：

- `DecisionSnapshot.status=published`；
- `tier=verified`；
- 三闸通过，无 `pending_data`；
- 赔率完整、数据未过期；
- 不是 `market_reference`；
- 不是已停售/已结算；
- 有有效 `pick`。

#### 2. 单场评分

```text
edge = 模型概率 - 市场去水概率
EV = 模型概率 × 赔率 - 1
quality = 数据完整度 × 新鲜度
agreement = 模型 / Sportmonks / Pinnacle 的一致性
form = xG、xGA、伤停、阵容、休息天数、战意
clv = 入场赔率 vs 收盘/最新赔率
risk = 不确定性、联赛波动、阵容缺口
```

综合分：

```text
score =
  w1 * edge
+ w2 * EV
+ w3 * quality
+ w4 * agreement
+ w5 * form
+ w6 * clv
- risk_penalty
```

权重不是永久写死，进 `engine_config`，后台可审计。

#### 3. 组合约束

- 最多 4 场；
- 同一联赛最多 2 场；
- 同一球队最多 1 场；
- 不同开赛时段优先；
- 同一场不能出现多条腿；
- 不把同联赛/同时段的腿串在一起；
- 不足 4 场合格就少做。

#### 4. 单关 vs 串关

默认单关。  
只有满足以下条件才允许 2 串 1：

- 两场都在评分前列；
- 两场都有正 EV；
- 不同联赛/不同时段；
- 相关性低；
- 联合概率仍高于市场隐含；
- 稳健模式最多 1 个 2 串 1；
- 不做 3 串 1 起步。

#### 5. 反例

```text
1.30 的主胜，市场隐含 76.9%，模型 77.0%
→ edge 0.1pp，扣掉抽水/误差后没有价值，不选。

1.95 的主胜，市场隐含 51.3%，模型 56.0%
→ 有正 EV，数据完整，可选。
```

**不是赔率低就稳，是“真实概率高于市场”才稳。**

#### 6. 可解释

每个计划腿保存：

```text
model_prob
market_prob
edge
EV
quality_score
selection_reason
model_version
selection_version
feature_hash
data_cutoff
```

计划详情能回答：

```text
为什么选这场？
为什么这场是单关/串关？
为什么这场只投 100？
```

### 4.7 自训练模型路线

#### 阶段 1：先用现有数据

- DC v1.1；
- Sportmonks 1X2 / 让球；
- Pinnacle / 国际盘；
- xG、积分榜、伤停、阵容；
- 市场隐含概率；
- 先做规则 + 集成评分，不急着训练。

#### 阶段 2：特征快照

在 T-3h / T-30m 保存：

```text
feature_snapshots
  match_id
  captured_at
  features_json
  market_json
  lineup_json
  feature_hash
```

目的：

- 防止未来数据泄漏；
- 训练和线上推理用同一份特征；
- 可复算。

#### 阶段 3：离线训练

按联赛/市场分别训练：

- Dixon-Coles / Poisson；
- 梯度提升树；
- 市场先验 + 模型 stacking；
- 时间序列交叉验证；
- 校准（isotonic / Platt）；
- 评估 Brier / RPS / CLV / ROI；
- 样本不足不启用。

#### 阶段 4：影子与上线

```text
shadow → 对比市场基线 → 达到样本/指标 → 小流量 → 联赛启用
```

复用：

- `ModelEval`；
- `LeagueModelConfig`；
- `ModelRun`；
- `ops_jobs`。

新增：

```text
model_registry
training_runs
feature_snapshots
```

原则：

- 没跑赢市场基线，不启用；
- 不手工改权重；
- 每周回测，漂移告警；
- LLM 只解释，不选场。

### 4.8 计划数据表

```text
plan_cycles
  id
  name                 # 稳健定投 / 平衡定投 / 进取定投
  risk_level
  cycle_no
  start_at / end_at
  budget               # 400
  target_matches       # 4
  status               # draft / published / settled
  total_stake
  total_return
  pnl
  roi
  max_drawdown
  selection_version
  model_version
  published_at
  version

plan_bets
  id
  cycle_id
  bet_type             # single / parlay
  label
  stake                # 100 / 200
  odds
  status               # pending / won / lost / void
  pnl
  settled_at

plan_bet_legs
  id
  bet_id
  verdict_id
  match_id
  market
  line
  direction
  odds
  allocation           # 每腿 100
  model_prob
  market_prob
  edge
  quality_score
  selection_reason
  result
  settled_at
```

约束：

- 每腿 `allocation=100`；
- 2 串 1 的 `plan_bets.stake=200`；
- `plan_cycles.total_stake` = 所有 bet stake 之和；
- 期收益 = 所有 bet pnl 之和；
- `market_settlements` 挂 `plan_bet` + `leg_index`；
- 方案发布后不可改腿，只能新版本。

### 4.9 不做跟单

- 不做 `plan_follows`；
- 不做自动记注；
- 不做代购；
- 不做资金托管。

可选增强（不阻塞 v1）：

- `收藏方案`（本地/后端均可）；
- `方案更新提醒`（只提醒，不跟单）；
- `分享方案`。

收藏/提醒不等于跟单，文案必须写清楚。

---

## 五、会员与权益

### 5.1 边界

| 能力 | 状态 |
|---|---|
| 会员等级 free/pro/max | 做 |
| 权益判断 | 做 |
| 每日免费额度 | 做 |
| 计划分级 | 做 |
| 后台手动开通会员 | 做 |
| 会员到期/续期/撤销 | 做 |
| 充值/支付 UI | 只做 UI，不接支付 |
| 订单/支付回调 | 以后做 |

### 5.2 权益矩阵

| 能力 | 免费 | Pro | Max |
|---|---|---|---|
| 每日分析 | 1 场 | 无限（竞彩 1X2/让球） | 无限（全市场，数据接入后逐项开放） |
| 竞彩胜平负/让球 | 1 场 | ✅ | ✅ |
| 竞彩比分/总进球/半全场 | ❌ | ✅ | ✅ |
| 大小球/BTTS/亚盘/国际盘 | ❌ | ❌ | ✅（数据接入后） |
| 串关参谋 | 示例 | 竞彩串关 | 跨市场串关 |
| AI 计划历史/累计收益 | ✅ | ✅ | ✅ |
| 今日 AI 计划完整方案 | ❌ | ❌ | ✅ |
| 关注比赛/推送 | 1 场 | 5 场 | 无限 |
| 会员充值 | 假 UI | 假 UI | 假 UI |
| 后台手动开通 | — | ✅ | ✅ |

### 5.3 数据表与约束

```text
user_memberships
  id
  user_id
  tier              # pro / max
  status            # active / expired / revoked
  starts_at
  expires_at
  source            # admin_manual / payment / trial
  granted_by
  note
  created_at
  updated_at

membership_events
  id
  user_id
  action            # grant / extend / revoke / expire
  tier
  before_json
  after_json
  actor
  note
  created_at

analysis_quota
  user_id
  trade_date
  limit_count
  used
  updated_at
  UNIQUE(user_id, trade_date)

analysis_usage
  id
  user_id
  trade_date
  match_id
  created_at
  UNIQUE(user_id, trade_date, match_id)
```

约束：

- `user_memberships` 同一用户只允许一条 `active`；
- `analysis_quota` 唯一键 `(user_id, trade_date)`；
- `analysis_usage` 保证同一场只扣一次；
- 竞彩日 05:00 重置；
- 会员到期 job 每天跑；
- Pro 续 Max / Max 降 Pro 必须写事件；
- 手动开通写 `membership_events` + `admin_audit`。

### 5.4 市场权限

新增：

```text
market_access
  tier
  market_key
  enabled
  note
```

种子：

- Pro：`1x2`, `hhad`, `score`, `total_goals`, `htft`
- Max：全部；但 `enabled` 由数据接入状态控制。

Max 数据未接完时：

- 手动开 Max 仍可看计划；
- 不能看未接入的市场；
- UI 写“全市场逐项开放”。

### 5.5 手动开通

管理后台：

```text
用户管理
→ 搜索用户
→ 查看当前会员
→ 手动开通 Pro / Max
→ 7 天 / 30 天 / 90 天 / 自定义
→ 备注
→ 确认
```

API：

```text
GET  /membership/me
GET  /admin/api/users?query=&tier=
GET  /admin/api/users/{id}
POST /admin/api/users/{id}/membership
POST /admin/api/users/{id}/membership/revoke
```

规则：

- 手动开通立即生效；
- 写 `membership_events` + `admin_audit`；
- 到期自动变 expired；
- 撤销立即生效；
- 只有 admin 角色能操作，operator 只读；
- 前台显示“已开通至 …”，不显示支付成功。

### 5.6 充值假 UI

价格表以运营最终确认为准。当前建议：

| 方案 | 7 天 | 月付 | 季付 |
|---|---:|---:|---:|
| Pro | ¥168 | ¥499 | ¥1,199 |
| Max | ¥268 | ¥699 | ¥1,699 |

说明：

- 原 Pro 季付 999 只做首季促销，不做常驻价；
- 原 Max 7 天 199 只做首周促销，不做常驻价；
- 会员页展示价格；
- `[立即开通]` 只提示“充值暂未开放”；
- 不创建订单；
- 不接支付 SDK；
- 不写支付回调；
- 不伪造支付成功；
- 后台手动开通才是当前真实路径。

---

## 六、人设系统

### 6.1 唯一事实源

```text
persona_profiles
persona_copy_slots
  persona_id
  slot_key
  template
  version
  enabled
```

所有文案走同一 renderer：

```text
canonical facts
  + persona slot
  → assistant_copy.render()
  → 前端渲染
```

前端 `COPY` 只保留离线 fallback，不再作为主来源。

`GET /personas` 必须返回：

```text
version
profiles
slots
```

前端按 version 缓存；服务端版本更新后异步刷新。

### 6.2 Chat 接入

- `ChatBody` 增加 `persona`；
- `respond(..., persona=...)`；
- 所有回复走 `assistant_copy.render`；
- 事实包由后端生成；
- 数字白名单校验；
- 禁用词扫描；
- LLM 只做开放聊天和语气翻译；
- 首页和独立 `/assistant` 共用同一 mutation/渲染组件。

### 6.3 必须补的 slot

```text
assistant_daily_record
assistant_buy_tonight
assistant_why_not
assistant_postmortem
assistant_analysis
assistant_memory
assistant_empty
assistant_fallback
assistant_status
plan_summary
plan_locked
plan_history
```

### 6.4 后台与测试

- 三版预览；
- facts diff；
- 数字白名单；
- 禁用词；
- 版本发布/回滚；
- fallback 率；
- `update_slot` 白名单扩展到全部 slot；
- 同一事实三种人设 `facts diff = 0`；
- 切换人设后结论不变；
- 卡片/聊天/推送数字一致。

`narrate.py` 和前端 `COPY` 逐步降级为 fallback，不能继续新增硬编码。

---

## 七、赛果与结算

### 7.1 能拿到什么

- Sportmonks：已映射 fixture 的赛果，FT/AET/PEN；
- football-data：五大联赛兜底；
- 未映射场次：拿不到，必须显示缺口；
- 当前 `SportmonksMatchData` 只覆盖已映射竞彩场次，不是所有竞彩场次。

### 7.2 90 分钟口径

竞彩 1X2、让球、大小球、BTTS、正确比分通常按 **90 分钟**结算。  
当前 `parse_score()` 取 `CURRENT`，`_FINISHED` 包含 `AET/PEN`，杯赛可能拿加时点球后的比分结算 1X2，这是必须修的 bug。

规则：

| 市场 | 口径 |
|---|---|
| 1X2 / 让球 / 大小球 / BTTS / 正确比分 | FT90，不含加时点球 |
| 半全场 | HT + FT90 |
| 先进球 | 90 分钟内进球顺序 |
| 晋级/夺冠 | 可用 AET/PEN，单独市场 |

### 7.3 数据表

```text
match_results
  fixture_id
  status              # FT / AET / PEN
  ft_home / ft_away   # 90 分钟
  ht_home / ht_away
  events_json
  source
  raw_hash
  retrieved_at

market_settlements
  id
  subject_type        # verdict / plan
  subject_id          # verdict_id / plan_id
  leg_index           # plan 腿序号，verdict 为 null
  market
  line
  direction
  rules_version
  result
  won
  settled_at
  source
```

计划腿不能用不存在的 `plan_pick` 表挂载。  
统一用：

```text
subject_type = plan_bet
subject_id = plan_bet.id
leg_index = 0..n
```

`RecommendationPlan` 只作为串关组件/校验器，不再作为计划本体。

### 7.4 自动链路

```text
result.ingested
  → result.normalized
  → market.settled
  → verdict.settled
  → performance.updated
  → notification.queued
```

要求：

- 独立 `settle_pending` job，不只依赖插入；
- 每 5–10 分钟扫描待结算；
- 幂等 `dedupe_key`；
- 结果源冲突进异常队列；
- 不允许静默用错误比分结算；
- 所有下游只读 `market_settlements` / `performance_daily`。

### 7.5 结果源冲突

优先级：

```text
Sportmonks fixture_id > football-data
```

如果两个源比分不一致：

- 不自动结算；
- 写 `ops_exceptions`；
- 后台人工确认；
- 记录 `raw_hash`。

### 7.6 下游统一

以下全部读同一份结算/战绩：

- AI 单场战绩
- AI 计划收益
- 公开账本
- 周报
- 赛后复盘
- 连败保护
- 推送
- 模型评估
- 管理后台

不允许每个接口自己算 `win/lose`。

### 7.7 迁移

- 新列全部 nullable；
- 历史 `MatchResult` 标记 `legacy`；
- 能补 FT90 的重新补；
- 不能补的不改历史结论，但在后台标记“旧数据未验证”；
- 旧的 `Verdict.settled` 不直接当 90 分钟事实；
- 新结算写入 `market_settlements`，逐步替换旧字段。

---

## 八、后端架构

### 8.1 模块化单体

不拆微服务。  
按领域分层：

```text
Market Data / Results
Prediction
Recommendation
Assistant
Commercial
Read Models
```

### 8.2 数据流

```text
竞彩 + Sportmonks + football-data
        ↓
   ingest / normalize
        ↓
   match_results / market_settlements
        ↓
   verdict / snapshot / plan
        ↓
   performance read models
        ↓
   assistant / push / admin
```

### 8.3 事实源

| 事实 | 唯一来源 |
|---|---|
| 赛果 | `match_results` |
| 市场结算 | `market_settlements` |
| 预测 | `Verdict` |
| 发布 | `DecisionSnapshot` |
| 计划 | `plan_cycles` / `plan_bets` / `plan_bet_legs` |
| 战绩 | `performance_daily` |
| 人设 | `persona_copy_slots` |
| 会员 | `user_memberships` |
| 记忆 | `Memory` + `user_profile_features` |
| 异常 | `ops_exceptions` |

### 8.4 新增表

```text
market_settlements
performance_daily
plan_cycles
plan_bets
plan_bet_legs
feature_snapshots
model_registry
training_runs
user_profile_features
assistant_threads
assistant_messages
ops_jobs
ops_exceptions
user_memberships
membership_events
analysis_quota
analysis_usage
engine_config
market_access
```

`RecommendationPlan` 保留，但只作为串关组件/校验器，不作为计划本体。

### 8.5 事件

```text
domain_events
  id
  type
  aggregate_type
  aggregate_id
  payload
  dedupe_key
  payload_hash
  created_at
  processed_at
```

事件：

- `result.settled`
- `verdict.published`
- `plan.published`
- `membership.granted`
- `membership.revoked`
- `push.queued`

`Event` 继续做通知扇出；`RecommendationEvent` 做发布审计；不要把三者混成一个表。

---

## 九、API

### 9.1 首页

```text
GET /stats/engine
GET /stats/record/summary
GET /stream
GET /recommendations/today
GET /matches/on-sale
```

`/stats/engine`：

```json
{
  "version": "V3.21",
  "running": true,
  "uptime_hours": 128,
  "today_data_points": 23045,
  "markets_monitored": 5,
  "models_reviewing": 7
}
```

`private, no-store`，前端 5 分钟刷新；`today_data_points` 复用 `pulse` 缓存。

`/stats/record/summary`：

```json
{
  "yesterday": {"picks": 3, "hits": 2},
  "last_30_days": {"hit_days": 24, "picks": 58, "hits": 36}
}
```

### 9.2 计划

```text
GET /plans/current?risk=stable
GET /plans/history?risk=stable&days=30
GET /plans/summary
GET /plans/cycles/{cycle_id}
```

- 历史摘要公开；
- 当前期完整注单需要 Max；
- 非 Max 返回 `locked=true`，不返回 `plan_bets` / `plan_bet_legs`；
- Max 详情返回 `selection_reason / model_prob / market_prob / edge / quality_score`；
- 不提供 follow 接口；
- 收藏/提醒可选，单独接口；
- 计划列表先取 cycle，再批量查 bets/legs，避免 N+1。

### 9.3 会员

```text
GET /membership/me
GET /admin/api/users
POST /admin/api/users/{id}/membership
POST /admin/api/users/{id}/membership/revoke
```

### 9.4 性能

- 新接口全部 `response_model`；
- 列表不返回完整 payload；
- 计划列表先取 plan，再 `IN` 查 verdict；
- 公开接口缓存 30–60s；
- 会员/计划今日接口 `private, no-store`；
- OpenAPI 重新生成 client；
- 首页并行请求，HeaderMetrics 不阻塞主内容；
- P1 可加 `/assistant/home` BFF，减少首屏请求数。

---

## 十、管理后台 OPC

### 10.1 定位

OPC = 一人公司驾驶舱。  
不是 CRUD 页面集合，而是：

```text
系统自动跑，人只看异常。
```

### 10.2 导航

```text
今日
  状态条：可发布 / 异常 / 数据源 / 今日成本
  异常队列
  今日流水

内容
  推荐主链
  AI 计划
  人设文案

数据
  采集器
  Sportmonks / 数据源
  赛果与结算
  模型联赛表

用户
  用户管理
  手动开通会员
  会员到期/撤销

系统
  调用用量
  运维
  账号
  审计
  日志
```

### 10.3 异常队列

持久表 `ops_exceptions`，不是每次工作台现算。

每条：

- 严重度
- 一句话原因
- 建议动作
- 一键执行
- 审计

类型：

- 采集器断流
- 映射缺失
- 赔率缺失
- 赛果冲突
- 90 分钟口径异常
- 结算差异
- 计划收益不一致
- 人设 fallback 率高
- 推送失败
- 成本/配额预警

### 10.4 任务

`ops_jobs`：

- 最后运行
- 耗时
- 成功/失败
- 错误
- 下次运行

任务：

- 采集
- Sportmonks 同步
- 赛果同步
- 结算
- 战绩聚合
- 计划收益
- 会员到期
- 人设翻译
- 推送

### 10.5 用户管理

列表：

- 用户
- 手机/邮箱
- 注册时间
- 当前会员
- 到期时间
- 来源
- 最近活跃

操作：

- 开通 Pro/Max
- 延长
- 撤销
- 备注
- 审计

只有 admin 可写；operator 只读。

### 10.6 成本

- LLM 调用
- Sportmonks/API-Football 配额
- 存储
- 单用户成本
- 月度毛利

OPC 每天只看异常，不看图表墙。

---

## 十一、记忆与推送

### 11.1 三层记忆

| 层 | 内容 | 来源 |
|---|---|---|
| 显式记忆 | 主队、风险偏好、不喜欢高赔 | 用户说“记住…” |
| 行为记忆 | 常看联赛、关注球队、看过哪些场 | `InteractionEvent` / `WatchTarget` / `Bet` |
| 情景记忆 | 上次问的比赛、上次结论 | `assistant_threads` |

### 11.2 数据

```text
Memory                  # 现有显式记忆
user_profile_features   # 派生特征
assistant_threads       # 会话摘要
assistant_messages      # 消息与 facts_hash
```

特征：

```text
team_affinity
league_affinity
risk_preference
active_hours
odds_range
content_preference
```

规则：

- 显式 > 派生；
- 置信度 + 过期；
- top 3–5 条进入上下文；
- 用户可见可删；
- 冲突必问；
- 低置信度不主动说“我记得”。

### 11.3 推送

场景：

- 早上：昨天战绩 + 今日一场
- 赛前：关注比赛 T-30
- 赛后：结果 + 复盘
- 计划：今日方案更新（只推给看过/收藏计划的用户）
- 沉默用户：一周一次召回

限制：

- 每日最多 2 条；
- 静默时段；
- 去重；
- 不伪造人数/结果；
- 深链必须能打开对应页面；
- 计划更新不能全量推。

### 11.4 低成本

- 80% 模板 + 规则，20% LLM；
- 每日简报不调 LLM；
- 推送按人群分段，不按用户逐个调；
- 夜间批处理记忆；
- `persona_copy_cache` 按 facts_hash 缓存；
- `llm_gateway` 预算/缓存/降级。

### 11.5 隐私

- `assistant_messages` 设保留期；
- 用户可删除记忆；
- 不推断敏感信息；
- 不把聊天全文塞进 prompt；
- 不向第三方上传原始聊天。

---

## 十二、性能、正确性、安全

### 12.1 性能

- 首页并行请求，HeaderMetrics 不阻塞主内容；
- 计划摘要 60s 缓存；
- 战绩摘要 60s 缓存；
- 列表不返回完整 payload；
- 批量查询，避免 N+1；
- 375px / 390px 实测 HeaderMetrics；
- 计划页首屏不画重图表。

### 12.2 正确性

- 90 分钟口径；
- 时区：竞彩日 05:00，UTC 存储；
- 幂等：settlement / performance / push；
- 版本：persona / plan / snapshot；
- 只统计 published + settled；
- 计划收益按 risk_level 分开；
- 会员唯一 active。

### 12.3 安全

- 管理后台 RBAC + CSRF + 会话撤销；
- 手动开通会员写审计；
- 支付假 UI 不接订单；
- 不返回用户隐私；
- 记忆可删除；
- 推送深链校验。

### 12.4 测试

- 90 分钟 vs AET/PEN；
- 多市场结算；
- 结果源冲突；
- 计划收益 per risk；
- 计划历史不足；
- 会员到期/手动开通/撤销；
- 免费额度 05:00 重置；
- 同一场不重复扣额度；
- 三版人设 facts diff；
- 推送上限/静默；
- 375px HeaderMetrics。

---

## 十三、实施顺序

### P0：结算与战绩

1. 修 90 分钟口径；
2. 扩展 `MatchResult`；
3. 新增 `market_settlements`；
4. 独立 `settle_pending` job；
5. 新增 `performance_daily`；
6. AI 战绩/计划收益/周报/账本统一读它。

### P1：人设单一事实源

1. 扩 `persona_copy_slots`；
2. `ChatBody.persona`；
3. `assistant_copy.render`；
4. 前端 fallback；
5. 三版预览 + 测试。

### P2：计划组合引擎

1. `plan_cycles` / `plan_bets` / `plan_bet_legs`；
2. 选场引擎 v1：硬过滤 + 评分 + 分散约束；
3. 单关/2 串 1 组合；
4. 计划收益与结算；
5. `/plans/current` / `/history` / `/summary`；
6. 后台 AI 计划页；
7. 初始只做 1X2/让球。

### P3：会员权益

1. `user_memberships` / `membership_events` / `analysis_quota` / `analysis_usage`；
2. `market_access`；
3. `GET /membership/me`；
4. 计划分级；
5. 免费额度；
6. 后台用户管理手动开通；
7. 充值假 UI。

### P4：UI 重构

1. 4 Tab：助理/比赛/计划/我的；
2. 记录迁移到我的；
3. HeaderMetrics；
4. 首页每日战绩；
5. 计划页；
6. 详情折叠；
7. 串关入口。

### P5：记忆与推送

1. `user_profile_features`；
2. 夜间聚合；
3. 每日简报模板；
4. 场景推送；
5. 记忆页。

### P6：OPC 驾驶舱

1. `ops_jobs` / `ops_exceptions`；
2. 异常队列；
3. 成本卡；
4. 赛果/计划/人设异常；
5. 审计。

---

## 十四、验收

- 赛果 90 分钟结算正确；
- 多市场结算可扩展；
- AI 战绩全站同一口径；
- 计划是 4 场定投组合，不是单张串关；
- 每期 4 场 ×100，总预算 400；
- 单关/2 串 1 可混合，收益按整期结算；
- 选场不是只看低赔率，必须有 edge/数据质量/组合约束；
- 计划收益不重复计算；
- 计划历史不空/不造假；
- 免费/Pro/Max 权限由后端判断；
- 后台手动开通会员立即生效；
- 充值 UI 明确“暂未开放”；
- 三种人设同一场事实一致；
- 聊天/卡片/推送同一文案源；
- HeaderMetrics 数字真实可解释；
- 首页首屏 3 秒能看懂；
- 计划页一屏能看懂；
- 管理后台异常队列可操作；
- 推送不超频、不伪造；
- 375px 布局不挤。

---

## 十五、不做

- 不做跟计划/自动记注/代购；
- 不接真实支付；
- 不拆微服务；
- 不新建重复的 AI 计划表；计划本体用 `plan_cycles / plan_bets / plan_bet_legs`，`RecommendationPlan` 只做串关组件；
- 不手工改模型权重；
- 不伪造赛果/战绩/人数；
- 不做假数据上线；
- 不在前端写死人设文案和指标数字；
- 不在旧文档上继续迭代。

---

## 十六、开放问题

上线前必须确认：

1. “5 个盘口 / 7 大模型”是真实接入，还是改成“5 路 / 7 层”；
2. `plan_cycles` 已发布历史是否够 30 天；
3. Max 全市场逐项开放的顺序；
4. 计划页是否加“收藏/提醒”（不与跟单混淆）；
5. 会员价格最终版本；
6. 手动开通会员的默认时长与审批规则；
7. 计划选场评分的初始权重，以及是否先只做 1X2/让球；
8. 自训练模型的首批联赛与上线门槛。

**2026-11-12 实现后的状态：**

1. 目前仍是后台配置展示“5 个盘口 / 7 大模型”，真实计划只处理 1X2/让球；在多市场数据补齐前，不能对用户宣称 5 个盘口数据已全部入库。
2. 历史期数从第一期开始累计，`/plans/history` 返回实际条数；不足 30 天不补假数据。
3. 未定；当前 Max 只能看已接入市场，页面写“逐项开放”。
4. 未做；收藏/提醒都不等于跟单，做之前必须先定文案边界。
5. 当前会员页展示 Pro ¥499/月、¥1,199/季；Max ¥699/月、¥1,699/季；7 天价格未进入移动端卡片。
6. 后台手动开通支持 7/30/90 天与自定义；默认时长与审批规则仍由运营定。
7. 已按 v1 只做 1X2/让球；评分是 edge/EV/数据质量规则，不是自训练模型。
8. 未开始；`feature_snapshots/model_registry/training_runs` 只是脚手架。

---

## 十七、一句话

**先把赛果结算、人设文案、助理记忆三个事实源做对；再把 4 Tab、计划页、会员权益、OPC 后台接上。**  
**会员只假充值，权益和手动开通都是真的；计划只展示方案，不做跟单。**

---

## 作废文档

以下文档已被本文取代，仅作历史参考：

- `docs/ai-warroom-monetization-plan.md`
- `docs/ai-native-token-plan.md`
- `docs/ai-match-membership-plan.md`
- `docs/ai-daily-one-subscription.md`
- `docs/membership-pro-max-ai-plan.md`
- `docs/grounded-app-optimization.md`
- `docs/mobile-ai-assistant-refactor.md`（UI 部分已被本文取代，技术细节可参考）
