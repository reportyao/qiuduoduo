# 管理后台重构 · Sportmonks / AI 情报 / 模型评估（2026-11-11）

## 这次改了什么

### 1. 数据源页从“状态卡片”改成“逐场作业台”

旧页面只能看 Sportmonks 覆盖数和缺场名单，运营发现“少一场”后无法处理。现在 `数据源` 页直接给今日竞彩场次矩阵：

| 列 | 内容 |
|---|---|
| 场次 / 对阵 | 竞彩编号、单关标记、队名、联赛、开赛时间 |
| SM 映射 | 自动 / 手动 / 未映射，fixture id |
| 模型概率 | Sportmonks Prediction Model 1X2（主 / 平 / 客） |
| 市场概率 | Pinnacle 1X2 去水（无 Pinnacle 时显示实际书商） |
| AI 情报 | ready / unavailable / 未同步 + 中文 headline |
| 判决 | promoted / screening / killed + pick + 赛果 |
| 操作 | 手动映射、改映射、重拉、解除 |

顶部 KPI：今日场次、SM 映射、模型概率、AI 情报、已发布。内容供给漏斗保留，但市场覆盖改为 `SM + 国际盘` 合并口径。

### 2. 手动映射闭环

新增接口：

- `GET /admin/api/sportmonks/matrix?date=YYYY-MM-DD`：逐场矩阵。
- `GET /admin/api/sportmonks/candidates?match_id=...`：开球前后 6 小时的 Sportmonks fixture 候选，带时间差、队名相似度、自动匹配建议、是否已被其他竞彩场绑定。
- `POST /admin/api/sportmonks/map` `{match_id, fixture_id}`：人工绑定，并立即拉取预测 / Pinnacle 1X2 / AI 情报。
- `DELETE /admin/api/sportmonks/map/{match_id}`：解除映射，同时删除该场 AI 情报，等下一次自动同步重新匹配。

约束：

- 一个 Sportmonks fixture 只能绑定一个竞彩 `match_id`。
- 手动绑定写 `source="manual"`，后台用蓝色“手动”标记，和自动映射区分。
- 解除 / 改映射都会写 admin 审计。
- 自动映射失败不会猜；仍然只接受开球 ±2h + 队名相似度规则。

### 3. Sportmonks Pinnacle 正式进入市闸

之前市闸只认 `The Odds API`，导致“Sportmonks 已覆盖但市闸仍 pending”。现在 `verdict.py` 会把 `SportmonksMatchData.odds`（Pinnacle 1X2 去水概率）作为竞彩官方之外的第二市场源：

- 有 Sportmonks Pinnacle → 可以不依赖 The Odds API 过市闸。
- 两者都有 → 市闸按多源离散度计算。
- 都无 → `pending_data`，原因文案改为“市场源不足”。

`supply.py` 的供给诊断同步改为合并覆盖：

- `sportmonks_market.covered_matches`
- `intl_odds.covered_matches`（The Odds API，兜底）
- `market_covered_matches`（二者并集）

健康检查不再因为“The Odds API 未配置”直接报 high；只有市场源完全为空才 high。

### 4. 新增“模型效果”页

`GET /admin/api/model-eval?days=90` 对已结算且有比分的判决计算 Brier：

- 模型概率（`verdict.model_h/d/a`）
- 竞彩去水基线（`verdict.p_home/p_draw/p_away`）
- Sportmonks Pinnacle 市场
- Sportmonks Prediction Model

按联赛聚合，样本 ≥10 才显示“模型更优 / 基线更优”，避免小样本误判。页面同时展示最近 40 场结算明细。这个页面是下一步“按联赛开关模型”的依据，不直接改发布逻辑。

### 5. Sportmonks 赛果回填

football-data.co.uk 只覆盖五大联赛，而竞彩大量场次是英锦标赛、日联赛杯等，导致 `verdicts.settled` 长期为 0、模型效果页无样本。新增 `app/modules/sportmonks_results.py`：

- 对最近 N 天已开球且已映射的场次，按 `fixture_id` 取 `state` + `CURRENT` 比分。
- 只接受 FT / AET / PEN；拿不到就保持未结算，绝不推算。
- 写入 `match_results` 后调用 `settle_verdicts`，覆盖所有联赛。
- `POST /admin/api/sportmonks/results` 手动回填最近 2 天；生产 cron 每小时 :20 自动跑最近 2 天。
- `POST /admin/api/sportmonks/results/backfill` 对历史未结算判决按开球日拉 fixture 回填（默认 14 天，每天最多 3 页，不逐场请求）；后台“回填赛果”按钮会同时跑这两个接口。

### 6. 工作台修正

- 阶段顺序改为：采集 → 入库 → 情报 → 市场 → 模型 → 三闸 → 封存 → 复核 → 发布 → LLM → 推送。之前“情报”排在“入库”前面，阅读顺序错误。
- 情报阶段和经济阶段可直接执行 `sync_sportmonks` / `sync_intel`，走 allowlist，不执行任意命令。
- 市场阶段文案从“国际盘”改为“Sportmonks 市场 + 国际盘”，并显示 SM Pinnacle 覆盖数。

### 7. 接入中心分区

- **主数据链路**：Sportmonks、AI 情报、竞彩 SP 采集器。
- **兜底数据源**：API-Football、The Odds API，明确标“非主链路”。
- LLM 配置卡继续显示 `reasoning`（auto / off），文案模型池单独管理。

## 仍然要注意

1. **AI 情报不是概率**：只做事实翻译/摘要，不参与模型、不参与市闸。
2. **模型效果页只做评估**：当前 `model_enabled` 仍是“有模型预测即展示”，没有按联赛自动关闭；是否关闭要看这个页面的样本外结果。赛果回填只覆盖“已映射 + 已完赛”的场次，上线首日样本仍会从 0 开始积累。
3. **Sportmonks 赔率不是每个联赛都有 Pinnacle**：`_fetch_odds` 会退回其他书商，后台显示实际书商名；市闸使用前只校验概率和为 1。
4. **手动映射会消耗 API 配额**：一次映射 = fixture 详情 + 预测 + 赔率 + 情报（match-facts + sidelined + LLM）。只对缺场/错场使用。
5. **生产仍是 SQLite**：本轮没有改数据库结构，不需要迁移；Postgres 切换仍是独立任务。

## 验证

```bash
cd jieqiu-backend
python -m pytest tests/test_admin_ui.py tests/test_w3_review.py tests/test_sportmonks_results.py -q
node --check app/static/admin/admin.js
```

新增测试覆盖：

- 数据矩阵字段、手动映射标记、情报状态、判决状态。
- 候选 fixture 查询、绑定、解除接口。
- 模型效果 Brier 聚合。
- Sportmonks Pinnacle 单独作为第二市场源时市闸 `pass`。
