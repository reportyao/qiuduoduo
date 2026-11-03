# 技术方案开源复用审查 v1.0

| 项目 | 内容 |
|---|---|
| 审查对象 | TechSpec v2.1 全部技术选型 |
| 专项问题 | penaltyblog 是否真正"融入开发" |
| 结论 | **penaltyblog 只完成"选型登记"，未完成"工程融入"——缺 5 项落地设计；另发现 6 个高价值开源项目未被采用** |
| 日期 | 2026-11-01 |

---

## 一、penaltyblog 融入度评估（核心问题）

### 1.1 现状：文档提及 12 次，全部停留在"用它"

| 出现位置 | 内容 | 性质 |
|---|---|---|
| TechSpec §1 | "penaltyblog（DC/贝叶斯/去水/抓取）取代自写模型层" | 选型登记 |
| TechSpec §8 | 能力清单罗列 | 选型登记 |
| TechSpec §13 | W1 用它跑三数验证 | 排期 |
| Review v2.0 | 省时估算 2–3 周 | 论证 |

**全部是"我们打算用它"，没有一句"我们怎么用它"。**

### 1.2 缺失的五项落地设计

| # | 缺失 | 后果 |
|---|---|---|
| 1 | **模块映射**——哪个功能调它的哪个 API | 开发时才发现 API 不匹配，返工 |
| 2 | **能力缺口清单**——它没有的东西 | 误以为"模型层全有了"，实际要补 40% |
| 3 | **版本锁定与依赖隔离** | penaltyblog 依赖 Cython 编译，与 Python 版本耦合；升级会连锁 |
| 4 | **维护风险兜底** | 单人维护项目（Martin Eastwood），停更即断供 |
| 5 | **抓取合规边界** | 它自带 FBref/Understat 抓取器，但 ToS 与商用授权是另一回事 |

### 1.3 模块映射（本次补全）

| 我们的模块 | penaltyblog 提供 | 需自建 |
|---|---|---|
| 球队强度估计 | `DixonColes` / `BayesianGoalModel` / `HierarchicalBayesianGoalModel` | 时间衰减调参、跨赛季衔接 |
| 比分矩阵 → 玩法概率 | `predict()` → `home_draw_away`、亚盘、大小球 | 竞彩整数让球映射、总进球/半全场/比分玩法 |
| 去水 | `goal_expectancy` 内置 + overround 解码 | Shin 法（penaltyblog 用的是简单归一化，Shin 需自写或引 mberk/shin） |
| 历史数据 | football-data / FBref / Understat / ClubElo 抓取器 | **官方竞彩 SP 历史**（它没有，必须自采） |
| 回测 | 模型拟合与预测 | walk-forward 框架（用 sports-betting 补）、CLV 计算、影子模式、模型版本管理 |
| 校准 | ❌ 无 | isotonic / 分联赛分桶（sklearn 补） |
| 融合权重 | ❌ 无 | logit 空间加权 + 每季重估（自写） |
| 实时赔率 | ❌ 无（历史库） | The Odds API / 商业源 |
| 阵容伤停 | ❌ 无 | API-Football |
| 实时比分 | ❌ 无 | 商业 live feed |

**结论：penaltyblog 覆盖"建模核心"，约占总工作量的 35%，不是 80%。** Review v2.0 的估算偏乐观，需修正——但它依然值得用，因为省的是最难写的那 35%。

### 1.4 版本锁定与依赖隔离（本次定稿）

```toml
# pyproject.toml
[tool.poetry.dependencies]
penaltyblog = "~=1.13"          # 锁定次版本，禁跨 minor 自动升级
cython = "^3.0"                  # 编译依赖，构建期镜像内固定
# 隔离：模型层作为独立包 packages/model，依赖 penaltyblog；
#       verdict/ingest 等业务模块不直接 import penaltyblog
```

**架构约束**：业务代码只调 `packages/model/predictor.py` 的稳定接口，内部实现可换。这样 penaltyblog 停更/换库，只需重写 200 行适配层。

### 1.5 维护风险兜底

| 风险 | 触发信号 | 兜底 |
|---|---|---|
| 项目停更 | 12 个月无 release | 已在适配层封装，切换 sports-betting 或自写 DC（Cython 版代码已开源可 fork） |
| Cython 编译失败 | Python 大版本升级 | 锁 Python minor 版本于 Docker 镜像；CI 加编译冒烟 |
| 抓取器失效 | 目标站改版 | 核心数据不依赖 scrape：赔率用商业 API、xG 用 FBref 商业导出或自建 |

---

## 二、本次新增的高价值开源项目（6 个）

### P0 · 立即可用

**① betfairlightweight —— 「势」维度的基础设施**

| 项 | 内容 |
|---|---|
| 仓库 | `betcode-org/betfair` (~512★, 22k 月下载) |
| 能力 | Betfair API-NG 完整封装；**历史流文件解析**（`create_historical_generator_stream`），可重建任意时刻的盘口状态、BSP、成交量 |
| 对我们 | **「势」维度的历史数据来源**——之前设计里"3 年分钟级双源快照"是最大数据成本项，现在可用 Betfair 历史流低成本回放 |
| 用途 | M1 或 M2 起，用历史流训练/验证"盘口异动检测"，不必干等一年自采 |
| 许可 | MIT |

**为什么这条最关键**：它把「势」维度从"要等 12 个月积累"变成"可以立刻回测"，直接改变了 Roadmap 的时间表。

**② Pandera —— 赔率管道的数据契约**

| 项 | 内容 |
|---|---|
| 仓库 | `unionai-oss/pandera`（5000 万下载） |
| 能力 | DataFrame schema 校验（类型/范围/统计假设/自定义 check），支持 pandas/polars/pyspark；class-based API 与 Pydantic 同构；lazy validation 一次报全部错 |
| 对我们 | **赔率快照、对齐结果、特征表的强制契约**——这是数据稳定性的最大杠杆 |
| 具体用法 | 每张表一个 `DataFrameModel`：赔率必须 >1.0 且 <1000、概率和 ∈ [1.0,1.2]、captured_at 不得为未来、match_id 必须在 matches 表内、单日记录数不得为 0（空抓取告警） |
| 集成 | FastAPI 入参已有 Pydantic；Pandera 管 DataFrame 层，两者互补 |
| 许可 | MIT |

**为什么这条第二关键**：我们最怕的不是模型不准，是**悄悄抓到了脏数据还在跑**。Pandera 把"静默污染"变成"响亮失败"。

**③ RapidOCR —— 票面识别本地化**

| 项 | 内容 |
|---|---|
| 仓库 | `RapidAI/RapidOCR`（PaddleOCR 模型的 ONNX 轻量版） |
| 对比 | 同一批中文票据：准确率打平；CPU 单张 **0.57s vs PaddleOCR 7.15s**；体积 20MB vs 300MB–2GB；pip 一条命令 |
| 对我们 | **拍票记账（F9）的主引擎**——本地跑，零 token 成本，隐私不出端 |
| 分工调整 | **RapidOCR 做票面字段提取**（场次号/玩法/SP/金额/倍数，结构化，强确定性）；**GLM-4V 只做"推荐截图理解"**（需要语义，OCR 做不了） |
| 注意 | 输出含空格需清洗；长进程内存偏高（约 5.2GB 峰值，需定期重启 worker）；长边 >2000px 先缩放 |
| 许可 | Apache-2.0 |

**为什么这是修正**：原方案把所有图像都喂给 GLM-4V，票面识别用大模型既慢又贵还不稳定。拆开后，票面识别零成本、亚秒级、可离线；只有"聊天截图理解"才走 VLM。

### P1 · 第二阶段引入

**④ soccerdata —— 抓取广度**

`probberechts/soccerdata` (~747★)：统一 DataFrame 输出的抓取器集合，覆盖 ClubElo / ESPN / FBref / FiveThirtyEight / football-data / **FotMob** / **Sofascore** / SoFIFA / Understat / WhoScored，本地缓存、内置限速（FBref 1 req/2s）。

价值：补 penaltyblog 抓取器的覆盖盲区（尤其 FotMob/Sofascore 的中文队名与阵容数据），且列名统一，与 Pandera 契约直接对接。
风险：scrape 类库受目标站改版影响，**只做补充源，不做唯一源**。

**⑤ sports-betting —— 回测框架（已在选型，本次明确用途）**

`georgedouzas/sports-betting` (~823★)：`SoccerDataLoader`、`ClassifierBettor`、backtesting、value bet 预测。用它承担 walk-forward 骨架与 bettor 抽象，我们只写竞彩特有的结算是非逻辑。

**⑥ flumine —— Betfair 策略回测（M2 备选）**

构建在 betfairlightweight 之上，专为交易所策略回测设计。若 M2 走 UK 市场，可复用其撮合/入场逻辑模拟。

### 附：小工具（零成本、即插即用）

| 库 | 用途 |
|---|---|
| `tenacity` | 抓取/API 重试与退避（替代手写 retry） |
| `hishel` / `httpx` 缓存 | 源站响应缓存，降请求量、提升稳定性 |
| `Playwright` | 无 API 站点的兜底抓取（仅备用，不进主链） |
| `Meilisearch` | 球队/场次搜索（中文容错、拼写纠错），替代手写模糊匹配 |
| `pgvector` | 相似历史比赛检索（RAG），替代自建向量方案 |

---

## 三、三个架构修正（本次定稿）

### 修正 1：数据层按"可替换性"分层

```
┌ 契约层：Pandera schema（每张表一个 model，CI 强制）
├ 适配层：source adapter 统一接口 fetch(match_id) → 标准 DataFrame
│   ├ penaltyblog 抓取器（历史）
│   ├ soccerdata（广度补充）
│   ├ betfairlightweight（交易所历史流）
│   ├ 商业 API（实时赔率/阵容/比分）
│   └ 官方竞彩自采（SP/单关/停售）
└ 存储层：Postgres 分区表 + DuckDB（本地回测）
```
**任何源失效只需换 adapter，不动业务代码。**

### 修正 2：图像识别分工

| 任务 | 引擎 | 理由 |
|---|---|---|
| 票面字段提取 | **RapidOCR（本地）** | 结构化、确定性、零成本、亚秒 |
| 推荐截图理解 | GLM-4V | 需语义（读懂"稳胆""让半一"这类话） |
| 赛程/比分截图 | RapidOCR → 匹配库 | 同上 |

### 修正 3：「势」维度数据来源改为双路

| 路 | 来源 | 时点 |
|---|---|---|
| **历史回放** | betfairlightweight 历史流 + football-data 开盘/收盘 | **W1 即可做**（不用等） |
| **实时自采** | The Odds API + 官方竞彩快照 | 上线后持续积累 |

这直接修正了原方案"势维度要等 12 个月"的排期假设。

---

## 四、修正后的省时账

| 项 | 原估算 | 修正 | 依据 |
|---|---|---|---|
| 模型层（penaltyblog） | 省 2–3 周 | **省 2–3 周**（覆盖 35%，不是 80%） | §1.3 |
| 数据校验（Pandera） | — | **新增省 1 周** + 大幅降事故率 | 新增 |
| 票面 OCR（RapidOCR） | GLM-4V，¥0.02/次 | **省 ¥/次 + 提速 10 倍** | 新增 |
| 「势」维度历史数据 | 等 12 个月自采 | **省 12 个月** | betfairlightweight |
| 抓取广度（soccerdata） | 自写 3 个爬虫 | 省 1 周 | 新增 |
| 搜索（Meilisearch） | 手写模糊匹配 | 省 3 天 | 新增 |
| **合计** | | **净省约 5 周 + 12 个月数据债** | |

---

## 五、风险清单（新增）

| 风险 | 影响 | 应对 |
|---|---|---|
| penaltyblog 停更 | 模型层断供 | 适配层隔离 + 可 fork（Cython 源码开源） |
| scrape 库因站改版失效 | 数据缺口 | 核心数据走商业 API，scrape 只做补充 |
| RapidOCR 内存泄漏 | worker 崩溃 | 定时重启 + 单次批处理上限 |
| Pandera 校验过严 | 正常数据被拦 | 分两级：ERROR（阻断）/ WARN（记录告警），灰度调阈值 |
| Betfair 历史流需账户 | 无法获取 | 需注册 + 购买历史包；提前评估成本 |
| 依赖膨胀 | 构建慢、冲突 | 模型层独立包；CI 矩阵锁 Python minor |

---

## 六、需要落进 TechSpec 的补丁（已执行）

1. §1 选型表：penaltyblog 备注改为"覆盖建模核心约 35%，配适配层"
2. §8 模型层：新增模块映射表、能力缺口清单、版本锁定、适配层约束
3. §1/§10：新增 betfairlightweight / Pandera / RapidOCR / soccerdata / Meilisearch
4. §3.2 组件：OCR 分工调整（票面 RapidOCR / 语义 GLM-4V）
5. §13 排期：W1 增加 Pandera 契约 + betfair 历史流评估
6. 新增附录：数据源适配层接口定义

---

## 附：本轮开源全景（最终版）

| 层 | 项目 | 许可 | 状态 |
|---|---|---|---|
| 建模 | penaltyblog | MIT | 已选，本次补落地设计 |
| 回测 | sports-betting | MIT | 已选，明确用途 |
| 交易所 | betfairlightweight | MIT | **新增 P0** |
| 抓取 | soccerdata | MIT | **新增 P1** |
| 校验 | Pandera | MIT | **新增 P0** |
| OCR | RapidOCR | Apache-2.0 | **新增 P0** |
| 搜索 | Meilisearch | MIT | 新增 P2 |
| 向量 | pgvector | PostgreSQL | 新增 P2 |
| Auth | Supabase | Apache-2.0 | 已选 |
| 订阅 | RevenueCat | 商业 | 已选 |
| 埋点 | PostHog | MIT | 已选 |
| 推送 | JPush / Expo | 商业/开源 | 已选 |
| 客服 | Chatwoot | MIT | 已选 |
| 邮件 | Listmonk | AGPL | 已选 |
| 社媒 | Postiz | AGPL | 已选 |
| 编排 | n8n / Activepieces | fair-code / MIT | 已选 |
| LLM 观测 | Langfuse | MIT | 已选 |
| 监控 | uptime-kuma + Sentry | MIT/商业 | 已选 |

*Review v1.0 完*
