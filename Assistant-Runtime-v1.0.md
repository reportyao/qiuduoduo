# 解球 · AI 助理运行时 v1.0

> 范围：主动监控、推送、用户记忆、助理交互，以及与现有文档 / 后端 / 管理后台的对照。
> 关联：`PRD-v5.1.md` F13/F19/F21/F22 + §5.2 推送矩阵；`TechSpec-v2.1.md` §4/§5/§8；`Intelligence-Layer-v1.0.md`；`Release-plan-v1.1.md` W5/W6。
>
> 状态：设计与差距分析。现有后端已具备判决/修订/记忆/下注/聊天/周报/控制台；监控、推送、收件箱、派生记忆、AI 分析尚未实现。
>
> **平台范围（2026-11-03 定）：MVP 只做 Android；iOS/APNs 与 Global/FCM 延后。**

---

## 0. 结论

性价比最高的路线不是“全能 Agent”，而是：

> **事件驱动监控 + 规则推送 + 结构化记忆 + 少量 LLM 润色**

- 规则决定“监控什么、推给谁、什么时候推”；
- LLM 只负责把事件写成一句像助理说的话，按事件缓存；
- 记忆先用结构化表，不上向量库；
- MVP 只做 Android + 站内信 + JPush；iOS 后补。

---

## 1. 助理能力地图与当前状态

| 能力 | 说明 | 当前状态 | 差距 |
|---|---|---|---|
| **感知** | 监控比赛、盘口、阵容、赛程、赛果 | 判决/修订/结算/SP 已有；阵容/伤停未接 | 无 events 表、无监控 worker |
| **理解** | 三关、Dixon-Coles、情报信号 | 三关/模型/修订链已上线；情报信号设计完成未实现 | signals/AI 表未建 |
| **记忆** | 用户偏好、约束、历史、情绪、上下文 | `users.persona`、`memories` 表 + 冲突 409 + 聊天写入已有 | 无派生记忆、无五类、无置信/过期 |
| **表达** | 三套人设、文案、推送文案 | 前端 `T()` 已做；后端 `users.persona` 已持久化 | 推送文案/事件摘要未做 |
| **行动** | 站内信、推送、深链、关注 | 前端本地 follows/通知软请求；后端无 follow/notification/push | 全链路缺失 |
| **反思** | 归因、周报、连败保护 | W6 已上线（归因/周报/保护 423） | 与监控/推送未打通 |

**一句话：理解和反思已有雏形；感知、记忆、行动是短板。**

### 1.1 助理分身（产品视角）

| 分身 | 职责 | 文档 | 现状 | 缺口 |
|---|---|---|---|---|
| **盘口哨兵** | 盯 SP 异动、抽水变化、多源分歧 | PRD F15 / §5.2 | 前端“资金异动”演示卡；后端无监控 | events + 阈值 + 推送 |
| **纪律管家** | 连败保护、休息日、自排除、预算提醒 | PRD F11/F14 | 后端 discipline/rest/423 保护已上线；前端有入口 | 主动提醒/推送未接 |
| **情报官** | 首发、伤停、轮换、赛程密度 | TechSpec §8.7 | 设计完成；前端情报 UI 演示 | signals 表 + API-Football |
| **复盘官** | 赛后归因、周报、CLV | PRD F12 / W6 | W6 已上线归因/周报/复盘卡 | 与推送/记忆打通 |
| **陪看** | 实况卡、进球/红牌、走盘 | PRD §5.4 | 前端实况演示；无 live feed | 实时比分源 + 静默推送 |
| **选比赛** | 点形象→当日全量列表→快速进入 | PRD F22 | 前端已做简化版；后端无全量 `/matches` | 全量列表 + 分类 chips |
| **对话** | 问成本/查比赛/记事情 | PRD F15 / W6 | 后端 `/chat` + 记忆写入；前端聊天条 | 上下文个性化/记忆检索 |


---

## 2. 与现有文档的对照

| 文档条目 | 要求 | 现状 | 结论 |
|---|---|---|---|
| PRD F13 记忆 | 五类；口述>推断；冲突当场问；可见可删 | `memories` 表 + `/me/memories` + 冲突 409 + 聊天写入；前端可删 | **部分完成**：缺派生记忆、五类、置信/过期 |
| PRD F19 人设 | 三套人设、即选即换、通知中性 | `users.persona` + `PATCH /me` + 前端 `T()`/形象 sprite | **基本完成**：推送文案未接人设 |
| PRD F21 关注 | 详情关注开关、实况卡、终场推送 | 前端 `S.follows` 本地；后端无 follows 表/接口 | **未完成** |
| PRD F22 吉祥物选比赛 | 点大头像→分类 chips→点场次→卡入流 | 前端已做简化版（点击形象出 6/12 场列表） | **部分完成**：后端无全量 `/matches`，无分类 |
| PRD §5.2 推送矩阵 | 终场/结算/结论/拦截/未决；过程不推；静默时段 | 文档完整；代码无 events/notifications/push | **未完成** |
| PRD §5.3 两级时序 | 终场 T+2min、结算 T+2h、结论 T-3h、T-30m 未决 | 无调度/推送 worker | **未完成** |
| TechSpec 推送 | JPush CN + Expo Global；静默推送 | 仅文档；无 token/推送适配 | **未完成**，MVP 只做 Android/JPush |
| TechSpec §8.7/8.8 | 情报层 + AI 研判层 | 仅设计；无 signals/ai_analyses/ai_jobs | **未完成** |
| Release W5 | 推送/实况卡/关注/连败保护 | 认证/连败保护已上线；推送/实况/关注未做 | **部分完成** |
| Release W6 | 归因/记忆/卡片路由/非比赛日 | 已上线 | **完成** |

---

## 3. 与现有后端的对照

### 已具备、可直接复用

| 资产 | 位置 | 用途 |
|---|---|---|
| `verdict_revisions` / `chain_*` | `models.py` / `sealchain.py` | 结论变化事件源；修订去噪 |
| `Verdict` / `gates` | `verdict.py` | 状态 promoted/pending/killed，事件 payload |
| `Bet` | `models.py` / `w6.py` | 用户下注关系、结算/复盘对象 |
| `Memory` | `models.py` / `users.py` | 显式记忆；可扩展 category/confidence/expires |
| `User.persona/display_name/discipline_on/rested_until/odds_format/locale/region` | `models.py` | 人设、设置、纪律 |
| `w6` 聊天/记忆/下注/周报/归因 | `routers/w6.py` | 助理对话、记忆写入、复盘 |
| `settle.py` | 模块 | 赛果同步、结算、ledger |
| `console/alerts` | `routers/console.py` | 运维告警；可扩展事件/推送 |
| `w4` SSE narration | `routers/w4.py` | 站内事件流可复用 SSE 模式 |
| 认证/JWT/设备令牌 | `auth.py` / `auth_w5.py` | 推送 token 绑定用户 |

### 缺失、必须新建

```text
watch_targets     用户关注：match / team / league + 事件偏好 + 静默时段
events            监控事件：type/severity/match_id/payload/dedupe_key
notifications     站内信/推送队列：user_id/event_id/channel/status/scheduled_at
push_tokens       Android JPush registration_id / 设备信息 / enabled
user_events       行为日志：view/click/buy/dismiss/search/chat
```

`memories` 需扩展：

```text
category      preference / constraint / history / emotion / context
confidence    0–1
source        user / derived
expires_at    派生记忆衰减
last_used_at  用于排序与清理
```

### 不需要现在做

- Redis / Kafka / Celery：先用 DB 表 + systemd worker，量上来再换。
- 向量库 / pgvector：聊天语义检索后期再加。
- APNs / FCM / 微信服务号：MVP Android 之后。
- 自建推送通道：直接用 JPush。

---

## 4. 与管理后台的对照

现有控制台页面：`/console`（日报）、`/console/alerts`（断链/延迟/源未配）、`/console/variants`（文案变体）、`/console/ops`（运维）。

缺口：

| 页面 | 需要展示 | 优先级 |
|---|---|---|
| `/console/assistant` | 事件流、监控规则命中、通知队列、推送到达/打开/点击、失败重试 | P0 |
| `/console/ai` | AI 分析列表、状态、分歧、成本、失败率、人工复核 | P1 |
| `/console/memory` | 记忆写入统计、冲突/删除/投诉、异常推断 | P1 |
| `/console/push` | 设备 token、厂商通道、静默/频控、退订 | P0 |
| `/console/alerts` 扩展 | 事件延迟、推送失败率、队列积压、LLM 失败率 | P0 |

控制台仍只做“异常复核 + 运维”，不做全量人工审核；AI/推送自动发布为主。

---

## 5. 目标架构

```text
 ingest / verdict / settle / signals
                ↓
          events（去重、优先级、过期）
                ↓
   monitor_worker（每分钟）→ 只生成“值得说”的事件
                ↓
   fanout：watch_targets + bets → notifications
                ↓
   ┌───────────────┬────────────────┐
   │ 站内信 inbox   │ JPush（Android）│
   └───────────────┴────────────────┘
                ↓
   user_events（打开/点击/忽略/下注/聊天）
                ↓
   memory_worker（规则推导 + 衰减）
                ↓
   memories → 排序/文案/聊天上下文
                ↓
   LLM（事件摘要/人设改写；按 event 缓存）
```

### Worker 形态

- `app.assistant_worker` 单进程循环，systemd 常驻；
- 每分钟：生成事件 + 扇出通知；
- 每 30 秒：发送待推送；
- 每小时/每日：记忆推导与衰减；
- 失败重试 3 次，写 `notifications.status/last_error`；
- 不阻塞 API；推送失败不影响判决发布。

---

## 6. 监控：MVP 只做 4 类

| 优先级 | 事件 | 触发 | 数据 | 推送 |
|---|---|---|---|---|
| P0 | 结论变化 | 新修订：概率 >1pp / pick 变 / 状态翻转 | `verdict_revisions` | 关注/下注用户 |
| P0 | 停售提醒 | 关注/下注比赛 T-10min | SP 快照 | 一次 |
| P1 | 结算+归因 | 下注比赛出赛果 | `settle` | 一次 |
| P1 | 每日简报 | 固定 19:00（可配） | 当日统计 | 每天最多 1 |
| P2 | 首发/伤停 | 官方首发/确认缺阵 | API-Football | 关注/下注 |
| P2 | 盘口异动 | 30min SP ≥2pp / 分歧突变 | SP/国际盘 | 关注场 |
| P3 | 关注球队动态 | 赛程/积分/连败 | 赛程/积分 | 每日摘要 |

规则：

- 只对**关注/下注/候选**比赛生成事件；
- `dedupe_key` 唯一，防重复；
- 同一场同一事件 2 小时不重复；
- 每日主动推送 ≤2 条（PRD 守护指标），每日总推送 ≤4；
- 静默 23:30–08:00（拦截类例外，PRD 已定）；
- 多事件合并成一条摘要。

---

## 7. 推送：Android MVP

### 7.1 渠道

| 渠道 | MVP | 说明 |
|---|---|---|
| 站内信 inbox | ✅ | 所有用户可见，不依赖推送权限 |
| JPush Android | ✅ | 华为/小米/OPPO/vivo 厂商通道 |
| APNs / iOS | ❌ 延后 | 需要 Apple 证书 + iOS 构建 |
| FCM / Global | ❌ 延后 | MVP 只做 CN Android |
| 微信服务号 | ❌ 后期 | 认证/模板限制 |
| 短信 | ❌ | 只做登录/安全 |

### 7.2 Android 现实约束

- Android 13+ 需要 `POST_NOTIFICATIONS` 运行时权限；
- 国内厂商杀后台严重，必须走厂商通道，不能只靠 JPush 自建通道；
- 需要 Android 包名、签名、厂商开发者账号、JPush AppKey；
- Expo RN 需要 JPush 原生模块/EAS 构建；Web 测试前端无法验收系统推送；
- 深链：`jieqiu://match/{id}`、`jieqiu://verdict/{id}`；冷启动先入流再定位；
- 锁屏文案不含赔率/投注字样。

### 7.3 推送表

```text
push_tokens
  id, user_id, platform(android), provider(jpush),
  token UNIQUE, app_version, last_seen, enabled

notifications
  id, user_id, event_id, channel(inapp/push),
  status(pending/sent/failed/opened/clicked),
  scheduled_at, sent_at, opened_at, clicked_at,
  dedupe_key UNIQUE
```

---

## 8. 记忆：五类 + 显式优先

### 8.1 五类

| 类型 | 例子 | 来源 | 用途 |
|---|---|---|---|
| 偏好 | 关注曼城、喜欢让球、中文欧赔 | 口述/行为 | 排序、文案 |
| 约束 | 单次 ≤50、预算、自排除 | 口述/设置 | 保护、提醒 |
| 历史 | 近 20 注、命中/未中、关注场 | `bets`/`user_events` | 复盘、上下文 |
| 情绪/状态 | 连败、休息、深夜 | 行为/时间 | 关怀，不做促销 |
| 上下文 | 刚问过哪场、正在看哪场 | 会话/浏览 | 聊天连续 |

### 8.2 规则

- 口述 > 推断；冲突当场问（已有 409 机制）；
- 派生记忆需 ≥3 次观察，带 `confidence`；
- 30–90 天不 reinforcement 自动衰减；
- 记忆页可见、可删、可改；
- 敏感推断（成瘾、负债）不写入、不用于营销；
- 聊天只取最相关 5 条，不整包注入。

### 8.3 派生示例

```text
常关注球队：30 天内 view/follow/bet ≥3 次
风险偏好：最近 20 注均值 + 最大单注
活跃时段：打开/点击时间分布
推送耐受：点击率 / 忽略率；忽略高则自动降频
深水回避：深水场只看不记 / 记录后删除
```

---

## 9. API 草案

```http
GET    /me/inbox?unread=1
POST   /me/inbox/{id}/read
GET    /me/watch
POST   /me/watch          {target_type, target_id, events}
DELETE /me/watch/{id}
GET    /me/notify-settings
PUT    /me/notify-settings {channels, quiet_hours, daily_cap}
POST   /push/register      {platform:"android", provider:"jpush", token}
POST   /push/unregister
GET    /me/memories        （已有）
PUT    /me/memories/{key}  （已有）
DELETE /me/memories/{key}  （已有）
GET    /me/events/stream   （SSE，可选）
```

内部 worker 直接读写 DB，不暴露公网。

---

## 10. 开发难度与排期

| 模块 | 难度 | 工期（1 人） | 依赖 |
|---|---|---|---|
| events/notifications/watch/push_tokens 表 | 低 | 2–3 天 | 无 |
| monitor_worker + 4 类监控 | 中 | 5–7 天 | 现有 verdict/settle |
| 站内信 inbox + 红点 | 低 | 3–4 天 | 表 |
| 关注 API + 设置页 | 低 | 3–4 天 | 表 |
| JPush Android + token + 深链 | 中高 | 5–8 天 | Android 包/厂商账号 |
| 记忆扩展 + 派生规则 | 中 | 5–7 天 | `user_events` |
| 记忆页/通知设置前端 | 低 | 3–4 天 | API |
| 控制台 assistant/push 页 | 中 | 4–6 天 | 表 |
| LLM 事件摘要/人设改写 | 低 | 2–3 天 | provider |
| 总 MVP（Android） | — | **4–6 周** | — |

---

## 11. 分期

### P0（Android MVP，4–6 周）

- 表：events / notifications / watch_targets / push_tokens / user_events；
- 4 类监控：结论变化、停售、结算、每日简报；
- 站内信 + 红点 + 关注管理 + 通知设置；
- JPush Android + 厂商通道 + 深链；
- 控制台：事件/推送队列/失败告警；
- 只做 Android，iOS 不做。

### P1（2–3 周）

- 派生记忆 + 五类 + 记忆页；
- 人设同步到推送文案；
- 吉祥物选比赛接入全量 `/matches`（分类 chips）；
- 推送频控/静默/合并调优。

### P2（2–3 周）

- 首发/伤停、盘口异动监控；
- AI 事件摘要 + 人设改写（按事件缓存）；
- AI 分析层（signals/ai_analyses/ai_jobs）+ 控制台复核/成本；
- 周报/复盘与推送打通。

### P3

- iOS/APNs、Global/FCM；
- pgvector 语义记忆；
- 微信服务号；
- 多语言/多区域。

---

## 12. 指标与红线

### 指标

- 推送到达率 ≥95%；
- 打开率 ≥15%；
- 关通知率 ≤15%；
- 每日主动推送 ≤2，总推送 ≤4；
- 未读清空率 ≥50%；
- 事件生成延迟 <2min；
- 记忆删除/投诉率 <1%；
- 推送点击→详情转化。

### 红线

- 不推送“快买/稳赚/回本”；
- 锁屏不含赔率/投注字样；
- 夜间静默；
- 未关注不推过程事件；
- 连败/亏损只做关怀，不做促销；
- 记忆可见可删；敏感推断不落库；
- 推送可一键关闭。

---

## 13. 现有文档需要同步的点

1. **平台范围**：TechSpec/PRD 的 Global/iOS 推送条目标注“MVP 延后”，先 Android/JPush。
2. **F21 关注**：补后端表/API，不再只存前端。
3. **F22 选比赛**：补全量 `/matches` 与分类 chips；当前 `/stream` 只有 top/watch。
4. **F13 记忆**：补五类、置信、过期、派生；现有 `Memory` 只有 key/value/source。
5. **推送矩阵**：PRD 已有，但 W5 未实现；按本文 P0 落地。
6. **AI 分析**：TechSpec §8.8 设计完成，后端表/worker/控制台未建。
7. **控制台**：新增 assistant/push 页；alerts 扩展事件/推送指标。
8. **冻结基线**：新增路由后重新 adopt，再跑 `/review/checklist`。

---

## 14. 一句话

**Android 先跑通“事件 → 站内信/JPush → 行为 → 记忆”的闭环；iOS、向量库、微信都往后放。** 这样既像真助理，又不会把 MVP 拖成半年工程。
