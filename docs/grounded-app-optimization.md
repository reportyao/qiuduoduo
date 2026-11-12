# 球多多 · 基于现有 App 的优化重构（v2 修正版）

> **已作废（2026-11-12）**：以 [qiuduoduo-v4-final-plan.md](./qiuduoduo-v4-final-plan.md) 为唯一有效方案。本文仅作历史参考。

> 2026-11-12 修正：
> 1. **保留首页顶部悬浮头像**，点击选比赛进对话分析的逻辑不变；
> 2. **保留 HeaderMetrics 的“预测引擎 v3 · N 个数据点”**，不删，反而增加信息量；
> 3. **记录 Tab 改为“计划”Tab**，承载 AI 计划跟单；
> 4. 个人票单/周报/公开账本移到“我的”，功能不丢；
> 5. 整体 UI 做减法：首页清晰、详情分层、计划一屏看懂。

## 一、现有代码事实

| 层 | 现状 | 位置 |
|---|---|---|
| 底部 Tab | 助理 / 比赛 / 记录 / 我的 | `apps/mobile/app/(tabs)/_layout.tsx:18-21` |
| 首页 | 对话流；顶部 Header 在 ScrollView 内；悬浮头像常驻 | `apps/mobile/app/(tabs)/index.tsx:355-388` |
| 悬浮头像 | 点击打开今日比赛选择器，选中后回首页聚焦分析 | `apps/mobile/src/components/FloatingAssistant.tsx` |
| HeaderMetrics | “在线 / 预测引擎 v3 · N 个数据点 / 相对时间” | `apps/mobile/src/features/home/components/HeaderMetrics.tsx` |
| 记录页 | 个人票单 / 周报 / 公开账本 | `apps/mobile/app/(tabs)/records.tsx` |
| 助理聊天 | `/chat` 规则意图 + 硬编码文案，没有 persona 参数 | `jieqiu-backend/app/routers/w6.py:422` |
| 人设 | `PersonaProfile` / `PersonaCopySlot` 已有；前端 `COPY` 三套 | `jieqiu-backend/app/modules/persona_registry.py`、`apps/mobile/src/features/personas/personas.ts` |
| 发布链 | `DecisionSnapshot` 发布；`RecommendationPlan` 是串关预览 | `jieqiu-backend/app/models.py:596-656` |
| 数据 | 只有 1X2（237）+ 市场 1；没有大小球/BTTS/半全场 | `jieqiu-backend/app/modules/sportmonks.py:205-224` |
| 会员/支付 | 没有会员、权益、支付表 | `docs/database-architecture.md:180` |
| 后台 | 工作台/推荐主链/组合预览/人设/模型效果等 | `jieqiu-backend/app/static/admin/index.html:63-79` |

## 二、新的 4 Tab

```text
助理 · 比赛 · 计划 · 我的
```

| Tab | 职责 | 变化 |
|---|---|---|
| **助理** | 对话、选场、分析、盯盘、复盘 | 保留现有逻辑；顶部悬浮头像和 HeaderMetrics 不动 |
| **比赛** | 在售雷达、筛选、详情 | 保留；补“AI 实力”入口 |
| **计划** | **AI 计划 + AI 战绩**：计划跟单、净值、今日 picks、历史周期；AI 单场战绩 | **替换原“记录”Tab** |
| **我的** | 会员、我的记录、人设、记忆、通知、合规、工具 | 接收原记录页的票单/周报/公开账本 |

### 记录页怎么处理

不是删掉，而是降级为“我的”里的二级页：

```text
我的
├─ 会员与权益
├─ 我的记录
│   ├─ 票单
│   ├─ 周报
│   └─ 公开账本
├─ 助理风格 / 记忆
├─ 通知
└─ 助理技能（串关/抽水/赔率/仓位/回本）
```

路由建议：

- `app/(tabs)/plans.tsx` 新增；
- `app/(tabs)/records.tsx` 移到 `app/records/index.tsx`，从“我的”进入；
- `app/records/weekly.tsx`、`app/records/ledger.tsx` 保留；
- `BottomTabBar` 的 `records` 换成 `plans`，图标用 `layers-outline` / `analytics-outline`。

## 三、首页：保留两个“老东西”，但让它们更高级

### 1. 悬浮头像不动

- `FloatingAssistant` 继续常驻 4 个 Tab；
- 点击仍然打开 `GlobalMatchPicker`；
- 选中比赛后仍然 `setFocus` 回首页，展示 `FocusSection`；
- 不新增“顶部状态条”替代它，避免两个头像/两套入口。

### 2. HeaderMetrics 不动文案，增加信息量

保留：

```text
● 在线
预测引擎 v3 · 3,300 数据点
```

新增第二行/第三行，仍用真实数据：

```text
● 在线
预测引擎 v3 · 3,300 数据点
6/6 源 · 今日 6 场 · 12s 前
```

数据来源：

- `pulse.display.dataPoints`：现有数据点；
- `pulse.sources`：在线/部分/缺失源数量；
- `stream.stats.total`：今日场次；
- `pulse.asOf / stale_seconds`：刷新时间；
- 模型覆盖：`stream.stats.promoted` 或 `pulse.counts.model_runs`。

交互：

- `HeaderMetrics` 外层改成可点击，打开现有 `DataStatusSheet`；
- 不加假图表、不加假在线人数；
- 窄屏时第三行只保留“6/6 源 · 12s”，今日场次放 `DataStatusSheet`。

### 3. 首页第一屏做减法

现在 `AssistantBrief` 里有：

- 一段开场；
- 4 个统计；
- 数据状态链接；
- 比赛选择器；
- 4 个快捷回复。

第一屏信息偏多。改成：

```text
① 一句话：今天 6 场，我只看好 1 场。
② 一行小数据：已发布 1 · 复核中 2 · 在售 6
③ 比赛选择器（最多 3 个选项，其余“展开全部”）
④ 两个主操作：看这场 / 换一场
⑤ 输入框
```

把“今日扫描/已核验/已发布预测/在售”四个技术标签，改成用户能懂的三项：

- 今天能看
- 我有把握
- 还在等数据

技术口径放 `DataStatusSheet`，首页不展开。

## 四、计划 Tab：一屏看懂“跟不跟”

### 4.1 页面结构

计划 Tab 不能只服务 Max，否则免费/Pro 打开就是一面付费墙。所以它做两个分段：

```text
[AI 计划]  [AI 战绩]
```

**AI 计划**：

```text
稳健计划        Max 专享
当前第 2/7 天 · 净值 1,082
本期 +4.2% · 最大回撤 -4.1%
[跟这个计划]

今日 picks
· 曼城 vs 利物浦 · 主胜 · 1.92 · 1% 模拟本金
· 皇马 vs 巴萨 · 大 2.5 · 1.88 · 1% 模拟本金

[净值曲线]
[历史周期]
```

**AI 战绩**（所有用户可见）：

```text
近 30 天 58 中 36（62.1%）
平均赔率 1.87 · CLV +2.4% · 最大回撤 -5.8%

近 20 场
🔴 🔴 ⚪ 🔴 🔴 🔴 ⚪ 🔴 🔴 🔴

[近 7 天] [近 30 天] [近 90 天]
```

这样免费/Pro 打开计划 Tab 也有真实内容，不是死页；Max 的差异是“能跟计划、看今日 picks”，不是“能不能打开这个 Tab”。

### 4.2 三种计划

| 计划 | 风险 | 单注 | 周期 | 市场 |
|---|---|---|---|---|
| 稳健计划 | 低 | 1% | 7 天 | 胜平负/让球/双重机会 |
| 平衡计划 | 中 | 2% | 14 天 | 1X2 + 大小球 + BTTS |
| 进取计划 | 高 | 0.5–1% | 30 天 | 正确比分/半全场/高赔 |

### 4.3 权限

- 免费：AI 战绩可见；AI 计划只看到公开净值和“Max 可跟”，不能看今日 picks；
- Pro：AI 战绩可见；AI 计划仍锁（按之前约定 Pro 不能看 AI 计划）；
- Max：跟计划、看今日 picks、看历史周期、看计划净值；
- 锁定态不泄露具体 picks，只显示“Max 可跟”；
- 如果 Pro 点“跟计划”，明确告诉他“Pro 含竞彩分析，不含 AI 计划”，不要只弹一个冷冰冰的锁。

### 4.4 跟单逻辑

- 跟计划 = 订阅这个计划的每日 picks；
- 不是真实代购/资金托管，明确“模拟跟单”；
- 可暂停、可退出；
- 每日推送“计划第 N 天，今天 2 注”；
- 结算后更新净值/回撤；
- 历史周期可查，亏损也展示。

### 4.5 后端

```text
ai_plans
  id, name, risk_level, period_days, unit_pct, markets_json,
  min_tier, enabled

plan_cycles
  id, plan_id, cycle_no, start_date, end_date, starting_bankroll,
  current_bankroll, return_pct, max_drawdown, status

plan_picks
  id, cycle_id, match_id, market, direction, odds, probability,
  edge, stake, result, pnl, settled_at

plan_follows
  user_id, plan_id, cycle_id, status, created_at
```

API：

```text
GET  /plans
GET  /plans/{id}
GET  /plans/{id}/cycles
POST /plans/{id}/follow
POST /plans/{id}/unfollow
```

计划引擎只消费已发布/已核验的 canonical picks；不直接读原始 verdict 当推荐。

## 五、助理：保留现有对话，补人设一致性

现状问题：

- `/chat` 没有 persona；
- 前端 `useChatMutation` 不传人设；
- 回复硬编码，和 `AssistantBrief` / `narrate.py` 的语气不一致；
- `update_slot` 只允许 `DEFAULT_SLOTS`，后台改不了新增 slot。

改法：

1. `ChatBody` 增加 `persona`，前端传当前人设；
2. `respond(..., persona=...)`，所有文案走 `assistant_copy.render`；
3. 扩展 `persona_registry` 的 assistant slots；
4. `update_slot` 白名单扩到全部 slot；
5. 首页和独立 `/assistant` 共用同一个 mutation；
6. 事实/数字不由 LLM 生成；
7. 三种人设同一场必须同方向、同概率、同风险。

## 六、前端 UI Review：现在的问题和改法

### 1. 首页

问题：

- `FloatingAssistant` 在顶部中间，`AppHeader` 左侧标题、右侧 Metrics；再加信息量会挤；
- `AssistantBrief` 四个统计 + 数据链接 + 选择器 + 四个快捷回复，第一屏偏重；
- “今日扫描/已核验/已发布预测/在售”是内部口径，用户要理解成本。

改法：

- 悬浮头像尺寸/位置不动；HeaderMetrics 控制在 3 行内，第三行小字；
- AssistantBrief 改成“一句话 + 三项小数据 + 选择器 + 两个主操作”；
- 技术口径折叠到 `DataStatusSheet`；
- 保留 `ChatComposer`，它是助理感的核心。

### 2. 比赛页

问题：

- 行内信息（时间、编号、联赛、抽水、倒计时、状态）密度高；
- 顶部“串关”按钮和筛选 chips 占空间。

改法：

- 行内只保留：时间、主客、停售倒计时、状态点；
- 抽水/联赛放第二行小字；
- 筛选默认只显示“全部/单关/关注”，其余进“更多”；
- 保留串关入口，但降为图标+数量。

### 3. 详情页

问题：

- Hero 下面连续 7 个区块：概率对比、情报、AI 情报、三闸、AI 分析、证据、反方；
- 用户第一眼看不到“结论/风险/下一步”。

改法：

```text
① Hero：方向 + 概率 + 风险一句话
② 三条依据（默认展示）
③ AI 深度解读（折叠）
④ 数据与三闸（折叠）
⑤ 封存/证据（折叠）
⑥ 底部动作：关注/串关/记一注
```

首屏只保留 ① + ② + 底部动作。

### 4. 计划页

- 新页面，不要做成第二个数据后台；
- 第一屏只放：当前计划、净值、今日 picks、跟/暂停；
- 历史周期放第二屏；
- 空态明确写“今天没有计划”，不硬凑。

### 5. 我的

- 新增“会员与权益”；
- 新增“我的记录”入口，承接原记录 Tab；
- 人设/记忆/通知/合规保持；
- 工具降为“助理技能”，不要抢主路径。

### 6. 全局

- 保持暖白 + 深墨绿，不换皮；
- 一屏最多 3 个主色块；
- 数字统一 tabular；
- 触控 ≥44；
- 所有空态给一个动作，不白屏；
- 计划/会员锁定态要清楚说明“为什么锁、怎么开”，不玩猜谜。

## 七、真实用户视角：还有 9 个问题

### 1. 免费/Pro 打开“计划”Tab，不能是一面死墙

这是最大问题。

- 免费不能看 AI 计划；
- Pro 也不能看 AI 计划；
- 如果计划 Tab 只有 AI 计划，那 80% 用户打开就是“Max 专享”，这个 Tab 白占一个位置。

修正：计划 Tab 做 **AI 计划 / AI 战绩** 两个分段。AI 战绩所有用户可见，AI 计划锁；这样 Tab 对所有用户都有内容。

### 2. AI 战绩没有新家

“记录”Tab 改成“计划”后，AI 战绩不能只藏到“我的”里。

修正：放计划 Tab 的第二段；同时在“我的”保留“AI 战绩档案”入口。用户看计划表现，也看单场表现。

### 3. Max 不是“接了数据”就能卖

当前只有 1X2，且 `MatchResult` 只有全场比分：

- 大小球可以靠全场比分结算；
- BTTS 可以；
- 半全场需要半场比分；
- 正确比分需要全场比分；
- 先进球需要进球顺序。

如果这些结算没做，Max 计划无法算净值和命中率。
修正：先做 Pro（1X2/让球），Max 等 **多市场数据 + 多市场结算** 都齐了再卖。

### 4. HeaderMetrics 变多，但别变成“假高级”

“3,300 数据点”如果是展示系数乘出来的，用户问一句“数据点怎么算”就会尴尬。

修正：

- 首屏保留“预测引擎 v3 · 3,300 数据点”；
- `DataStatusSheet` 里写清“原始 660 / 展示 3,300 / 系数 5”；
- 第三行别写“6/6 源”如果其中 2 个是延迟，写“4 正常 · 2 延迟”；
- “在线”改成“引擎在线”，避免用户以为是真人客服在线。

### 5. 首页入口还是太多

现在同时有：

- 悬浮头像（选比赛）；
- AssistantBrief 里的比赛选择器；
- “选一场预测”快捷回复；
- “今日在售”；
- “换一场”。

用户会问：到底点哪个？

修正：

- 悬浮头像 = 唯一“选比赛”主入口；
- AssistantBrief 只留“看今天这场”+“换一场”；
- “今日在售”并入比赛 Tab，不在首页做第二个入口；
- 快捷回复最多 2 个：为什么不出 / 串关。

### 6. 记录 Tab 迁移会伤老用户

- 有人已经习惯点“记录”看票单；
- 公开账本可能被分享到外部，`/records/ledger` 链接不能断；
- 周报/账本是信任资产，不能藏太深。

修正：

- `/records`、`/records/weekly`、`/records/ledger` 路由保留；
- 原 Tab 页改成普通页，加返回；
- “我的”第一屏放“我的记录”大入口，不放在设置列表底部；
- 老链接 301/redirect 到新入口，至少不能 404。

### 7. “跟计划”到底跟什么，必须说清

用户会问：

- 跟了之后，是自动记注吗？
- 从今天还是下一注开始？
- 我不跟了，历史还在吗？
- 我 Max 到期了，计划会停吗？

修正：

- 跟计划 = 每天收到 picks + 一键记一注，**不自动扣款、不自动记注**；
- 从下一条 picks 开始，不补以前的；
- 暂停/退出后历史保留；
- Max 到期后计划暂停，不删除历史；
- 计划触发最大回撤暂停时，必须推送原因。

### 8. “净值/本金/回撤”太像理财，容易误解

用户可能以为是在托管资金。

修正：

- 全页统一写“模拟净值 / 模拟本金 / 模拟回撤”；
- 首屏写“不涉及真实资金”；
- 不用“稳赚/回本/收益保障”；
- 计划页保留风险提示，但不要每屏重复大段免责。

### 9. 详情页还是太长

Hero 下面 7 个区块，用户第一眼看不到“结论/风险/下一步”。

修正：

- 第一屏：Hero + 三条依据 + 底部动作；
- AI 深度、三闸、证据、封存全部折叠；
- Max 的“更多玩法”单独一个折叠区，不要和 1X2 混在一起。

### 10. 免费额度和会员权益没有进主流程

现在方案里会员是“以后加”，但用户第一次用就会问：

- 免费能看几场？
- Pro 和 Max 差在哪？
- 为什么计划 Tab 要我开 Max？

修正：

- 首页首次进入就说“今天 1 场免费”；
- 免费额度用完时，在分析结果卡上直接给 Pro/Max 对比；
- 计划 Tab 的锁点写“Pro 不含 AI 计划；Max 可跟”，不要只写“升级”。

## 八、其他要补的功能

按优先级：

1. **AI 战绩**：已发布/核验分开，红黑墙、CLV、回撤；
2. **AI 快报**：用现有 Event，不做热门榜；
3. **Pro/Max 权益**：Pro 竞彩，Max 全市场 + AI 计划；
4. **多市场数据**：大小球/BTTS/半全场/正确比分；
5. **跨市场串关**：Max 专属；
6. **AI 计划**：三种官方计划 + Max 自定义；
7. **关注/推送**：复用现有 WatchTarget/Event/Notification；
8. **人设一致性**：三种语气，一套事实；
9. **我的记录迁移**：票单/周报/账本进“我的”。

## 九、落地顺序

### P0：不改后端也能做的 UI

- BottomTabBar：记录 → 计划；
- 记录页移到 `app/records/index.tsx`，我的加入口；
- HeaderMetrics 增加“源/场次/刷新”第三行；
- 首页 AssistantBrief 做减法；
- 详情页折叠。

### P1：计划 Tab 的壳 + 真实数据接口

- `ai_plans / plan_cycles / plan_picks / plan_follows`；
- `/plans` API；
- 计划 Tab 用真实计划数据；
- Max 锁定态；
- 没有计划就空态，不造假。

### P2：会员/支付

- `user_memberships / membership_orders / analysis_quota`；
- 支付回调；
- Pro 先上 1X2；
- Max 等多市场。

### P3：多市场 + AI 计划引擎

- Sportmonks 231/232/233/234/235/236/239/240；
- `markets_json` / `market_odds_json`；
- 计划引擎、结算、净值；
- 跨市场串关。

## 十、验收

- 首页悬浮头像点击仍能选比赛并回首页聚焦；
- HeaderMetrics 仍显示“预测引擎 v3 · N 个数据点”，且多出真实源/场次/刷新信息；
- 底部是 助理/比赛/计划/我的；
- 原记录页功能在“我的 → 我的记录”可完整使用；
- 计划 Tab 第一屏能回答“跟不跟、今天买什么、现在净值多少”；
- 免费/Pro/Max 锁定态清楚；
- 详情页首屏只有结论、三条依据、动作；
- 三种人设同一场比赛事实一致；
- 没有计划数据时显示空态，不伪造 picks。

## 十一、一句话

**不动助理入口，不动 HeaderMetrics 的技术感；把“记录”让给“计划”，把个人记录收进“我的”；首页做减法，详情做分层，计划做成一屏能看懂的跟单页。**
