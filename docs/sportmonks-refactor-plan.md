# 球多多 × Sportmonks 重构方案（数据源收编 + Prediction Model 主力）

> 前提约束：**数据源收敛为两个** —— ① 自建竞彩采集器（SP/让球/单关/销售窗口，唯一竞彩口径事实源）；② Sportmonks Football API v3（国际数据 + 预测模型）。
> 依据：`Sportmonks调研报告.md`（预测专项）+ docs.sportmonks.com/v3 全量文档（llms-full.txt 本地留存）+ 当前代码审查（dc_model/verdict/intl_odds/api_football/understat/results 同步链）。
> 日期：2026-11-11

## 0. 一句话结论

**把 Sportmonks Prediction Model 作为"模型闸"的第二引擎（非五大联赛的唯一引擎），把 Sportmonks 赔率（Pinnacle）作为"市场闸"的唯一国际基准，把它的伤停/阵容/积分榜作为情报事实包，赛果结算也切到它——然后下线 The Odds API、API-Football、football-data 三条链路；Understat 只保留给 DC 模型训练回填（免费且只有五大联赛有 xG）。**

---

## 1. 为什么这样接：现状诊断

当前预测链路的实际瓶颈（来自代码与生产数据）：

| 环节 | 现状 | 问题 |
|---|---|---|
| 模型闸 | Dixon-Coles（Understat xG 训练，五大联赛 10,707 场） | **只覆盖五大联赛球队**（`min_matches=3`），日职/英锦标赛/韩职等全部 `model_runs=0`、模型闸 pending → 无法发布 |
| 市场闸 | The Odds API（免费 500 credit/月，target-only） | EFL Trophy 等无 sport key（404），覆盖缺口；credit 是长期天花板 |
| 情报层 | API-Football 免费 100 次/天 | 配额小，lineups/injuries 经常拿不到 |
| 结算 | football-data（免费） | 免费源覆盖不稳，低级别联赛缺 |
| xG | Understat（免费） | 五大联赛 only，且是抓取（有被反爬风险） |

Sportmonks 一次收编解决全部四个问题：

- **Predictions Model 覆盖 1,350+ 联赛**（36 种市场，赛前 21 天可用，逐日刷新）→ 补齐模型闸的联赛缺口；
- **赔率 feed**（50+ 庄家、150+ 市场，赛后历史回溯到 2018）→ 市场闸换 Pinnacle 基准；
- **lineups / sidelined（伤停）/ standings / statistics / h2h** → 情报层一次性配齐，无免费配额焦虑；
- **fixtures 赛果** → 结算替代 football-data。

## 2. 数据采购决策（先定钱，再定架构）

| 采购项 | 决策 | 理由 |
|---|---|---|
| 基础套餐 | **Growth €99/月**（任选 30 联赛） | 竞彩近两月 38 个赛事、860 场的分布（见 `jczq_leagues_2m.json`），5/120 档都不合适 |
| Predictions | **Odds & Predictions 捆绑 €15/月**（省 20%） | 比单买 Basic €23 便宜；下单前邮件客服确认捆绑内是 Basic 还是 Advanced |
| Advanced（滚球） | **暂不买** | 球多多是赛前产品；滚球只有 1X2 一个市场且按分钟烧配额。等做"实时胜率曲线"功能再升 |
| xG Basic | **暂不买**（€19+） | 赛后 xG 对赛前预测无用；DC 训练用 Understat 免费源；低级别杯赛大概率没 xG |
| Premium Odds / Premium Expected Lineups / Livescores | 不买 | 赛前产品用不上；普通 lineups include 够用 |
| 年付 | 验证跑通 1-2 个月后再转年付（-20%） | 先月付 |

**月成本：€114（≈ ¥880）。** 30 个联赛槽位名单按 `docs` 里 24 固定 + 6 轮换执行（见前一轮"会员选联赛"结论）。

## 3. Sportmonks 数据怎么用（按预测价值排序）

| 数据 | 端点/字段 | 用在哪 | 对准确率的价值 |
|---|---|---|---|
| **1X2 概率**（type 237） | `predictions/probabilities/fixtures/{id}` | 模型闸第二引擎；详情页概率对比 | ★★★ 核心补齐：非五大联赛从"无模型"变"有模型" |
| **Value Bets**（type 33） | `predictions/valuebets` | review 层参考信号（不直接发布） | ★★★ 模型×庄家赔率的现成价值筛选 |
| **联赛可预测性**（type 243） | `predictions/predictability/leagues/{id}` | 模型权重 + UI 诚实标签 | ★★★ `high/medium/poor` 直接决定"这场信不信模型" |
| **赛前赔率全庄家** | `odds/fixtures/{id}`（按 bookmaker/market 过滤） | 市场闸：Pinnacle 去水基准 + 全庄离散 | ★★★ 收盘最强基准，替代 The Odds API |
| **伤停/停赛**（sidelined） | fixture include `sidelined` | intel_items → AI 解读事实包 | ★★ 核心球员缺阵是赛前最大信息增量 |
| **阵容**（confirmed + predicted lineups） | fixture include `lineups` | 详情页情报卡；开赛前刷新 | ★★ 预测首发（赛前）→ 确认阵容（赛前 20-40 分钟） |
| **积分榜/排名** | standings by season（含主客场拆分） | 特征 + 解读事实（主客场成绩差） | ★★ 主场龙/客场虫类结构性信号 |
| **赛季统计** | statistics by participant | 解读事实（进失球、连胜连败、零封率） | ★★ 与 xG 互补的状态特征 |
| **历史交锋** | fixtures by head-to-head | 解读事实包 | ★ 心理/风格因素，权重低 |
| **赛果** | fixtures（state/scores） | 结算（替代 football-data） | 结算可靠性，不直接提升预测 |
| **赛程** | fixtures by date-range | 与采集器对齐（`jc_source_links`） | 基础设施 |
| 比分矩阵（240）/BTTS/大小球/双 chance/HT-FT | 同预测端点 | 暂存不展示（未来玩法扩展） | ★ 预留 |
| zh 翻译（Beta） | `locale=zh` | 辅助展示 | ★ 自建 type_id/state 中文映射表，不依赖 Beta |
| xG / 滚球 / Pressure Index | 加购 | **不接** | — |

**明确不用的**：Pressure Index（比赛动能，滚球语境）、Transfer rumours（噪声）、News/TV（无关）。

## 4. 预测链路重构（核心）

### 4.1 模型闸：从"单 DC"到"双引擎融合"

```text
                 ┌─ DC 模型（Understat xG，五大联赛有数据时）─┐
竞彩 SP 隐含概率 ─┤                                            ├─ 融合概率 p_model ─ 模型闸 vs 竞彩 SP
                 └─ SM Prediction 1X2（1350+ 联赛）──────────┘
                         权重 w(sm) = f(联赛 predictability, 自测 RPS)
```

- **五大联赛**：`p = 0.5·DC + 0.5·SM` 起步（权重由第 4.3 节验证管线产出后动态调）；
- **非五大**：`p = SM`（DC 没有数据，诚实降级为单引擎，证据层标注 `model_source=sportmonks`）；
- **联赛级开关**：predictability `fulltime_result=poor` 的联赛，模型闸只做"不反对"检查（SM 概率与 SP 隐含偏差 > 阈值时不否决、也不加持），UI 打"该联赛模型可信度低"标签；
- `verdict.gates.model` 证据扩展：`{"model_source": "dc"|"sportmonks"|"blend", "sm_prob": {...}, "dc_prob": {...}, "blend_weights": {...}, "league_predictability": "high"}`。

### 4.2 市场闸：Pinnacle 基准 + 全庄离散

- 现有 `intl_odds` 表保留，`source` 增加取值 `sportmonks:pinnacle` / `sportmonks:median`；
- Pinnacle 去水隐含概率作为"市场基准盘"参与模型闸对照（收盘基准语义）；
- 离散度计算改为：竞彩去水 vs Pinnacle vs 全庄中位数，三向最大离散 < 5pp（阈值沿用现有 settings）；
- The Odds API 代码路径保留但默认关闭（`JQ_ODDS_API_ENABLED=false`），试用期内并行跑一周做数据对照后再删。

### 4.3 第三方模型验证管线（上线前必做，报告 §7 的落地）

黑盒模型不验证就不配上权重：

1. **每日快照冻结**：`sm_prediction_snapshots` 表（fixture_id、type_id、probabilities、captured_at），每天对全部在售竞彩场次拉一次预测——概率是逐日刷新的，冻结快照防"赛后回填"；
2. **赛后结算对比**：SM fixtures 赛果落库后，计算每场 **RPS / log loss**（1X2）；
3. **按联赛×周滚动聚合**进现有 `model_evals` 表：SM vs DC vs Pinnacle 收盘三列对照；
4. **权重决策**：某联赛 SM 连续 4 周 RPS 显著差于 Pinnacle 隐含 → `w(sm)` 降权/该联赛模型闸只做不反对检查；
5. 期间**绝不随机切分**，按时间切。

### 4.4 Value Bet 的位置

- `predictions/valuebets` 每日同步到 `sm_valuebets`（fixture、market、prob、bookmaker_odds、value）；
- **不直接进发布链**——它只是"第三方模型认为有价值"的参考。进入 `review_runs`（L1 规则层）作为参考字段：`value_bet: {"present": true, "edge": 0.07}`，人设文案可以引用，但三闸语义不变；
- 合规红线不变：文案只写"预测方向/预测概率/置信度"，不得写"必中/稳赚"。

### 4.5 情报层（intel_items 扩容）

现有 `match_coverage` 六源（price/market/model/lineups/standings/schedule）从 API-Football 切到 Sportmonks：

| 覆盖源 | 新数据源 | 刷新时机 |
|---|---|---|
| lineups | SM fixture include lineups（confirmed）+ predicted lineups | 开赛前 2h / 30min 两次 |
| 伤停 | SM sidelined include | 每日 + 开赛前 2h |
| standings | SM standings（主客场拆分） | 每日 |
| schedule | 采集器（竞彩口径，唯一权威） | 不变 |
| price | 采集器 SP | 不变 |
| market | SM odds | 每日 + 开赛前 2h |

`FocusResponse.interpretation` / `match_analysis` 事实包自动获得伤停、阵容、排名、交锋事实——这些直接提升 AI 解读质量（match_analysis 的 `_compact` 事实包加入 SM 预测概率与伤停清单）。

### 4.6 结算切换

`results_sync`（football-data）替换为 SM fixtures 赛果：对齐走 `jc_source_links`，`jc_results` 表（见 `docs/jc-data-model.md`）承接。Understat 结果代理同步一并下线。

## 5. 新增/改造模块清单（后端）

```text
app/modules/sportmonks.py            # 新增：HTTP client（token/重试/限速/usage 记账）
app/modules/sm_sync.py               # 新增：fixtures/predictions/odds/lineups/sidelined/standings/results 七个同步器
app/modules/sm_predictions.py        # 新增：概率解析（type_id 拆包）、快照冻结、RPS/logloss 计算
app/modules/verdict.py               # 改：模型闸双引擎融合 + 证据扩展
app/modules/gates.py                 # 改：model_gate 接受 blended prob + model_source
app/modules/intl_odds.py             # 改：SM Pinnacle/中位数源接入（The Odds API 路径保留可关）
app/features/intel/service.py        # 改：coverage 六源切换到 SM；事实包扩容
app/features/analysis/service.py     # 改：match_analysis 事实包加 SM 预测/伤停/交锋
app/modules/results_sync.py          # 改：结算切 SM fixtures（football-data 下线）
app/models.py                        # 新表：sm_fixtures, sm_prediction_snapshots, sm_valuebets, sm_usage（复用 jc_source_links, model_evals）
migrations/20261111_17_sm_*.py       # Alembic
```

配置新增（`config.py` + 后台接入中心可改）：`SPORTMONKS_TOKEN`（Fernet 入库，同 llm_profiles 模式）、`SPORTMONKS_BOOKMAKER_PINNACLE_ID`（试用时从 bookmakers 端点确认后固化）、`SPORTMONKS_PLAN`、`SM_SYNC_HORIZON_DAYS=21`。

**配额预算**（Growth 2,500 次/实体/小时，实际消耗极低）：每日同步 ≈ 在售场次 N×4 类请求 + 每周 7 次联赛级 predictability + 赛果 N 次，日均 < 500 次。`sm_usage` 表照抄 `api_football_usage` 的按日计数模式。

## 6. 移动端（UI/功能）改造

| 位置 | 改动 |
|---|---|
| 详情页（verdict/[id]） | 新增**「概率对比」卡**：竞彩 SP 隐含 vs 融合模型 vs 市场基准（Pinnacle 去水），三向条形对比；显示"数据源：竞彩官方 + Sportmonks" |
| 详情页 | 联赛可预测性徽章：`高/中/低`（来自 type 243），low 时显示"该联赛模型参考价值有限"——把诚实度做成 UI |
| 详情页情报区 | 伤停清单卡（核心球员红点）、阵容卡（开赛前自动刷新为确认阵容）、交锋摘要（近 5 次） |
| FocusResponse | `coverage.sources` 从 api-football 键换 sportmonks 键；`sm_prediction` 字段进 focus payload |
| verdict 卡片（Home） | 证据层带 `model_source` 徽章（融合/SM/DC）；文案不变（仍走人设渲染） |
| `/chat` | `match_analysis` 事实包自动包含 SM 概率/伤停 → 回答"为什么看好 X"时能引伤停事实 |
| 结算/账本 | 无感切换（SM 赛果），公开账本不受影响 |

原则：**前端契约尽量不动**——`FocusResponse`/verdict payload 是追加字段，不破坏现有 OpenAPI 契约；OpenAPI 快照更新后 `api-client` 重新生成。

## 7. 管理后台改造

| 页面 | 改动 |
|---|---|
| 接入中心 | **API-Football、The Odds API 卡片下线**；新增「Sportmonks」大卡：token/套餐/配额用量/七条同步器状态/最近错误；联赛槽位选择器（30 个联赛 ↔ jc_leagues 映射状态，未映射标红） |
| 新增「模型对照」页 | 按联赛列表：SM RPS / DC RPS / Pinnacle 隐含 RPS、predictability 评级、`w(sm)` 当前权重、样本数；提供"权重方案"编辑（operator 权限），改动进 admin_audit |
| 工作台 | 阶段「市场数据」「模型」的证据源换成 Sportmonks；数据源健康卡显示 sm_usage 配额水位 |
| 调用用量 | 加 SM 每日/每小时请求曲线 |
| 审计 | 权重变更、联赛槽位变更、token 变更全部进 admin_audit |

## 8. 实施排期（预计 2 周）

| 阶段 | 内容 | 产出/验收 |
|---|---|---|
| **P0 试用验证**（1-2 天） | 开 14 天试用；跑验证脚本：30 联赛预测覆盖（predictable 命中率）、Pinnacle 盘存在性、243 评级粒度、zh 覆盖率、€15 捆绑包档位（邮件客服） | 覆盖率报告；决定 Growth 30 槽最终名单 |
| **P1 通道搭建**（2-3 天） | sportmonks.py + sm_sync（fixtures/odds/results）+ jc_source_links 对齐 + sm_usage | 竞彩在售场次 100% 有 SM fixture 映射；市场闸双源并行 |
| **P2 预测接入**（3-4 天） | sm_predictions 快照冻结 + 融合模型闸 + 验证管线 + 值预测参考 | 非五大联赛模型闸从 pending 变有输出；RPS 管线出第一周报告 |
| **P3 情报与 UI**（3 天） | sidelined/lineups/standings 同步 + 详情页三卡 + 概率对比 + 后台模型对照页 | 详情页可见伤停/阵容/概率对比 |
| **P4 收编清理**（2 天） | 关闭 The Odds API/API-Football 调用路径（代码保留 30 天后删）；结算切 SM；文档更新 | 数据源只剩采集器 + Sportmonks |
| **P5 调优**（持续） | 权重按周报调整；predictability poor 联赛降级；30 天后转年付省 20% | 每周模型周报 |

**回滚**：每阶段独立可回滚——P1 后市场闸可切回 The Odds API（配置开关）；P2 后 `SM_WEIGHT=0` 即回到纯 DC 行为；无 schema 破坏性变更（全部新表）。

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| SM 模型黑盒、部分联赛质量差 | 验证管线 + predictability 门槛 + 权重动态化；poor 联赛模型闸降级为"不反对" |
| 目标联赛不在预测覆盖（1,350+/2,200+） | P0 阶段逐联赛验证，覆盖缺口写入联赛槽位决策 |
| zh 翻译 Beta 不全 | 自建 type_id/state/队名映射（`jc_teams.name_cn` 已有）；UI 中英混排设计 |
| 配额超限 | sm_usage 记账 + 2500/entity/hr 远超实际用量；分页 per_page=50 |
| €15 捆绑包内含 Basic 还是 Advanced 不明 | 下单前邮件客服确认（报告 §8 行动清单） |
| 依赖第三方 API 可用性 | 采集器 SP 是主键事实源，SM 全挂时链路降级为"只有价闸"——不阻塞发布流程，只是市场/模型闸 pending |
| 合规 | 第三方模型概率展示必须带"参考"字样与数据源标注；发布仍走 L1-L5 与封存链 |

## 10. 和 jc-data-model 的关系

本方案的表结构遵循 `docs/jc-data-model.md`：SM 是通过 `jc_source_links` 挂接的增强源，`match_id`（体彩官方）仍是唯一根主键；`sm_*` 表全部带 `source/source_ref/captured_at/payload_hash`；预测快照带 `captured_at` 冻结语义。
