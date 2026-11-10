# 球多多 × Sportmonks 重构方案 v2（数据源收编 + Prediction Model 主力）

> 前提约束：**数据源收敛为两个** —— ① 自建竞彩采集器（SP/让球/单关/销售窗口，唯一竞彩口径事实源）；② Sportmonks Football API v3（国际数据 + 预测模型）。
> 依据：`Sportmonks调研报告.md` + docs.sportmonks.com/v3 全量文档 + 当前代码审查 + **DeepSeek 独立评审 12 条（已全部采纳，见 §11 与 [sm_deepseek_review.md](./sm_deepseek_review.md)）**。
> v2 变更：预算上限修正、市场闸判据修正、验证管线改影子模式、结算双源对账、排期改四门制、合规与授权缺口补齐。
> 日期：2026-11-11

## 0. 一句话结论

**把 Sportmonks Prediction Model 作为"模型闸"的第二引擎（非五大联赛的唯一引擎），Pinnacle 赔率作为"市场闸"的国际基准，伤停/阵容/积分榜做情报事实包，赛果结算先双源对账再切换——全部切换都以"合同确认 + 覆盖验证 + 影子运行"三门为准入，然后才下线 The Odds API、API-Football、football-data；Understat 只保留给 DC 训练回填。**

---

## 1. 为什么这样接：现状诊断

| 环节 | 现状 | 问题 |
|---|---|---|
| 模型闸 | Dixon-Coles（Understat xG 训练，五大联赛） | **只覆盖五大联赛球队**，日职/英锦标赛等全部模型 pending → 无法发布 |
| 市场闸 | The Odds API（免费 500 credit/月） | EFL Trophy 等无 sport key；credit 是天花板 |
| 情报层 | API-Football 免费 100 次/天 | 配额小，lineups/injuries 经常拿不到 |
| 结算 | football-data（免费） | 覆盖不稳，低级别联赛缺 |
| xG | Understat（免费抓取） | 五大 only，有反爬风险 |

Sportmonks 对应解决：Predictions Model 覆盖 1,350+ 联赛；赔率 feed 50+ 庄家；lineups/sidelined/standings/h2h 情报一次配齐；fixtures 赛果结算。

## 2. 数据采购决策（v2：预算给上限，合同给门）

| 采购项 | 决策 | 说明 |
|---|---|---|
| 基础套餐 | Growth €99/月（任选 30 联赛），先月付 | 30 槽名单见 §2.1 |
| Predictions | 优先 Odds & Predictions 捆绑 €15/月 | **书面客服确认四件事后才锁定**：①捆绑内含 Predictions Basic 还是 Advanced；②Odds 是标准 feed 完整档还是阉割档；③是否含 Pinnacle 及其历史；④**C 端展示/再分发许可** |
| 预算上限 | **按 €99 + €23（Basic）+ €14（Odds 最低档）= €136/月 做预算上限** | €15 捆绑是官方"Save 20%"标注（€24→€15），实际折扣约 37%，数字存疑；确认前按最坏情况做预算，不把 €114 写进任何承诺 |
| Advanced 滚球 | 暂不买 | 赛前产品；只有 1X2 一个市场且按分钟烧配额 |
| xG Basic | 暂不买 | 赛后 xG 对赛前无用；DC 用 Understat |
| Premium Odds / Premium Expected Lineups / Livescores | 不买 | 赛前产品用不上 |
| 年付 | 四门全过后转年付（-20%） | — |

### 2.1 30 槽名单与覆盖缺口降级策略

- 名单：24 固定 + 6 轮换（前一轮"会员选联赛"结论），按近两月 860 场/38 赛事分布校准；
- **38 赛事 > 30 槽是事实**：亚运类一次性赛事、沙特联、亚冠联2、单场杯赛（巴西杯/荷杯）天然无槽。P0 产出**竞彩场次加权覆盖表**：每个赛事近 90 天场次 × 是否入槽 × SM 预测覆盖（predictable 命中率）；
- **降级规则（写进验收，不隐瞒）**：无 SM 覆盖的比赛 = 维持现状（市场/模型闸 pending，不发布预测，只展示 SP 与分析），**不能因为接了 SM 就默认全部竞彩场次都有模型**；
- 杯赛是否占槽、是否按赛季计费：P0 问客服确认。

## 3. Sportmonks 数据怎么用（按预测价值排序）

| 数据 | 端点/字段 | 用在哪 | 价值 | 状态 |
|---|---|---|---|---|
| 1X2 概率（237） | predictions/probabilities/fixtures/{id} | 模型闸第二引擎 | ★★★ | 受 predictable 过滤，非每场都有 |
| Value Bets（33） | predictions/valuebets | review 层参考（禁"价值/edge"措辞外露） | ★★★ | 模板合规见 §9 |
| 联赛可预测性（243） | predictions/predictability/leagues/{id} | 权重参考 + UI 标签 | ★★★ | **定性**；`unchanged` 单独按未知处理，不映射为权重 |
| 赛前赔率全庄家 | odds/fixtures/{id}（bookmaker/market 过滤） | 市场闸 Pinnacle 基准 | ★★★ | Pinnacle id/含盖许可 P0 确认 |
| 伤停（sidelined） | fixture include | intel_items | ★★★ | — |
| 阵容 lineups | fixture include（confirmed） | 情报层 only（见 §4.5 时序） | ★★ | predicted lineups 是否含基础档未验证，不进验收 |
| 积分榜（主客拆分） | standings | 特征 + 事实 | ★★ | — |
| 赛季统计 / h2h | statistics / head-to-head | 事实包 | ★★ | — |
| 赛果 | fixtures state/scores | 结算（先对账） | 基础设施 | 状态机见 §4.6 |
| zh 翻译 | locale=zh（Beta） | 辅助 | ★ | 自建映射为主 |
| xG / 滚球 / Pressure / Premium 系列 | 加购 | 不接 | — | — |

## 4. 预测链路重构（v2 核心修订）

### 4.1 模型闸：双引擎，但**影子起步、权重从数据里长出来**

- **五大联赛**：起步 `w(sm)=0`（纯 DC 维持现状），SM 概率只记录进 `model_evals` 对比表；
- **非五大联赛**：起步 SM 单引擎（DC 无数据，`model_source=sportmonks`）——这是唯一一开始就启用的部分，且每联赛先查 predictable 命中率；
- **融合（DC ⊕ SM）不预设 0.5/0.5**：等影子期 RPS 数据（含置信区间）出来后按联赛定权重；样本不足的联赛不开融合；
- **独立性检查（防双重计数）**：SM 预测大概率吸收了赔率信息，与 Pinnacle 基准相关。影子期加做两项检验：①SM 概率 vs Pinnacle 去水隐含的相关性；②SM 对 Pinnacle 的**条件信息增量**（在已知 Pinnacle 概率的条件下，SM 是否还提升 RPS）。无增量就不融合，模型闸只认一个；
- verdict.gates.model 证据扩展：`{"model_source", "sm_prob", "dc_prob", "blend_weights", "league_predictability", "sm_predictable": bool}`。

### 4.2 市场闸：判据修正（v2）

- **主判据（唯一否决判据）**：`竞彩去水隐含 vs Pinnacle 去水隐含` 逐结果偏差 < 5pp（沿用现有阈值语义：竞彩对国际基准的偏离）；
- **辅助展示（不进同一 max）**：全庄离散改用 **IQR / 标准差 + 庄家数**，作为信息展示和人工复核提示，不参与自动否决——Pinnacle 与中位数高度相关，三向取 max 会系统性放大误杀；
- **双源策略**：The Odds API 链路**保留且默认开启**，与 SM 并行对照 ≥ 2 周、且 §2 四项书面确认到手后，才配置切换默认源；切换后旧链路保留 30 天再删代码。

### 4.3 验证管线：影子模式起步（v2，修复"4 周样本 vs 14 天试用"矛盾）

1. **P0 先问客服：历史 predictions 是否可回溯**（文档只承诺赛前 21 天逐日刷新，未承诺历史回溯）。可回溯 → 直接拉历史做回测；不可回溯 → 只能前瞻积累；
2. **影子模式**：`sm_prediction_snapshots` 每日冻结在售竞彩场次的预测（fixture、type_id、probabilities、captured_at），模型闸行为不变，只记录对比；
3. 赛果落库后算每场 **RPS / log loss**，按**联赛×市场**聚合进 `model_evals`：SM / DC / Pinnacle 三列；
4. **启用条件按统计而非固定时长**：某联赛 SM 样本 ≥ 30 场且 RPS 的 bootstrap 置信区间不差于 Pinnacle 隐含 → 该联赛 `w(sm)>0`；样本不够就继续影子；
5. 时间序列切分，绝不随机切分；快照表是防回填的关键，永远先冻结再对账。

### 4.4 Value Bet 的位置

- 同步进 `sm_valuebets`；只进 `review_runs` L1 作参考字段；
- **L1 模板硬约束：禁止"价值/edge/庄家优势/收益率"类措辞**，只允许"模型概率/方向/置信度"；UI 明示"第三方参考，非投注建议"。

### 4.5 情报层 + 封存时序（v2 修订）

| 覆盖源 | 新数据源 | 刷新时机 |
|---|---|---|
| lineups | SM confirmed lineups | 开赛前 2h 拉一次；T-30min 第二次**只进情报层** |
| sidelined | SM sidelined | 每日 + 开赛前 2h |
| standings | SM standings（主客拆分） | 每日 |
| schedule / price | 采集器（唯一权威） | 不变 |
| market | SM odds（Pinnacle + 中位数） | 每日 + 开赛前 2h |

**封存纪律**：verdict 一经封存，后到的情报（如 T-30min 确认阵容）**不得修改已封存证据**；若需要用新情报重算，走 `verdict_revisions` 新版本 + 重新封存 + UI 标注版本。predicted lineups 未确认能力前不进任何验收标准。

### 4.6 结算：双源对账 ≥ 4 周后才切主（v2）

- 定义**比赛状态机**：scheduled → live → finished（90 分钟口径）/ postponed / cancelled / abandoned；SM state 与竞彩停售口径的差异逐个映射（加时/点球不算 90 分钟结果）；
- **阶段一（≥4 周）**：SM fixtures 赛果只读比对 football-data，逐场记录差异（含比分、状态、开赛时间），差异告警进工作台；
- **阶段二**：连续 4 周无未解释差异 → SM 切主，football-data 转 fallback；
- 结算是资金/公信力链路，任何对不上都要人审，不允许静默取一方。

## 5. 新增/改造模块清单（后端）

```text
app/modules/sportmonks.py        # HTTP client：token/重试/429 退避/限速/sm_usage 记账/硬熔断
app/modules/sm_sync.py           # 七个同步器，全部幂等（唯一键 + ON CONFLICT）+ 失败死信表
app/modules/sm_predictions.py    # type_id 拆包、快照冻结、RPS/logloss、bootstrap 置信区间
app/modules/verdict.py           # 模型闸双引擎 + 影子记录 + 证据扩展
app/modules/gates.py             # model_gate(blended, model_source)；market_gate 改主判据+辅助
app/modules/intl_odds.py         # SM Pinnacle/中位数源；The Odds API 保留可切
app/features/intel/service.py    # coverage 六源切 SM；事实包扩容
app/features/analysis/service.py # match_analysis 事实包加 SM 预测/伤停/交锋
app/modules/results_sync.py      # SM 赛果只读比对（阶段一）
app/models.py + migrations       # 新表 sm_fixtures/sm_prediction_snapshots/sm_valuebets/sm_usage/sm_dead_letter
```

**配额纪律**（Growth 2,500/entity/h）：赔率**只拉 Pinnacle + 竞彩对应市场**（bookmaker_id + market_id 过滤，杜绝全庄全市场分页暴涨）；预测按 fixture 单拉；`sm_usage` 按端点×实体记账 + 日/时熔断阈值 + 429 指数退避 + 死信队列。缓存节奏 T-2h / T-30m 两档。

配置：`SPORTMONKS_TOKEN`（Fernet 入库）、`SPORTMONKS_BOOKMAKER_PINNACLE_ID`（P0 从 bookmakers 端点核实后固化）、`SPORTMONKS_PLAN`、`SM_MARKET_SOURCE=the_odds_api|sportmonks`（默认 the_odds_api，四门过后切）、`SM_SHADOW=true|false`。

## 6. 移动端改造

| 位置 | 改动 |
|---|---|
| 详情页 | 「概率对比」卡（SP 隐含 vs 模型 vs Pinnacle 基准）；联赛可预测性徽章（高/中/低/未知）；`unchanged` 与无预测场次显示"第三方模型暂无可信预测"，**不承诺"有模型"** |
| 详情页情报区 | 伤停卡、阵容卡（confirmed；赛前仅情报展示，不改封存证据）、交锋摘要 |
| verdict 卡片 | `model_source` 徽章（融合/SM/DC）；数据源标注"竞彩官方 + Sportmonks" |
| 全局 | 第三方内容统一脚注："数据来源：Sportmonks，仅供参考，非投注建议" |
| /chat | match_analysis 事实包自动含 SM 概率/伤停（如有） |

原则：FocusResponse/verdict 契约只追加字段；OpenAPI 快照更新后重新生成 client。

## 7. 管理后台改造

| 页面 | 改动 |
|---|---|
| 接入中心 | API-Football、The Odds API 卡片改为"对照源"状态；新增 Sportmonks 大卡（token/套餐/配额水位/七同步器状态/死信队列深度） |
| 新增「模型对照」页 | 联赛×市场：SM RPS（含 CI）/ DC RPS / Pinnacle 隐含 RPS、predictability、当前 `w(sm)`、样本量、影子/启用状态；权重编辑走 admin_audit |
| 工作台 | 阶段证据源切 SM；结算对账差异面板（阶段一核心） |
| 审计 | 权重/槽位/token/数据源切换全部入 admin_audit |

## 8. 实施排期：四门制（v2，每门有退出条件）

| 门 | 内容 | 进入条件 | 退出条件（准出） |
|---|---|---|---|
| **门1 合同与覆盖**（2-3 天） | 试用 + 验证脚本 + 客服书面确认（捆绑档位/Pinnacle/再分发许可/历史预测回溯/杯赛占槽） | 开通试用 | 四项确认到手 + 加权覆盖表产出 |
| **门2 影子同步**（3-4 天） | sportmonks.py + sm_sync（fixtures/odds/results/predictions）+ jc_source_links 对齐 + 快照冻结 + usage/死信 | 门1 过 | 在售场次映射率 ≥95%；快照连续 3 天无缺口；配额 < 预算 30% |
| **门3 只读展示**（3 天） | 详情页概率对比/情报卡/后台模型对照页；全部只读，不影响任何 gate | 门2 过 | UI 验收；数据一致性抽查通过 |
| **门4 影响 gate**（3-4 天 + 影子期） | 市场闸切 SM（主判据修订版）；非五大模型闸启用 SM；融合按 §4.3 条件逐步开 | 门3 过 + 影子 RPS 报告 | 每个联赛独立启用；回滚开关验证 |

门4 之后才谈结算切主（§4.6，另计 4 周对账）与旧链路删除。**2 周内只承诺到门3；门4 由影子数据决定节奏，不赶工。**

## 9. 风险与对策（v2 补强）

| 风险 | 对策 |
|---|---|
| SM 预测与赔率同源（双重计数→三闸虚假一致） | §4.1 独立性检验；无条件增量不融合 |
| 覆盖缺口（30 槽 < 38 赛事；predictable 非全量） | §2.1 加权覆盖表 + 显式降级规则；UI 不承诺全覆盖 |
| 历史预测不可回溯 | 影子模式前瞻积累；统计门而非时间门 |
| Pinnacle/再分发授权不明 | 门1 书面确认；确认前双源默认 The Odds API |
| 结算事故 | §4.6 状态机 + 4 周对账 + 差异人审 |
| 封存后证据变化 | §4.5 封存纪律：revision + 重封存 |
| 措辞合规 | L1 模板禁"价值/edge"；UI"非投注建议"脚注 |
| zh 翻译 Beta | 自建映射；中英混排 |
| 配额 | 端点记账 + 熔断 + 市场过滤拉取 |
| 单人带宽 | 四门制；每门可独立暂停，不阻塞现有生产链 |

## 10. 与 jc-data-model 的关系

不变：`match_id`（体彩官方）是唯一根主键；SM 通过 `jc_source_links` 挂接；`sm_*` 表全部带 `source/source_ref/captured_at/payload_hash`；预测快照冻结语义。

## 11. DeepSeek 独立评审采纳清单（2026-11-11，12/12 采纳）

| # | 评审要点（P0×6/P1×6） | 处置 |
|---|---|---|
| 1 | €15 捆绑算术与档位不明；预算失效风险 | §2 预算上限 €136 + 四项书面确认 |
| 2 | 30 槽 < 38 赛事，覆盖不成立 | §2.1 加权覆盖表 + 显式降级规则 |
| 3 | 4 周 RPS vs 14 天试用矛盾 | §4.3 影子模式 + 统计门 + 历史回溯询问 |
| 4 | predictable/unchanged 不能当权重 | §4.1/§3 按联赛×市场统计；unchanged 按未知 |
| 5 | Pinnacle id/许可/全庄历史未确认 | 门1 确认项；双源默认不切 |
| 6 | 结算切主无对账、无状态机 | §4.6 状态机 + 4 周对账 |
| 7 | 双引擎独立性/双重计数 | §4.1 条件信息增量检验；无增量不融合 |
| 8 | 三向 max 离散系统性误杀 | §4.2 主判据改两向；全庄改 IQR 辅助 |
| 9 | 配额低估（分页/全庄/双刷新） | §5 市场过滤 + 熔断 + 死信 |
| 10 | lineups 晚于封存 → 证据漂移 | §4.5 封存纪律 + revision 机制 |
| 11 | "edge"措辞与再分发合规 | §4.4/§6/§9 模板禁词 + 授权确认 + 脚注 |
| 12 | 2 周排期低估 | §8 四门制，2 周只承诺到门3 |

评审原文：[sm_deepseek_review.md](./sm_deepseek_review.md)；评审上下文事实单：[sm_review_context.md](./sm_review_context.md)。
