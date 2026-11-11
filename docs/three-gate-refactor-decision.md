# 三闸与预测呈现重构决策（2026-11-11）

## 结论

**要调整，但不建议把三闸推倒。**

三闸作为“风险证据”是有效的：价闸防高抽水，市闸防单源/异常市场，模闸防无依据方向。问题在于它被当成了**唯一的发布开关**：三闸全过才有内容，任一不过就只剩“今天不硬推”。

在 Sportmonks 预测、Pinnacle 市场、AI 情报和赛果回填都接进来之后，这个二元模式已经不合适：

- 模型没有验证过的联赛，会被模闸永久卡成 pending；
- 市场已经有 Sportmonks 第二源，但内容仍然可能因为模型缺失而全部消失；
- 用户看到的是“有数据但没有预测”，而不是“有依据的参考”；
- 三闸术语对用户不透明，用户无法判断“没过”是风险、成本还是模型没覆盖。

建议改成：**三闸继续做后台诊断与审计，前台改成“核验预测 / 市场参考 / 回避”三层内容。**

---

## 一、当前模式的实际问题

### 1. 二元开关导致内容空窗

`build_verdicts` 现在的规则是：

- 三闸全 pass → `promoted`
- 任一 fail → `killed`
- 其余 → `screening`

推荐主链只把 `promoted` 固化为 snapshot，再经 L1–L5 发布。结果是：

- 模型联赛未验证/无 xG → 模闸 pending → 永远不 promoted；
- 价闸严格 → 高抽水场次全部 killed；
- 市闸多源分歧 → killed；
- 用户端首页没有“已发布”，只剩“今天不硬推”。

这不是“诚实”，而是**把数据覆盖问题伪装成产品结论**。

### 2. 模型还没有证明自己

当前生产模型效果页的 16 条结算样本：

- 模型 Brier `0.7588`
- 同批竞彩去水基线 `0.7573`
- Top1 命中 `31.2%`

模型没有跑赢基线。168 场 Sportmonks 回测也同样显示：

- SM logloss `0.988` vs Pinnacle `0.955`
- SM RPS `0.193` vs Pinnacle `0.183`
- SM 命中 `52%` vs Pinnacle `54%`

所以现在把“模型闸”当成内容生死线，等于用一个**尚未验证的模型**决定用户今天能不能看到内容。

### 3. 新数据源没有被正确分层

现在同时有：

- 竞彩官方 SP（成本/价格基准）
- Sportmonks Pinnacle 1X2（市场基准，部分联赛可用）
- Sportmonks Prediction Model 237（第三方模型，按联赛强弱不同）
- 自有 DC 模型（依赖 xG，当前源不稳定）
- AI 情报（事实摘要，不是概率）

它们不是同一种东西，不能都塞进“模型闸”。尤其：

- AI 情报不能参与概率判断；
- SM Prediction 不能默认比 Pinnacle 强；
- 自有 DC 模型在联赛没验证前只能 shadow；
- Pinnacle 是市场基准，不是“模型”。

### 4. 用户看到的是内部术语

“价闸 / 市闸 / 模闸”“三关通过”“复核中”是运营语言。用户真正想知道的是：

- 这场有没有值得看的结论？
- 结论依据是什么？
- 风险/成本在哪里？
- 没有结论时，是数据不够、成本太高，还是模型不占优？

---

## 二、建议的新内容模型

### 2.1 三闸保留为诊断，不再直接决定“有没有内容”

保留 `price/market/model` 三个 gate 结果，用于后台、审计、证据链和复盘；新增一个**内容层（tier）**：

| Tier | 含义 | 展示 | 发布 |
|---|---|---|---|
| `verified` | 价、市、模都过，且该联赛模型已验证 | “核验预测” | 走现有 L1–L5 发布 |
| `market_reference` | 价、市可用，但模型未验证/不占优/缺失 | “市场参考”，明确非模型预测 | 不进付费；可进助理/比赛页/详情参考区 |
| `avoid` | 价闸失败、市闸分歧、数据过期/不足 | “不建议”，展示原因 | 不发布 |
| `no_data` | 连 SP/市场都不完整 | “待数据” | 不发布 |

关键变化：

- 模型不可用 → 从 `screening/pending 永久` 变成 `market_reference`；
- 模型不占优 → `market_reference`，而不是直接消失；
- 价闸/市闸失败 → 仍是 `avoid`，因为这是成本和市场风险，不是“没模型”；
- `verified` 才是原来的“三闸全过 + 联赛模型已验证”。

### 2.2 联赛模型注册表

新增 `league_model_config`（或等价配置）：

- `league`
- `dc_status`: `disabled / shadow / enabled`
- `sm_status`: `disabled / shadow / enabled`
- `weight_dc / weight_sm`
- `samples`, `brier_dc`, `brier_market`, `rps_dc`, `rps_market`
- `validated_at`, `enabled_by`

规则：

1. 默认全部 `shadow`，只展示不参与 tier=verified。
2. 样本 ≥100（最好 200）且滚动 Brier/RPS 显著优于市场，才 `enabled`。
3. 五大联赛可先跑 DC；非五大联赛先看 SM 是否真的优于 Pinnacle，不默认启用。
4. SM 与 Pinnacle 高度相关，不能因为“两个模型都同意”就当成独立证据；先做增量信息检验，再决定融合权重。
5. 固定 0.5/0.5 融合不做。

### 2.3 Gate 结果变成证据，不是口号

对外不再展示“三闸”字样，详情页改成三段：

1. **结论**：核验预测 / 市场参考 / 不建议
2. **依据**：市场隐含、第三方参考、自有模型（若启用）、AI 情报摘要
3. **风险**：抽水、市场分歧、数据截止、失效条件

后台仍保留 gate 详情和 L1–L5 复核，供运营和审计使用。

---

## 三、前台呈现建议

### 3.1 首页开场

现在：

> 今天没有值得发布的预测。

改成：

> 今天 6 场：2 场已核验，3 场只有市场参考，1 场不建议。
> 先看哪场？

选择条状态：

- `核验预测`（绿）
- `市场参考`（蓝/灰，明确“非模型预测”）
- `不建议`（amber，点开看原因）
- `待数据`（muted）

### 3.2 详情页

头部 tier 标签 + 一句结论，不再让用户先看三个闸。

概率区建议四行（有则显示）：

| 行 | 含义 |
|---|---|
| 竞彩隐含 | 官方 SP 去水 |
| 市场基准 | Sportmonks Pinnacle / 国际盘 |
| 第三方参考 | Sportmonks Prediction 237，标“第三方，非本产品模型” |
| 自有模型 | 仅在联赛模型启用时显示；否则显示“未启用/未验证” |

如果 tier=`market_reference`，不显示“主胜/客胜预测”这种拟结论，只显示“市场倾向：主胜 48%（市场隐含），无模型优势”。

如果 tier=`avoid`，显示：

- 不建议原因（抽水 14.2% 超阈值 / 市场分歧 8pp / 数据过期 / 模型不占优）
- 仍可展开证据，不隐藏数据。

### 3.3 文案边界

- `verified` 才能用“预测方向 / 置信度 / 条件 / 失效条件”。
- `market_reference` 只能用“市场倾向 / 参考 / 非模型预测”。
- `avoid` 只能用“不建议 / 原因”。
- 不使用“三关通过”“稳”“价值”“edge”“庄家优势”等词。

---

## 四、后端/API 改造

### 4.1 数据模型

给 `Verdict` 增加：

- `tier`: `verified / market_reference / avoid / no_data`
- `model_status`: `disabled / shadow / enabled / unavailable`
- `model_source`: `dc / sm / ensemble / none`
- `data_quality`: JSON（SP 新鲜度、市场源、模型覆盖、截止时间）

`status` 保留 `promoted/screening/killed` 作为内部状态，避免一次性改爆旧接口；对外用 `tier`。

### 4.2 生成逻辑

```text
price_fail  -> avoid
market_fail -> avoid
data_missing -> no_data
model_status != enabled -> market_reference
model_gate fail -> market_reference（标“模型不占优”）
all pass + model enabled -> verified
```

这样模型缺失不再阻断内容，但也不会把市场参考伪装成模型预测。

### 4.3 发布链

- `verified`: 走现有 `DecisionSnapshot` + L1–L5 + publish。
- `market_reference`: 新增 reference snapshot / 或独立 `/matches/{id}/reference`；只做确定性规则 +  banned-word 扫描，不进付费。
- 首页 `/recommendations/today` 返回 `verified` 和 `reference` 两个数组，前端分别渲染。
- `avoid/no_data` 进 stream 的 avoid 区，不进发布链。

### 4.4 后台

- 新增“模型开关”页：按联赛显示样本、Brier、RPS、当前状态、启用/停用。
- 模型效果页已有数据；增加“建议状态”和“启用”动作，但启用需要二次确认。
- 数据源页显示“模型覆盖：dc/sm/shadow”，而不是只有 SM 映射。

---

## 五、分阶段落地

### Phase 1（低风险，先不改发布）

1. 新增 `tier/model_status/model_source/data_quality` 字段与迁移。
2. `build_verdicts` 计算 tier，但先只写字段，不改变现有 promoted/publish。
3. 详情 API 返回 tier 和新概率行；前端加 tier 标签和 SM 第三方参考行。
4. 后台模型效果页加 per-league 状态展示。

### Phase 2（内容分层）

1. `/recommendations/today` 增加 reference 区。
2. 首页/比赛页展示 market_reference；文案边界上线。
3. 发布链支持 reference snapshot，不进入付费。

### Phase 3（模型门控）

1. `league_model_config` + 后台开关。
2. 用历史 100–300 场/联赛跑 Brier/RPS，先 shadow，再逐联赛启用。
3. 验证 SM 与 Pinnacle 的增量信息，再决定是否融合。

### Phase 4（实验与回收）

观察：

- 首页有内容率
- 详情打开率、关注率、记注转化
- verified 的 CLV / Brier / 连败
- reference 的点击与误解投诉
- 空窗天数

如果 reference 被用户误解为“预测”，回退到只展示“市场倾向”并用更弱视觉。

---

## 六、建议

**做，但按“三闸保留 + 内容分层 + 联赛模型门控”做，不要直接删三闸，也不要把 SM Prediction 当成新救世主。**

最小第一步不是改发布链，而是：

1. 给 verdict 加 `tier` 和 `model_status`；
2. 详情页把“自有模型”和“第三方参考”分开；
3. 后台把每联赛模型状态显示出来；
4. 先让首页能诚实展示“市场参考”，再决定是否让它进主推荐位。

这样既不牺牲诚实性，也不会继续用未验证模型把内容全部卡死。

## 实施状态（2026-11-11）

- Phase 1：`verdicts.tier/model_status/model_source/data_quality` 已落库；详情/流/后台序列化已返回；概率卡增加 Sportmonks 第三方参考行；详情头部显示“核验预测 / 市场参考 / 不建议 / 待数据”和“模型影子”。
- Phase 2：`/recommendations/today` 返回 `references`；首页选场条、开场文案、详情卡和比赛页接入市场参考；市场参考卡不再显示“预测/预测概率/三闸”。
- Phase 3：`league_model_config` + 后台“模型开关（按联赛）”已实现；默认 disabled/shadow，`JQ_TIER_ENFORCE=false` 保持旧发布语义，开启后才只有 enabled 联赛可 `verified`。
- Phase 4：后台模型效果页增加内容分层计数（近 N 天）与分层指标接口 `/admin/api/tier-metrics`；`tier_enforce` 状态在页面可见。
- 迁移：Alembic `20261111_21` / `20261111_22`；Postgres `alembic upgrade head --sql` 已离线验证。
