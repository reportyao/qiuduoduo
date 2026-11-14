# AI 足球助理 · 专属化/记忆化/助理化 开发方案（盯盘落地篇）

> 2026-11-14。定位升级：从「数据工具」到「专属 AI 足球助理」——它记得用户看过/问过/关注着谁；
> 开赛、进球、终场、数据更新时，像真人助理一样**在对话框里主动发消息**。
>
> **与既有规划的关系**：本方案是 [qiuduoduo-v4-final-plan.md](./qiuduoduo-v4-final-plan.md) 中「助理 Tab = 对话/选场/分析/**盯盘**/复盘/每日战绩」与动作白名单 **`assistant_memory`** 两项既定方向的落地篇；执行层面延伸 [opc-ai-refactor.md](./opc-ai-refactor.md)（"助理负责解释，系统负责跑腿"三原则直接沿用）；感知框架沿用 [mobile-ai-assistant-refactor.md](./mobile-ai-assistant-refactor.md) 的 L1 人格 / L2 节奏 / L3 对话模型（该文 UI 部分已作废，五层感知模型仍有价值）。

---

## 一、现状盘点（本轮代码侦查实证）

### 已有基建——比想象中完整，缺的是"三根接线"

| 能力 | 现状 | 位置 |
|---|---|---|
| 事件管线 | monitors：verdict_changes / **close_soon 临开赛** / **prematch 开赛** / **final 终场** / settlements / daily_brief → Event 表（dedupe_key/payload_hash/data_cutoff 齐全）→ fanout | `app/features/assistant/monitors.py`、`fanout.py` |
| 扇出收件人 | 关注者（WatchTarget）+ 下注者（Bet）；用户偏好过滤：paused / event_types / channels / **daily_cap / quiet hours** | `fanout.py::_recipients` |
| 投递 | Notification：`inapp`（即落）+ `push`（JPush 队列、lease 防重投） | `models.py:1049` |
| 站内信前端 | **完整消费链已存在**：`/me/inbox`、unread-count、read、read-all、click + 消息中心页 | `src/features/inbox/queries.ts`、`app/inbox.tsx` |
| 交互记忆采集 | InteractionEvent（user_id / match_id），白名单事件含 `verdict_viewed`、`focus_select`、`free_text_send` 等——**"看过/问过"数据已在落库** | `models.py:1128`、`features/intel/router.py` |
| 实时数据 | SportmonksLiveState + `sync_live_states`（cron 每 30 分钟，随 sportmonks sync） | `features/board/service.py` |
| 助理人设 | persona + assistant_copy + llm_gateway（fast/deep） | `app/modules/` |
| 助理对话 | 首页对话流 = **本地 AsyncStorage**（v5，60 条上限）；POST /chat 单轮 LLM | `src/features/home/conversation.ts` |

### 用户诉求映射 → 真实缺口

| 诉求 | 现状 | 缺口 |
|---|---|---|
| 记录用户看了哪些比赛 | 数据已在落库（verdict_viewed 等） | 无"记忆化使用"——助理不知道也不引用 |
| 数据更新 → 对话框提示 | inapp 管线完整 | ① 通知不进对话框（本地对话流与服务端 Notification 平行世界）② 无 live 数据变化 monitor |
| 开赛主动通知 | **prematch/close_soon 已实现** | 只进消息中心/推送，不进对话框 |
| 进球像真人助理通知 | 无 | 缺 goal monitor + live 抓取 30 分钟太慢 + 对话框注入 |

**核心架构判断：不需要重建系统，缺三根"接线"：**
① 进球/比分变化 monitor 接入现有 Event 管线；② live 抓取按需提频；③ inapp 通知注入助理对话流。

---

## 二、方案：三期，每期独立可上可回滚

### P0 · 打通「对话框 = 助理的嘴」（核心闭环，~1.5 天）

1. **后端 · 新 monitor `scan_live_updates`**（`monitors.py`，接入现有 `run_monitors`）
   - 扫进行中的 SportmonksLiveState（state ∉ FT/AET/PEN/FINISHED）；
   - 复用 monitors 现有 `_get_state/_set_state` 状态存储对比：
     - 比分变化 → `Event(type="goal", payload={score, minute, scorer})`，
       `dedupe_key = f"goal:{match_id}:{minute}:{score}"`（防重放，含补时 45+2 等场景）；
     - 未开始 → 1H → `Event(type="kickoff")`；
     - 红牌（type_id=20）→ `Event(type="red_card")`；
   - fanout 自动接管（收件人/偏好/免打扰/日上限全复用现有 `_recipients`）。
2. **后端 · live 抓取按需提频**（`worker.run_once` 每分钟心跳已有，不新增 cron）
   - worker 检测「进行中 且 有 watch/bet/交互收件人」的比赛 → 限流调 `sync_live_states(force=True)`；
   - 节流：monitors 状态存储记 `live:last_fetch`，≥45s 才真正拉取；无进行中比赛零调用。
   - **配额事实**（opc-ai-refactor）：订阅 = Growth 27/30 + 4 specials（试用至 2026-11-25，后 €197/月）。Growth 档含 live scores；提频后峰值 ≈ 60 次/小时/比赛日，需在 P0 上线前用当前订阅实测每分钟限额（预留 env `JQ_LIVE_POLL_SECONDS` 调节开关）。
3. **前端 · 对话流注入**（`useHomeConversation`）
   - 打开对话/首页时拉 `/me/inbox` 未读 inapp；
   - 新 Notification 渲染为「助理气泡」（kind=assistant-push，带 deeplink 点击直达详情）；
   - AsyncStorage 记已注入 notification id 集合防重复；拉取即标 read（未读红点留在消息中心）。

**P0 验收**：关注一场比赛 → 开赛/每球/终场各在对话框收到助理气泡（延迟 ≤1 分钟），点击直达详情；未关注场次的比赛不收到（专属化边界）。

### P1 · 专属记忆（~2.5 天）

1. **`GET /assistant/memory`**：聚合最近 N 天 InteractionEvent（看过 x 场 / 问过 y 次 / 关注 z 场）+ WatchTarget + 上次日报时间。
2. **前端「助理记忆」面板**：首页简报或我的页——「你最近看过 / 问过 / 关注着」。
3. **文案引用记忆**：`render.py` 注入用户上下文——「你昨晚关注的英格兰拿下了」；daily_brief 按记忆个性化。
4. **对话服务端化**：新表 `assistant_thread_messages`（user_id / kind=assistant|user / text / deeplink / created_at / read_at）；
   本地 60 条上限 → 服务端线程（换设备不丢、LLM 获得历史上下文、主动消息与用户消息同线程）；迁移策略：本地历史首次上传统一合并。

### P2 · 更"真人"（~2 天）

1. 基于记忆的主动早报：「今天你关注的 3 场已更新；昨晚你预测的 4 场中了 2 场」（daily_brief 接记忆排序）；
2. **球队级关注**（WatchTarget 扩 team_type）；
3. 进球后 LLM 一句话点评（llm_gateway fast，配额开关 + 失败降级为纯比分文案）。

---

## 三、风险与约束

| 风险 | 应对 |
|---|---|
| Sportmonks 配额（live 提频） | 只对「有收件人的进行中比赛」提频；无比赛零调用；`JQ_LIVE_POLL_SECONDS` 调节；P0 上线前实测订阅限额 |
| 进球通知延迟 | ≤1 分钟（worker 每分钟 + 45s 节流）；对比现状 30 分钟 |
| 通知噪音 | 用户偏好体系已在位（goal 纳入 event_types 可单独关闭；daily_cap/quiet hours 复用） |
| 事件准确性 | dedupe_key 含 minute+score；点球(16)/乌龙(15)已计入进球事件（`d96ffd8` 修复）；比分以终场同步为准 |
| 游客（无 user_id） | 通知需要 user_id——关注动作本身已要求设备账户（现有链路）✓ |
| 内容合规 | 助理文案沿用 render.py 中性约束：不出现"买/注/赔率/推荐/稳赚"；不承诺收益 |

---

## 四、工作量与排期

| 期 | 内容 | 工作量 |
|---|---|---|
| P0 | live monitor + 按需提频 + 对话流注入 | ~1.5 天（后端 0.5 / 前端 0.5 / 测试联调 0.5） |
| P1 | memory 端点 + 记忆面板 + 文案引用 + 对话服务端化 | ~2.5 天 |
| P2 | 主动早报个性化 + 球队关注 + LLM 进球点评 | ~2 天 |

---

## 五、明确不做（产品红线）

- 不做无事件闲聊推送——没有值得说的事，助理不说话（真人助理也不刷屏）；
- 不突破用户 daily_cap / quiet hours（偏好是产品红线，goal 事件同样受控）；
- P0 不动对话存储架构（本地注入是过渡方案，服务端化放 P1 一次做对）；
- 不做"保证命中"类话术——文案继续走中性预测口径（产品内容规则 7）。
