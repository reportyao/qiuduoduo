# Sportmonks 实测报告与方案 v3（真实 token 验证）

> 验证时间：2026-11-11
> 方式：用真实 API token 直连 api.sportmonks.com 探测（token 仅存临时文件，未写入仓库）；抽样 14 个联赛、168 场已完赛比赛做 SM Prediction vs Pinnacle 收盘回测。
> 结论：**Prediction Model 可用、覆盖面好、历史可回溯；但"SM 一定比市场准"不成立——必须按联赛回测门控。当前订阅的 29 个联赛里有 8 个废槽，且缺日职/欧国联/亚冠/北欧，先换槽再谈接入。**

---

## 1. 订阅实测（和之前假设不一样的地方）

```text
计划：Growth - Trialing until 2026-11-25 03:32 UTC（category=Advanced）
附加：Euro Club Tournaments（All-in）+ Odds & Predictions 捆绑（试用）
加购：add_ons = []（xG/Livescores/Premium 均未购买）
限流：2,500 次/小时（实测响应头 x-ratelimit-limit=2500，每次请求扣 1）
联赛：已选 29 个（Growth 上限 30，尚有 1 个空位）
```

关键事实：

1. **试用 11-25 到期**，到期前必须决定是否续费/换档；Advanced 试用结束后若只续 Basic，Live 预测端点会关闭（赛前预测不受影响）。
2. **xG 端点试用期可访问**（`/expected/fixtures` 返回赛后 xG），但 `add_ons` 为空，续费后不保证——**不能把 xG 写进生产依赖**。
3. 试用含 Odds & Predictions 捆绑，Pinnacle 赔率、预测、value-bets、predictability 全部可用。

## 2. 当前 29 个联赛：8 个废槽，缺 6 类主力

### 2.1 废槽（竞彩几乎不卖/数据不可用）

| 联赛 | id | 问题 |
|---|---|---|
| Primeira Liga | 1100 | **死槽**：`currentseason=null`、`last_played_at=2021-12-06`、无 Odds 特性；不是真葡超 |
| La Liga 2 | 567 | 竞彩近两月 **0 场** |
| Bundesliga Play-offs | 163 | 竞彩不卖 |
| Ligue 1 Play-offs | 1673 | 竞彩不卖 |
| Ligue 2 Play-offs | 1674 | 竞彩不卖 |
| Eredivisie Play-offs | 1353 | 竞彩不卖 |
| Eredivisie Cup | 2037 | 竞彩不卖 |
| UEFA Super Cup | 1328 | 一年一场 |

### 2.2 缺失（按竞彩近两月场次量）

| 缺失 | id（覆盖页） | 竞彩场次/2月 |
|---|---|---|
| UEFA Nations League 欧国联 | 1538 | 52（当前批次就有 6 场） |
| J-League 日职（J1） | 968 | 29 |
| AFC Champions League Elite 亚冠精英 | 3381 | 23 |
| Allsvenskan 瑞超 | 573 | 21 |
| Eliteserien 挪超 | 444 | 18 |
| Veikkausliiga 芬超 | 292 | 13 |
| 2. Bundesliga 德乙 | 85 | 7 |
| 真·Primeira Liga 葡超 | 462 | 24（替换死槽 1100） |
| Carabao Cup 英联杯（备选） | 27 | 9 |

### 2.3 换槽清单（30 个）

**保留 21 个**：UCL 2、UEL 5、UECL 2286、EPL 8、Championship 9、EFL Trophy 39、Eredivisie 72、Eerste 74、Bundesliga 82、Ligue 1 301、Ligue 2 304、Serie A 384、La Liga 564、Liga Profesional 636、Brazil Serie A 648、Serie B 651、MLS 779、J2 1022、J-League Cup 1031、K League 1 1034、A-League 1356。

**换出 8 个**：1100、567、163、1673、1674、1353、2037、1328。

**换入 9 个**（8 换 + 1 空位）：462（真葡超）、968（日职）、1538（欧国联）、3381（亚冠精英）、573（瑞超）、444（挪超）、292（芬超）、85（德乙）、27（英联杯，备选；若 dashboard 预测覆盖不通过则保留 La Liga 2 或补巴乙）。

> 注意：Growth 每月有换槽次数限制，试用期内能否一次换 8 个需在 my.sportmonks.com 确认；换槽前先确认 462 可选（覆盖页有完整特性）。

## 3. Prediction Model 实测

### 3.1 数据形态

- 每场比赛返回 **25 条预测**：237 胜平负、240 比分矩阵、231 BTTS、234/235/236/1679 大小球、232 半全场、233 半场胜者、238 先进球、239 双 chance、326-334 单队大小球、1683-1690 角球。
- 概率是百分比（如 `{"home":41.09,"away":34.59,"draw":24.27}`），三向和=100。
- **没有 37072/predictable 行**；实测"有行=可预测"，无行=无预测。抽样 168 场全部有预测（覆盖率 100%）。
- 历史预测 **至少回溯 1 年**（2025-11-08 的比赛仍有 10 条预测）——验证不用等影子期。
- 历史 Pinnacle 收盘赔率同样可回溯（2025-11 的 Match Winner 3 条在库）。

### 3.2 赔率实测

```text
Market Winner = market_id 1
Pinnacle = bookmaker_id 20
单场只拉 Pinnacle 1X2：filters=markets:1;bookmakers:20 → 3 行 / 1 次请求
不过滤全量：单场 2,770 行 ≈ 56 页（绝不能这么拉）
全庄 1X2：filters=markets:1 → 54 行（18 家 × 3）/ 2 页
```

Pinnacle 对 EFL Trophy、J-League Cup 都有盘（实测），更新时间在分钟级。

### 3.3 Value Bets 实测

- 全量端点只有 **3 条**；单场通常 1 条且 `is_value=false`。
- 结论：**不作为核心信号**，只做 review 层参考 chip。

### 3.4 predictability 实测（有数值，不只有定性）

每个联赛返回 5 类：241 数值 log loss、242 命中率、243 定性评级、244 趋势、245 另一版 log loss。但**存在明显异常**：

| 联赛 | 241 logloss | 242 命中 | 243 评级 | 244 趋势 |
|---|---|---|---|---|
| EPL | -1.1113 | 0.44 | good | up |
| La Liga | -1.0884 | 0.50 | high | unchanged |
| Serie A | -1.0897 | 0.58 | high | up |
| Bundesliga | -1.0806 | 0.5455 | high | down |
| Ligue 1 | -1.0413 | 0.53 | **poor** | up |
| Championship | -1.0779 | 0.47 | medium | up |
| EFL Trophy | -1.0233 | 0.50 | **poor** | down |
| Eredivisie | -1.1352 | 0.47 | high | unchanged |
| Eerste | -1.078 | 0.48 | medium | down |
| K League 1 | -1.1 | 0.43 | **poor** | unchanged |
| J2 | -1.0988 | 0.53 | good | up |
| J-League Cup | -0.5377 | 0.5962 | **poor** | unchanged |
| A-League | -0.9587 | 0.3214 | **poor** | up |
| MLS | -1.0812 | 0.50 | medium | up |
| Argentina | -1.1067 | 0.48 | high | unchanged |
| Brazil A | -1.0246 | 0.57 | high | unchanged |
| Serie B | -1.0706 | 0.49 | good | unchanged |
| Ligue 2 | -1.0852 | 0.49 | **poor** | up |
| La Liga 2 | -1.0728 | 0.52 | medium | unchanged |
| Primeira 1100 | — | — | — | —（死槽，无数据） |

异常点：J-League Cup logloss 0.54/命中 59.6% 却评 poor；A-League 命中 32% 却 logloss 0.959。**说明单看官方评级会误判，必须自己回测。**

### 3.5 我们的真实回测（2026-10，14 联赛 × 12 场 = 168 场）

| 联赛 | n | SM logloss | Pinnacle ll | SM RPS | Pin RPS | SM 命中 | Pin 命中 |
|---|---:|---:|---:|---:|---:|---:|---:|
| EPL | 12 | **0.949** | 0.970 | **0.190** | 0.196 | 0.58 | 0.50 |
| La Liga | 12 | 0.977 | **0.892** | 0.143 | **0.116** | 0.42 | 0.50 |
| Serie A | 12 | **0.925** | 0.934 | **0.181** | 0.186 | 0.67 | 0.58 |
| Championship | 12 | 1.062 | **0.996** | 0.230 | **0.203** | 0.42 | 0.58 |
| J2 | 12 | 1.077 | **1.018** | 0.249 | **0.228** | 0.42 | 0.50 |
| K League 1 | 12 | 0.998 | **0.961** | 0.203 | **0.196** | 0.58 | 0.50 |
| EFL Trophy | 12 | 0.779 | **0.618** | 0.194 | **0.144** | 0.83 | 0.83 |
| Eredivisie | 12 | **1.029** | 1.150 | **0.192** | 0.235 | 0.42 | 0.42 |
| Eerste | 12 | **1.107** | 1.110 | **0.167** | 0.173 | 0.50 | 0.50 |
| Ligue 2 | 12 | 0.967 | **0.917** | 0.194 | **0.181** | 0.58 | 0.50 |
| Brazil A | 12 | 0.968 | **0.949** | 0.178 | **0.169** | 0.50 | 0.58 |
| Serie B | 12 | 0.893 | **0.827** | 0.207 | **0.184** | 0.50 | 0.58 |
| MLS | 12 | 1.001 | **0.940** | 0.182 | **0.165** | 0.50 | 0.50 |
| A-League | 12 | 1.109 | **1.086** | 0.195 | **0.190** | 0.42 | 0.50 |
| **合计** | **168** | **0.988** | **0.955** | **0.193** | **0.183** | **0.52** | **0.54** |

结论（样本小，方向性）：

1. **整体 Pinnacle 收盘仍是最强基准**（RPS 0.183 vs 0.193）；
2. **SM 在 EPL、意甲、荷甲、荷乙优于 Pinnacle**；在西甲、英冠、日乙、韩职、法乙、巴甲、意乙、MLS、澳超、EFL Trophy 不如 Pinnacle；
3. 12 场/联赛噪声很大，必须扩到 100-300 场/联赛再下结论；
4. 官方评级与实测不完全一致（La Liga 评级 high，但样本里 Pinnacle 更好）→ **自测优先**。

## 4. 方案 v3：九处修正

### 修正 1：先换槽，再谈接入

当前订阅缺日职/欧国联/亚冠/北欧，导致"接了 SM 但当前 14 场比赛里 6 场欧国联完全没数据"。**任何接入工作开始前，先在 dashboard 完成 §2.3 换槽。**

### 修正 2：模型闸改为"按联赛回测门控"，不是 SM 单引擎

```text
对每个联赛 L：
  回测 ≥100 场（历史 predictions + 历史 Pinnacle 收盘 + 赛果）
  计算 RPS_SM、RPS_PIN、RPS_DC（如 DC 有覆盖）、RPS_blend
  若 RPS_SM < RPS_PIN（bootstrap 95% CI 不交叉）:
       模型 = SM（五大可再与 DC 按逆 RPS 加权）
       启用模型闸
  否则若 RPS_DC < RPS_PIN:
       模型 = DC
       启用模型闸
  否则:
       模型闸关闭（该联赛不发布预测，只展示 SP 与分析）
```

- 五大联赛：DC 有数据，先比 DC/SM/Pin 三方，谁赢用谁/加权；
- 非五大：SM 与 Pin 二选一，SM 赢才启用；
- 证据层记录 `model_source`、`rps_sm`、`rps_pin`、`rps_dc`、`enabled`、`sample_n`。

**这一条推翻了 v2 的"非五大 SM 单引擎"**——实测证明 SM 不是全联赛都强，盲目启用会比市场基准更差。

### 修正 3：验证从"影子 4 周"改为"历史回测先行 + 影子监控漂移"

- 历史预测/赔率可回溯 ≥1 年 → **先跑 100-300 场/联赛回测**，2-3 天可完成；
- 上线后仍保留每日预测快照，用于监控漂移（不是用来等样本）；
- 每季度重跑回测，权重/开关随数据调整。

### 修正 4：赔率拉取固定过滤

- 模型/验证：`filters=markets:1;bookmakers:20`（3 行/1 请求/场）；
- 市场闸全庄辅助：`filters=markets:1`（54 行/2 页/场，只取离散统计后丢弃明细）；
- 永不拉全市场（2,770 行/56 页/场）。

### 修正 5：Value Bets 降级

- 只存 `sm_valuebets`，review 层参考 chip；不进模型闸、不进价闸；
- 文案禁止 "value/edge/价值/庄家优势"。

### 修正 6：xG 不买不接

- 试用期 `/expected/fixtures` 能读，但只含**赛后** xG；赛前预测用不上；
- 续费后无 add-on 会失效；DC 训练继续用 Understat（五大免费）。

### 修正 7：predictability 只做先验

- 数值 241/242 + 定性 243 作为"预期质量"先验；
- 最终开关用我们的回测 RPS，不直接用官方评级（实测有矛盾）。

### 修正 8：试用到期与计费

- 11-25 前确认：Growth 续费价、Odds & Predictions 捆绑续费档位（Basic/Advanced）、Euro Club Tournaments 是否单独计费；
- 若只续 Basic：Live 端点关闭，赛前预测不受影响；不要做 Live 功能；
- 换槽动作要在试用结束前完成并验证。

### 修正 9：UI 与后台按"启用状态"展示

- 详情页概率对比卡增加一行：`模型：已启用 / 未启用（该联赛回测未跑赢市场）/ 数据不足`；
- 后台"模型对照"页直接用回测表（RPS + 样本量 + 开关），不做假仪表盘。

## 5. 修正后的接入设计

### 5.1 端点与用途

| 用途 | 端点 | 过滤/参数 | 频率 |
|---|---|---|---|
| 赛程对齐 | `/fixtures/date/{date}` | include=participants;league;state | 每日 |
| 单场详情 | `/fixtures/{id}` | include=participants;league;state;scores | 按需 |
| 1X2 概率 | `/predictions/probabilities/fixtures/{id}` | include=type；取 type_id=237 | 每日 + T-2h |
| 其他市场（预留） | 同上 | 231/234/235/239/240 | 暂不接 |
| 赔率（模型/市场） | `/odds/pre-match/fixtures/{id}` | `filters=markets:1;bookmakers:20` | 每日 + T-2h |
| 全庄 1X2（辅助） | 同上 | `filters=markets:1` | 每日 |
| 联赛模型质量 | `/predictions/predictability/leagues/{id}` | — | 每周 |
| 伤停 | fixture include `sidelined` | — | 每日 + T-2h |
| 阵容 | fixture include `lineups` | — | T-2h / T-30m |
| 积分榜 | `/standings/season/{id}` | — | 每日 |
| 赛果 | `/fixtures/date/{date}` | include=scores;state | 每日 |
| Value Bets（参考） | `/predictions/value-bets/fixtures/{id}` | — | 每日 |

### 5.2 配额实测预算

```text
单场：predictions 1 + Pinnacle 1X2 1 + 全庄 1X2 2 页 ≈ 4 次
30 场/日 ≈ 120 次/日；加 lineups/sidelined/standings ≈ 200 次/日
回测：1,000 场 ≈ 2,200 次（约 1 小时跑完）
Growth 2,500/小时：余量充足，无需担心
```

### 5.3 表结构（在 v2 基础上收敛）

```text
sm_predictions        (fixture_id, type_id, payload, captured_at)
sm_odds               (fixture_id, bookmaker_id, market_id, label, value, captured_at)
sm_predictability     (league_id, metric_type, data, captured_at)
sm_backtests          (league_id, sample_n, rps_sm, rps_pin, rps_dc, rps_blend, enabled, run_at)
sm_valuebets          (fixture_id, payload, captured_at)
sm_usage              (day, endpoint, count)
sm_dead_letter        (endpoint, fixture_id, error, payload, created_at)
```

### 5.4 排期（倒排到 11-25）

| 时间 | 动作 |
|---|---|
| 今天-11-12 | 用户在 dashboard 换槽（8 换 9），确认续费档位与换槽次数 |
| 11-12~11-15 | 我写 adapter + 历史回测脚本，跑 14 联赛 × 100-300 场 |
| 11-15~11-18 | 出 per-league 开关表；接 Pinnacle 市场闸（双源并行） |
| 11-18~11-22 | 预测接入（仅回测通过的联赛）；UI 概率对比卡（只读） |
| 11-22~11-25 | 验收、决定续费；未通过联赛保持"模型未启用" |

## 6. 风险与待确认

| 事项 | 状态 |
|---|---|
| Growth 试用期换槽次数/是否收费 | 需 dashboard/客服确认 |
| 11-25 后续费档位（Basic/Advanced）与价格 | 需确认 |
| 462 真葡超是否在 Growth 可选 | 覆盖页有，需 dashboard 验证 |
| 968 日职、1538 欧国联、3381 亚冠的预测覆盖 | 换槽后立即用脚本验证 |
| 27 英联杯预测覆盖 | 换槽后验证，不通过则换 La Liga 2/巴乙 |
| 168 场回测样本偏小 | 扩到 100-300 场/联赛再定开关 |
| Token 安全 | 只在临时文件；建议 11-25 后轮换一次 |

---

*附：回测明细 `docs/sm_backtest_2026-10.csv`（168 行，字段含 SM/Pinnacle 概率与逐场 RPS/logloss）；探测脚本 `scripts/sm/sm_probe*.py`、`scripts/sm/sm_backtest.py`，token 从环境变量/临时文件读取，不含明文。*

---

## 12. 2026-11-11 实际换槽执行结果（已保存并 API 复核）

### 12.1 已移除（7 个废槽）

Bundesliga Play-offs 163、La Liga 2 567、Primeira Liga 1100（死条目）、Eredivisie Playoffs 1353、Ligue 1 Play-offs 1673、Ligue 2 Play-offs 1674、Eredivisie Cup 2037。

### 12.2 已加入（8 个）

Liga Portugal 462（真葡超）、Carabao Cup 27（英联杯）、2. Bundesliga 85（德乙）、Allsvenskan 573（瑞超）、J1 League 968（日职）、AFC Champions League Elite 1085（亚冠精英）、Eliteserien 444（挪超）、J1/Eliteserien Play-offs 1768/1760（随主联赛自动带上的附加项，无害）。

### 12.3 当前状态

- API `/v3/my/leagues`：**31 个条目** = UI 27 个 Growth 名额 + 4 个 specials（UCL/UEL/UECL/UEFA Super Cup）；
- Growth 名额：**27/30，剩 3 个空位**（未填，留给月度换槽/赛季轮换）；
- 欧国联仍不可用：点击时提示属于 **International Tournaments 专项（€129/月）**，不在 Growth 30 名额内——当前 6 场欧国联只能维持"无 SM 数据"；
- 芬超/解放者杯/沙特联/亚冠2/德国杯：有竞彩场次但本次未加，3 个空位可后续按赛季补。

### 12.4 重要计费警告

订阅页显示：**试用 11-25 到期后自动扣费 €197/月**（不是之前估算的 €114）。包含 Growth + Euro Club Tournaments 等组合；到期前需在 Billing 页确认是否保留全部组成，否则会自动按 €197 扣款。

### 12.5 新发现：Pinnacle 不是全联赛都有

换入后立即验证（2026-11-20 前后场次）：

| 联赛 | 预测 237 | 1X2 书商数 | Pinnacle |
|---|---|---|---|
| Allsvenskan | ✅ | 8 | ✅ |
| 2. Bundesliga | ✅ | 有 | ✅（3 行） |
| Eliteserien | ✅ | 5（Dafabet/Marathonbet/1xbet/MelBet/bet365） | ❌ |
| J1 | ✅ | 0（距开赛 8 天，赔率未挂） | ❌ |
| Liga Portugal | ✅ | 1 | ❌ |
| ACL Elite | ✅ | 2 | ❌ |
| Carabao Cup | ❌（场次太远） | 0 | ❌ |

**结论：市场闸不能写死"Pinnacle 唯一基准"，必须做书商降级链**：

```text
Pinnacle(20) 有 → 用 Pinnacle 去水
否则 bet365(2) 有 → 用 bet365 去水
否则用该场可用书商的中位数（≥3 家才计算）
都没有 → market=pending，不发布
```

并按联赛记录 `bookmaker_availability`（哪家可用、最后更新时间），J1 这类"赔率晚挂"的联赛要在 T-2h/T-30m 再拉一次。
