# 2026-11-11 深审记录：Sportmonks / AI 情报 / 后台 / 前端

范围：当天 30+ 个提交，重点看 Sportmonks 接入、AI 情报、概率对比、后台数据矩阵、赛果回填、模型评估与首页/串关改动。

## 一、已修复的问题

### P0：详情页“模型”概率实际展示的是市场概率

`app/routers/api.py::_probability_compare` 原来用 `v.p_home/p_draw/p_away` 作为模型概率。这三个字段是竞彩去水后的市场概率，导致“竞彩隐含”和“融合模型”两条柱几乎一样，模型卡等于假数据。

修复：模型改用 `v.model_h/d/a`，并兼容 payload 里的 `model.shrunk`；`model_enabled` 同步改为按模型字段判断。
生产验证：历史判决 `v2026-11-08-周日023` 返回模型 `0.2392 / 0.2196 / 0.5411`，竞彩去水 `0.3038 / 0.2341 / 0.4621`，已明显区分。

### P0：Sportmonks 自动同步会把好数据覆盖成 null

`_snapshot` 原来每次同步都无条件写 `probs/odds`。Sportmonks 在比赛开球后或 API 偶发失败时返回空，会把之前已拿到的预测/赔率覆盖成 `None`，后台矩阵从“有数据”变成“未同步”。

修复：

- 自动同步只在拿到非空数据时更新；拿不到就保留上一次有效值，`captured_at` 也不刷新，让市场新鲜度判断自然变旧。
- 自动匹配如果真的换到另一个 fixture（`fixture_id` 变化），则强制清空旧预测/赔率，避免挂错数据。
- 人工改映射 `replace=True`，同样清空旧数据。

### P0：市闸可能拿过期 Sportmonks 赔率过闸

`verdict.py` 直接把 `SportmonksMatchData.odds` 加进市闸，没有校验时间。同步失败后旧赔率仍可能让市闸 `pass`。

修复：新增 `market_is_fresh()`：

- 只接受 2 小时内的赔率；
- 必须包含主/平/客三项；
- 三项都在 (0,1]，且和接近 1。

市闸、详情概率卡、供给诊断、工作台、聚焦覆盖度全部改用同一判断。

### P0：历史赛果回填触发两个生产 500

- `match_results` 唯一约束 `(home, away, match_date)`：同一场多个判决（had/hhad）在同一批插入时重复。修复：预加载已有 key + 批次内 `seen` 集合。
- `settle_verdicts` 对 `pick` 为 JSON null 的历史脏数据调用 `.get()` 抛 `AttributeError`。修复：只处理 `dict` 且 `dir` 非空的 pick。

### P1：UTC 日期窗口漏掉 05:00–08:00 CN 早场

`sync_trade_date` 用 CN 日期直接请求 `fixtures/between`，但 Sportmonks 按 UTC 日期。05:00–08:00 CN 的早场在 UTC 是前一天，会漏映射。

修复：`_fixture_date_range()` 把 CN 销售日窗口转成 UTC 日期区间；新增回归测试。

### P1：AI 情报过期后仍显示“就绪”

`AIResearch.status` 只写 `ready/unavailable`，`expires_at` 到期后详情页仍展示旧情报，后台也计入 ready。

修复：

- `effective_status()`：ready 且过期 → `expired`。
- 详情接口、后台矩阵、后台统计、工作台、首页脉搏统一使用。
- 前端 `AiIntelCard` 只渲染 ready；过期不展示。

### P1：工作台“情报”阶段只数映射行，不检查预测/赔率是否完整

映射存在但 `probs/odds` 为空时，工作台仍可能显示正常。

修复：新增 `sm_ready`（probs + odds 都不为空）作为“完整”口径；映射数和完整数分开展示，缺失时下一步给 `sync_sportmonks`。

### P1：模型效果页基线不是同一批样本

`model_brier` 只统计有模型样本，`market_brier` 统计全部结算样本，两者不可直接比较。

修复：新增 `market_model_brier`，只用“同时有模型概率”的样本算竞彩基线；页面 delta、分联赛结论都改用同批基线，全样本基线作为附注。

### P1：手动映射缺少防呆

`POST /admin/api/sportmonks/map` 可以绑定任意 fixture，可能把完全不同的比赛挂上来。

修复：

- fixture 开球时间与竞彩场次相差 >12h 时拒绝，需显式 `force=true`。
- 一个 Sportmonks fixture 不能同时绑两场竞彩。
- 自动同步不会覆盖人工映射的 `source="manual"` 标记（除非自动匹配真的换绑 fixture）。

### P1：公开数据状态仍只讲“国际盘”

`/stats/pulse` 和 `/matches/{id}/focus` 仍把市场源写成国际盘，Sportmonks/AI 情报没有出现在公开数据状态里。

修复：

- 脉搏新增 `sportmonks`、`intel` 两个来源；国际盘标为“兜底”。
- 单场聚焦的 `market` 覆盖改为 `Sportmonks 新鲜赔率 OR 国际盘`；事实卡优先展示 Sportmonks Pinnacle 去水概率。
- 前端数据状态 Sheet 支持 `partial` 状态，并显示 Sportmonks/AI 情报。

### P2：同场串关、重复“停售”、其他小问题

- 串关腿池新增“同一场比赛只能选一个方向”，详情加入和串关页选择都拦截。
- 列表倒计时新增 `saleCountdownText`，不再出现“已停售停售 / 停售时间待同步停售”。
- 后台同步接口校验日期，非法 date 返回 400 而不是 500。
- 后台矩阵新增 `odds_fresh`，过期赔率显示“已过期”。
- 同步场次按开球时间排序，返回 `total_matches/truncated`，不再静默截断 40 场。

## 二、验证结果

- 后端：`321 passed`。
- 移动端：`45 passed`，`tsc --noEmit`、`eslint` 通过。
- 生产：
  - 今日 6 场全部映射，预测/赔率/AI 情报均为 6/6，赔率全部 fresh。
  - 脉搏：`matches=6, sportmonks=6, ai_intel=6`。
  - 工作台 11 个阶段 evidence 全部为数组。
  - 模型效果：16 条结算样本，模型 Brier `0.7588`，同批竞彩基线 `0.7573`，Top1 `31.2%`。
  - 详情概率卡 model 与 sp 已分离。

## 三、仍然缺的（未在本次强行做）

1. **按联赛开关模型**：`model_enabled` 仍是“有模型概率即展示”，没有按联赛 Brier/样本外验证自动关闭。模型效果页已具备判断依据，但需要样本 ≥30 再动发布逻辑。
2. **Sportmonks Prediction Model 只做展示/对照**：还没有进入 DC 模型特征或按联赛融合；当前只用于后台矩阵和模型效果页。
3. **AI 情报没有“全网搜索”**：目前只翻译 Sportmonks match-facts + sidelined，不是 web search。用户之前提过“未启用的联赛调用 LLM 全网搜索”，这块需要搜索供应商/浏览能力与事实引用规范，不能靠模型记忆编造。
4. **AI 情报每 30 分钟重复调用 LLM**：事实未变也会重算。后续应存 facts hash，只有事实变化或过期才调用，控制成本。
5. **Sportmonks 错误可观测性不足**：`_get` 对 429/5xx 直接返回 None，没有重试/退避，也没有结构化错误日志；同步失败时后台只能看到 missing。
6. **Sportmonks 覆盖受订阅限制**：当前计划每天只有约 21 场 fixture，竞彩超出部分只能显示 missing 并走人工映射；候选里没有的场次无法补。
7. **分享页仍未按“AI 情报不进分享”重新设计**：当前分享仍只带判决叙述，未带 AI 情报，但没有做专门的分享内容分层。
8. **生产仍是 SQLite**：Postgres 迁移、备份/PITR 仍是上线阻塞项。
9. **回填赛果的对账**：历史 71 条 Sportmonks 回填结果只做了严格队名+开球时间匹配，建议抽样与 football-data 重叠场次对账后再扩大回填窗口。
