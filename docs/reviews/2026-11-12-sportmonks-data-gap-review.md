# Sportmonks 数据能力与前端缺口审查（2026-11-12）

> 范围：当前 Sportmonks 订阅、现有 `jieqiu-backend` 消费链路、助理/比赛/预测详情/数据状态/后台矩阵。
> 方法：对生产 token 实际请求 6 场欧国联 fixture + 官方 v3 文档核对 + 代码逐层扫描。
> 结论：**Sportmonks 能提供的数据远多于当前 UI 消费；最大缺口不是“没数据”，而是“数据没有落库、没有结构化、没有展示”。**
> 验证级别：L2 实网接口探测 + L1 代码审查；本审查**没有改代码**。

## 1. 实网证据：当前 6 场能拿到什么

以 2026-11-12 的 6 场欧国联为例，当前订阅下实际返回：

| 场次 | 首发 | 阵型 | 教练 | 裁判组 | 伤停 | 天气 | 预测维度 | 赔率行 | 积分榜 | 交锋 |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 周四001 土耳其 vs 比利时 | 22 | 2 | 2 | 4 | 1 | 有 | 28 | 4278 | 16 队 | 6 场 |
| 周四002 亚美尼亚 vs 塞浦路斯 | 22 | 2 | 2 | 4 | 0 | 有 | 29 | 2697 | 16 队 | 1 场 |
| 周四003 阿尔巴尼亚 vs 芬兰 | 22 | 2 | 2 | 4 | 0 | 有 | 29 | 2667 | 16 队 | 1 场 |
| 周四004 黑山 vs 拉脱维亚 | 22 | 2 | 2 | 4 | 1 | 无 | 29 | 2694 | 16 队 | 3 场 |
| 周四005 英格兰 vs 克罗地亚 | 22 | 2 | 2 | 4 | 1 | 有 | 28 | 4191 | 16 队 | 11 场 |
| 周四006 捷克 vs 西班牙 | 22 | 2 | 2 | 4 | 1 | 有 | 28 | 4279 | 16 队 | 6 场 |

补充：

- `lineups` 当前每场 22 人 = 双方各 11 名首发；含球员名、球衣号、位置、`formation_field`。
- `formations` 含双方阵型（如 4-4-2 / 4-3-3）。
- `coaches` 含姓名、常用名、照片、所属球队。
- `referees` 返回 4 条裁判关系（主裁/助理/第四官员/VAR），但只有 `referee_id`，需要二次解析姓名。
- `sidelined` 返回球员 ID、球队 ID、伤停类型 ID；例如 001 的 1 人是 Romelu Lukaku。
- `venue` 含球场名、城市、容量、草皮、图片。
- `weatherReport` 含描述、温度（日/晨/晚/夜）、体感、风速/风向、湿度、云量、气压；004 当前没有返回。
- `predictions` 有 28–29 个维度，不只是 1X2：BTTS、O/U 1.5/2.5/3.5/4.5、上下半场、双重机会、正确比分、半全场、先得分球队、角球 O/U 等。
- `odds` 有 169 个市场、18 个书商；当前代码只消费 Pinnacle 的 1X2。
- `standings` 按 round 返回 16 队，双方都在表内；按 season 返回 54 行。
- `head-to-head` 返回 1–11 场历史交锋；`fixtures/between/{from}/{to}/{team_id}` 可拿球队近期赛程。

`expectedLineups`、`prematchNews`、`postmatchNews`、`xGFixture`、`pressure`、`trends`、`statistics`、`events`、`scores`、`periods` 当前赛前多为空；这些不是“接口不存在”，而是赛前/临近开赛或赛后才会填充，适合做临场/赛后能力。

## 2. 当前代码怎么用 Sportmonks

| 位置 | 现在存/用什么 | 问题 |
|---|---|---|
| `jieqiu-backend/app/models.py:149` `SportmonksMatchData` | fixture_id、probs（1X2 + 正确比分）、odds（仅 Pinnacle 1X2）、bookmaker、captured_at | 没有 lineups、formations、standings、weather、venue、referees、coaches、sidelined、H2H、prediction 多维 |
| `jieqiu-backend/app/modules/sportmonks.py:235` | 只解析 type 237（1X2）和 type 240（正确比分） | 另外 26 个预测维度丢掉 |
| `jieqiu-backend/app/modules/sportmonks.py:252` | 赔率只取 markets:1 + bookmakers:20 的 1X2 | 169 个市场里只用了 1 个，且没有市场时间序列 |
| `jieqiu-backend/app/modules/intel_research.py:34` `_fetch` | `/match-facts` 只取 `per_page=10`；伤停只取数量 | 实际有 25 条 match-facts；伤停只有人数，没有球员名/类型/球队 |
| `jieqiu-backend/app/features/intel/service.py:319` `_facts` | 价/市/模/近况/休息/交锋/首发/伤停/积分榜 | 首发、伤停、积分榜全部走 API-Football 表；Sportmonks 有数据但不会被读取 |
| `jieqiu-backend/app/features/intel/service.py:237` `_coverage` | `lineups_ok`、`standings_ok` 也只看 API-Football | 当前 001 覆盖分 55、`deep_eligible=false`，尽管 Sportmonks 首发/积分榜都在 |
| `jieqiu-backend/app/features/intel/service.py:471` | `if not intl: unknowns.append("国际盘未覆盖")` | Sportmonks 市场已过闸时仍显示“国际盘未覆盖”，文案误导 |
| `jieqiu-backend/app/features/analysis/service.py:54` `_compact` | 只把 focus facts 前 14 条给 LLM | 没有结构化阵容/积分榜/天气/裁判/多市场预测 |
| `jieqiu-backend/app/features/analysis/service.py:169` | `deep_eligible` 才生成 AI 解读 | 当前 6 场因缺 lineups/standings，AI 解读会被 coverage 拦住 |

## 3. 前端 UI 缺口对照

### 3.1 首页 / 助理

| UI | 现在显示 | Sportmonks 可补 | 建议 |
|---|---|---|---|
| `HeaderMetrics` | `markets_monitored=5`、`models_reviewing=7`（`engine.py` 静态配置） | 实际 169 个市场、28–29 个预测维度、Pinnacle/1X2/正确比分模型 | 要么改成“5 个产品盘口（配置）”避免误解，要么动态显示“Sportmonks 覆盖 169 个市场 / 28 个预测维度” |
| `AssistantBrief` | 6 场、1 核验、3 市场参考 | 每场是否有首发、天气、排名、伤停 | 在比赛选项上增加小状态：`首发已公布` / `天气` / `榜位`，但不要挤占主文案 |
| `BriefMatchPicker` | 主客队、时间、核验/参考状态 | 联赛、球场、天气、首发状态、双方排名 | 增加一行 `英超 · 19:30 · 首发已公布`，点击后仍在对话流里出卡 |
| `FocusPanel` | 覆盖分、缺失源、最多 3 条 facts、最多 2 条 unknowns | 阵容、阵型、伤停姓名、积分榜、H2H、天气、裁判 | facts 分组 + 可展开；当前 `facts.slice(0,3)` 把大部分数据藏掉了 |
| 数据状态 Sheet | 阵容/伤停、积分榜来自 API-Football | Sportmonks 已能覆盖 | 增加 `Sportmonks 阵容/积分榜` 独立源，不要只显示“未覆盖” |

当前 `FocusPanel` 的实际表现（001）：
`coverage.score=55`，`missing=['price','lineups','standings']`，facts 只有价/市/模三条，unknowns 是“首发/伤停未接入、伤停未同步、积分榜未同步、国际盘未覆盖”。  
其中 `lineups`、`standings`、伤停姓名本来就可以从 Sportmonks 拿到。

### 3.2 预测卡 / 预测详情

| UI | 现在显示 | 可补 |
|---|---|---|
| `VerdictMessage` | 1X2/让球方向、概率、三关、抽水、封存 | 首发、伤停、天气、裁判、H2H 摘要、多市场预测参考 |
| `ProbabilityCompare` | 竞彩、模型、Sportmonks 市场、第三方 1X2 | 亚盘、O/U 2.5、BTTS、双重机会、正确比分 top 3 |
| `IntelSection` | 战意/阵容/疲劳/状态四个格子；无结构化数据时“未覆盖” | 用 Sportmonks 阵容、积分榜、H2H、近期赛程、天气、裁判填满六维 |
| `AiIntelCard` | headline + points；来源只写 Sportmonks | 分组：阵容/伤停、积分榜/战意、H2H、环境、裁判、市场预测；每条带时间和来源 |
| `MatchAnalysisCard` | 只有 `deep_eligible` 才生成 | 接入阵容/积分榜后 coverage 可到 75 左右，AI 解读才真正可用 |
| `WhyNotScreen` | 三关原因 + 引擎日志 | 显示“缺的是哪类 Sportmonks 数据、下一次同步时间”，而不是只写 pending |

### 3.3 后台 / 运维

- `/admin/api/data` 的 Sportmonks 区块只有 `with_odds`、`with_probs`、`latest`；没有 lineups/standings/weather/referee 覆盖。
- `/admin/api/sportmonks/matrix` 只有 probs/odds/intel headline；没有逐场阵容人数、阵型、积分榜是否命中、天气、裁判。
- `build_pulse` 的 `lineups`、`standings` 计数仍来自 API-Football 表，所以数据页会显示 0/4；接入 Sportmonks 后应改为“Sportmonks 或 API-Football 任一命中”。

## 4. 可补数据目录（按价值排序）

### P0：立刻补，直接改善 AI 情报与覆盖

1. **首发 + 阵型 + 教练**
   - 接口：`fixtures/{id}?include=lineups;formations;coaches`
   - 字段：`lineups[].player_name/team_id/position_id/formation_field/jersey_number`、`formations[].formation/location`、`coaches[].name/common_name`
   - UI：详情页 `LineupCard`；首页 FocusPanel 一条“首发已公布 · 4-4-2 / 4-3-3”。

2. **伤停/停赛姓名**
   - 接口：`fixtures/{id}?include=sidelined` + 对 `player_id`、`type_id` 做缓存解析
   - 当前只显示“1 人受伤”；应显示 `Romelu Lukaku（伤）` 和所属球队。
   - UI：`伤停 1 人 · 比利时 · 卢卡库`，点开看球员位置/预计缺阵。

3. **积分榜/小组形势**
   - 接口：`standings/rounds/{round_id}` 或 `standings/seasons/{season_id}`，`include=participant;form;details`
   - 字段：`position/points/result/form/details`（进失球等）
   - UI：`StandingsCard` 只显示双方所在小组的排名、积分、近 5 场；不要塞整张 16 队表。

4. **H2H + 近期状态**
   - 接口：`fixtures/head-to-head/{home}/{away}`、`fixtures/between/{from}/{to}/{team_id}`
   - 现有 `MatchResult`/football-data 只覆盖部分球队；Sportmonks 对国家队更完整。
   - UI：近 3 次交锋比分 + 双方近 5 场 W/D/L；放在 AI 情报和详情页。

5. **场地/天气/裁判/教练**
   - 接口：`venue`、`weatherReport`、`referees`、`coaches`
   - 裁判需要 `referee_id` 二次查 `/referees/{id}`；天气 004 当前为空，必须允许“无数据”。
   - UI：`MatchConditionsCard`：球场、城市、容量、天气、主裁；不要把这些当预测因子写死。

6. **match-facts 全量**
   - 当前 `per_page=10`，实际 25 条；改为 `per_page=100&include=type`，过滤 `natural_language` 非空，并保留 `category/scope/basis`。
   - UI：AI 情报按“交锋/连胜/先得分/历史比分”分组；不要只取前 10 条。

### P1：把“有数据”变成产品能力

7. **28 维预测**
   - 已返回：BTTS、O/U 1.5/2.5/3.5/4.5、双重机会、正确比分、半全场、先得分、角球 O/U 等。
   - 建议先接 5 个：`BTTS`、`O/U 2.5`、`双重机会`、`正确比分 top 3`、`半全场 top 2`。
   - 文案必须写“Sportmonks 预测参考”，不能写成“本产品模型”或“已核验”，除非它进入模闸并被明确标注。

8. **多市场赔率**
   - 当前只取 Pinnacle 1X2；实际 169 个市场、18 个书商。
   - 建议只存：1X2、亚盘、O/U 2.5、BTTS、双重机会、正确比分；按市场聚合共识，不存全量 4278 行。
   - UI：`MarketBoardCard` 显示“市场共识/离散度/更新时间”；先只做展示，不进入付费计划。

9. **动态 HeaderMetrics / 数据状态**
   - 把“5 盘口 / 7 模型”改成真实口径：
     - `已接 1X2/让球 · Sportmonks 169 市场`
     - 或明确写“5 个产品盘口（配置）”，避免用户以为 5 个就是全部。
   - 数据状态增加 `Sportmonks 阵容`、`Sportmonks 积分榜`、`Sportmonks 环境` 三个源。

### P2：临场/赛后能力

10. **临场**
    - `expectedLineups`（预计首发）、`prematchNews`（赛前新闻）、`inplayOdds`、`pressure`、`trends`、`events`、`statistics`、`ballCoordinates`。
    - 当前多为空；按 T-2h/T-30m 轮询，接口有数据再展示，不预生成假内容。

11. **赛后复盘**
    - `xGFixture`、`statistics`、`events`、`scores/periods`、`postmatchNews`。
    - 用于“赛后复盘”归因：xG、射门、控球、红黄牌、进球时间线。

12. **电视转播**
    - `tvStations` 当前返回 201 条，但需要解析 `tvstation_id` 并按国家过滤；优先级低，除非要做“在哪看”。

## 5. 建议的数据落库方式

不要在 `SportmonksMatchData.probs` 里继续塞所有东西，容易把模型概率和展示情报混在一起。建议：

```text
sportmonks_fixture_intel        # 1:1 match_id
  match_id, fixture_id, payload JSON, captured_at, expires_at
  payload = {
    venue, weather, coaches, referees, formations, lineups, sidelined,
    standings, h2h, recent_form, match_facts, tv_stations
  }

sportmonks_predictions          # 1:N match_id + type_code
  match_id, type_code, type_name, probabilities JSON, captured_at

sportmonks_odds_snapshot         # 只存选定市场
  match_id, market_code, bookmaker, label, price, handicap, captured_at
```

如果不想加三张表，最小改动是给 `SportmonksMatchData` 增加 `details JSON`，先放 P0 数据；但多市场/时间序列仍建议独立表，避免单行 JSON 越来越大。

## 6. 同步与成本控制

- 不要每 30 分钟拉 `odds` 全量：001 单场 4278 行；6 场会非常重。
- 拆分请求：
  - 情报包：`lineups;formations;coaches;referees;sidelined;venue;weatherReport;predictions`，每场一次；
  - 赔率包：只拉 `markets:1` 或指定 market IDs + Pinnacle，继续复用现有过滤；
  - 积分榜：按 round/season 缓存，6 小时或每日；
  - H2H/近期：24 小时缓存；
  - 临场：T-2h 起提高频率。
- 缓存 TTL 建议：首发 30 分钟（临场 10 分钟）、积分榜 6 小时、H2H 24 小时、天气 1 小时、预测 15 分钟、1X2 赔率 5–15 分钟。
- 裁判/球员/球队名称解析做本地缓存，避免每场重复请求。

## 7. 真实性与产品边界

1. **Sportmonks 预测不是本产品模型**：展示时必须标“Sportmonks 预测参考”；只有进入模闸并写入 `model_source=sportmonks` 的场次，才能按现有规则参与 verified/promoted。
2. **多市场不能直接进付费计划**：大小球/BTTS/半全场/正确比分先做情报展示，结算规则、复核门、Max 权限都未完成前，不得写成“已可用”。
3. **阵容会变**：首发公布后仍可能调整；所有阵容事实必须带 `captured_at`，页面写“已公布/预计”，不要写“最终”。
4. **AI 不能补编伤停**：LLM 只能使用结构化 facts；没有球员名/类型时写“未同步”，不能猜。
5. **“国际盘未覆盖”文案要修**：Sportmonks 市况已通过时，unknown 不应再写国际盘未覆盖；应写“The Odds API 未覆盖，Sportmonks 已覆盖”。
6. **HeaderMetrics 不能把配置当事实**：5 盘口/7 模型是配置值，和实际 169 市场/28 预测维度不是一回事。

## 8. 建议实施顺序

### Sprint 1（P0，优先做）

1. `SportmonksMatchData` 增加 `details`（或新表），同步 `lineups;formations;coaches;referees;sidelined;venue;weatherReport`。
2. 解析裁判姓名、伤停球员姓名/类型/球队；缓存 ID 解析。
3. 同步 `standings/rounds/{round_id}` 与 `head-to-head`。
4. `_coverage` 的 lineups/standings 改为“Sportmonks 或 API-Football 任一命中”；`build_pulse` 同步。
5. `focus.intel.facts` 增加阵容、伤停、积分榜、H2H、场地、天气、裁判；`FocusPanel` 分组/展开。
6. `AiIntelCard` / `IntelSection` 接结构化六维；`analysis._compact` 加入这些 facts，bump `PROMPT_VER`。
7. 修复“国际盘未覆盖”unknown 文案。

### Sprint 2（P1）

8. 解析 28 维预测，先展示 5 个高价值维度；明确“Sportmonks 预测参考”。
9. 多市场赔率只存选定市场，做 `MarketBoardCard` + 市场共识/离散。
10. HeaderMetrics 改为真实数据或明确“配置口径”；DataStatus 增加 Sportmonks 阵容/积分榜源。

### Sprint 3（P2）

11. `expectedLineups`、`prematchNews` 按临近开赛轮询。
12. 赛后 `xGFixture/statistics/events/scores` 接入复盘。
13. TV stations 按地区过滤，低优先级。

## 9. 结论

- **可复用结论：REUSE 现有 Sportmonks 订阅。** 不需要新增数据供应商。
- **最高性价比不是再接新 API，而是把已经返回的 lineups、standings、sidelined、H2H、venue、weather、referees、coaches、28 维 predictions 落库并展示。**
- 当前 6 场已经具备把覆盖率从 55 提升到约 75、解锁 `deep_eligible` 和 AI 单场解读的条件；这也是对用户感知提升最大的一步。
- 多市场赔率/预测是第二步，先展示、再复核、最后才考虑进入计划或付费区。

## 10. 审查边界

- 本审查未修改运行代码、未新增表、未改 API。
- `expectedLineups/prematchNews/xGFixture/pressure/trends/statistics/events` 在赛前为空，不能按“已有数据”宣传。
- Sportmonks 预测/赔率的最终商用边界、结算规则、Max 权益展示仍需产品/合规确认。
