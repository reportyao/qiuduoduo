# 球多多 · AI 助理运行时 v1.0

> 范围：主动监控、推送、用户记忆、助理交互，以及与现有文档 / 后端 / 管理后台的对照。
> 关联：`PRD-v5.1.md` F13/F19/F21/F22 + §5.2 推送矩阵；`TechSpec-v2.1.md` §4/§5/§8；`Intelligence-Layer-v1.0.md`；`Release-plan-v1.1.md` W5/W6。
>
> 状态：**P0 后端/管理后台/移动端已接（2026-11-05 更新）**：events / notifications / watch_targets / push_tokens / notify_settings / worker / inbox / 关注 / 通知设置 / 控制台助理/推送页；后端全量 **251 tests passed**（2026-11-05）。Android JPush 真实凭证、派生记忆、AI 分析、真实 live feed/进球提醒仍待接。完整全栈审查（历史快照）见 `docs/reviews/2026-11-04-full-stack.md`。
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
| **感知** | 监控比赛、盘口、阵容、赛程、赛果 | 判决/修订/结算/SP + events/monitor worker 已实现；API-Football 阵容/伤停/积分榜已接（默认关闭），尚未形成助理规则/事件 | 盘口异动/阵容规则待接 |
| **理解** | 三关、Dixon-Coles、情报信号 | 三关/模型/修订链已上线；情报信号设计完成未实现 | signals/AI 表未建 |
| **记忆** | 用户偏好、约束、历史、情绪、上下文 | `users.persona`、`memories` + 冲突 409 + category/confidence/expires 字段已有 | 无派生记忆/五类推导/记忆检索 |
| **表达** | 三套人设、文案、推送文案 | 前端 `T()` + 后端 persona + 中性推送模板已做 | chat 未读 persona；事件摘要未做 |
| **行动** | 站内信、推送、深链、关注 | watch_targets / inbox / notify_settings / push_tokens / events / notifications + worker + JPush dryrun 已实现；移动端 inbox/关注/设置已接 | 真实 JPush 凭证未配 |
| **反思** | 归因、周报、连败保护 | W6 已上线（归因/周报/保护 423） | 与监控/推送未打通 |

**一句话：理解和反思已有雏形；感知、记忆、行动是短板。**

### 1.1 助理分身（产品视角）

| 分身 | 职责 | 文档 | 现状 | 缺口 |
|---|---|---|---|---|
| **盘口哨兵** | 盯 SP 异动、抽水变化、多源分歧 | PRD F15 / §5.2 | events/worker 已实现；SP 异动规则未接 | odds monitor + 阈值 |
| **纪律管家** | 连败保护、休息日、自排除、预算提醒 | PRD F11/F14 | 后端 discipline/rest/423 保护已上线；前端有入口 | 主动提醒/推送未接 |
| **情报官** | 首发、伤停、轮换、赛程密度 | TechSpec §8.7 | API-Football fixtures/lineups/injuries/standings 已接（默认关闭）；前端有情报 UI | signals 表 + 情报规则/事件 |
| **复盘官** | 赛后归因、周报、CLV | PRD F12 / W6 | W6 已上线；settled 事件已接 | 推送/记忆打通 |
| **陪看** | 实况卡、进球/红牌、走盘 | PRD §5.4 | 前端实况演示；无 live feed | 实时比分源 + 静默推送 |
| **选比赛** | 点形象→当日全量列表→快速进入 | PRD F22 | 前端简化版；stream 有 verdicts/onsale；后端无分类接口 | 分类接口 + 前端接 onsale |
| **对话** | 问成本/查比赛/记事情 | PRD F15 / W6 | 后端 `/chat` + 记忆写入；前端聊天条 | chat 未读 persona；上下文/记忆检索 |


---

## 2. 与现有文档的对照

| 文档条目 | 要求 | 现状 | 结论 |
|---|---|---|---|
| PRD F13 记忆 | 五类；口述>推断；冲突当场问；可见可删 | `memories` + 冲突 409 + 聊天写入 + category/confidence/expires 字段 | **部分完成**：缺派生记忆/五类推导 |
| PRD F19 人设 | 三套人设、即选即换、通知中性 | `users.persona` + `PATCH /me` + 前端 `T()`/形象 sprite | **部分完成**：chat 未读 persona；前端切换未回写后端；推送保持中性 |
| PRD F21 关注 | 详情关注开关、实况卡、终场推送 | `watch_targets` + `/me/watch`、`/matches/{id}/follow` 已实现；移动端已接 | **已完成（关注链路）**；实况实时源仍未接 |
| PRD F22 吉祥物选比赛 | 点大头像→分类 chips→点场次→卡入流 | 后端已有 `GET /matches` 分类接口；移动端首页/在售已接 onsale | **已完成基础链路**：更细的分类 chips 仍可继续扩展 |
| PRD §5.2 推送矩阵 | 终场/结算/结论/拦截/未决；过程不推；静默时段 | events/notifications/worker/JPush dryrun 已实现；未决/T-3h 动态触发未接 | **部分完成** |
| PRD §5.3 两级时序 | 终场 T+2min、结算 T+2h、结论 T-3h、T-30m 未决 | close/final/settled/daily 已有；T-3h 动态/未决未接 | **部分完成** |
| TechSpec 推送 | JPush CN + Expo Global；静默推送 | JPush provider + dryrun + push_tokens 已实现；真实凭证未配 | **部分完成**，MVP 只做 Android/JPush |
| TechSpec §8.7/8.8 | 情报层 + AI 研判层 | 仅设计；无 signals/ai_analyses/ai_jobs | **未完成** |
| Release W5 | 推送/实况卡/关注/连败保护 | 认证/连败保护/推送/关注已上线；`/matches/{id}/live` 只到赛果+SP 快照 | **部分完成**：真实 live feed/进球提醒未接 |
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
| `/admin` 运维页 | `routers/admin_api.py` | 告警/事件/推送聚合 |
| `w4` SSE narration | `routers/w4.py` | 站内事件流可复用 SSE 模式 |
| 认证/JWT/设备令牌 | `auth.py` / `auth_w5.py` | 推送 token 绑定用户 |

### P0 已建（2026-11-03）

```text
watch_targets     用户关注：match / team / league + 事件偏好 + 静默时段
events            监控事件：version/type/severity/match_id/team_id/payload/payload_hash/data_cutoff/dedupe_key/created_at/expires_at
notifications     站内信/推送队列：user_id/event_id/channel/status/attempt/lease_until/provider_msg_id/last_error/scheduled_at
push_tokens       Android JPush：provider/token(unique)/app_version/last_seen/enabled/failure_count
user_events       行为日志：view/click/buy/dismiss/search/chat
notify_settings   事件类型/渠道/静默时段/每日上限/一键暂停
assistant_state   worker 游标：last_revision_id
```

`memories` 已扩展（旧数据默认 preference/1.0）：

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

当前后台是 `/admin`：总览、模型池/用量、人设文案、推荐主链、组合预览、数据源、运维（告警/API-Football/通知/Push/互动）、账号、审计、日志；RBAC（viewer/operator/admin）+ CSRF + 会话撤销 + `admin_audit` 审计。旧 `/console/*` 页面已全部下线，仅 302 到 `/admin`。

缺口：

| 页面 | 需要展示 | 优先级 |
|---|---|---|
| `/admin` 运维页 | 事件流、通知队列、扇出状态（✅ 已实现） | P0 |
| `/admin` 模型用量页 | LLM 用量/预算/缓存（✅ 已实现只读）；AI 分析列表/失败率/人工复核未实现 | P1 |
| `/admin`（规划） | 记忆写入统计、冲突/删除/投诉、异常推断（未实现） | P1 |
| `/admin` 运维页 | 设备 token、推送状态、dry-run/配置状态（✅ 已实现） | P0 |
| `/admin` 运维页 扩展 | 事件延迟、推送失败率、队列积压、LLM 失败率 | P0 |

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
| P0 | 终场快讯 | 比赛终场 T+2min | live/赛果 | 该场一次 |
| P1 | 结算+归因 | 下注比赛出赛果 T+2h | `settle` | 一次 |
| P1 | 未决提醒 | 停售前 90min 打开过且未决定，T-30m | 行为日志 | 一次 |
| P1 | 拦截/避雷 | 用户关注/看过的场次被砍 | `verdict` | 与结论合并 |
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
  token UNIQUE(provider, token), app_version, last_seen,
  enabled, failure_count, last_error

notifications
  id, user_id, event_id, channel(inapp/push),
  status(pending/sending/sent/failed/opened/clicked/suppressed),
  attempt, lease_until, provider_msg_id, last_error,
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
GET    /me/inbox/unread-count
POST   /me/inbox/{id}/read
POST   /me/inbox/read-all
POST   /me/inbox/{id}/click
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

以上除 `/me/events/stream`（未实现）与 `/me/memories`（已有）外均已落地；worker 直接读写 DB，不暴露公网。

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

### P0（Android MVP，4–6 周）· ✅ 后端/控制台已实现（2026-11-03）

- 表：events / notifications / watch_targets / push_tokens / user_events / notify_settings / assistant_state；
- 监控：结论变化、停售、终场、结算、每日简报；
- 站内信 + 红点 + 关注管理 + 通知设置；
- JPush provider（未配置自动 dry-run）+ 深链 + token 生命周期；
- 控制台：事件/通知队列、推送 token/状态、失败告警；
- 只做 Android，iOS 不做；
- **待接**：真实 JPush 凭证/厂商通道、未决 T-30m、真实 live feed/进球提醒、派生记忆/AI 分析。前端 inbox/关注 UI 已接。

### P1（2–3 周）

- 派生记忆 + 五类 + 记忆页；
- 人设仅用于站内信/详情；**推送文案保持中性（PRD F19：通知中性）**；
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
3. **F22 选比赛**：`GET /matches` 分类接口已补；更细的分类 chips/筛选仍可扩展（历史结论保留）。
4. **F13 记忆**：补五类、置信、过期、派生；现有 `Memory` 只有 key/value/source。
5. **推送矩阵**：PRD 已有；P0 事件/扇出/worker 已落地（历史结论“W5 未实现”保留为审计上下文）。
6. **AI 分析**：TechSpec §8.8 设计完成，后端表/worker/控制台未建。
7. **控制台**：新增 assistant/push 页；alerts 扩展事件/推送指标。
8. **冻结基线**：新增路由后重新 adopt，再跑 `/review/checklist`。

---

## 14. 一句话

**Android 先跑通“事件 → 站内信/JPush → 行为 → 记忆”的闭环；iOS、向量库、微信都往后放。** 这样既像真助理，又不会把 MVP 拖成半年工程。


---

## 15. 评审修正（v1.1）

| 问题 | 风险 | 修正 |
|---|---|---|
| **推送人设化与 PRD「通知中性」冲突** | 锁屏出现人设口吻/敏感赛事字样，合规与体验风险 | 推送模板中性；人设只用于站内信、详情、聊天；锁屏不含赔率/投注词 |
| **P0 事件矩阵缺终场/未决/拦截** | 与 PRD §5.2/§5.3 不一致，用户等不到预期通知 | 补齐终场 T+2min、未决 T-30m、拦截/避雷；P0/P1 分清 |
| **无 outbox / 幂等 / 租约** | worker 崩溃导致重复推送或丢推送 | `notifications` 增加 `sending/lease_until/attempt/provider_msg_id`；发送前后状态机 + 幂等 key |
| **事件无版本/来源/截止时间** | 同一修订重复、跨日 dedupe 冲突、无法回放 | `events` 增加 `version/source/data_cutoff/payload_hash` |
| **无 token 生命周期** | 卸载/换机/多设备导致无效推送、到达率下降 | `push_tokens` 唯一 `(provider, token)`、`failure_count`、失效清理；登录/登出绑定解绑 |
| **无偏好中心** | 无法按事件类型/时段/渠道关闭，容易关通知 | `notify_settings`：事件类型、渠道、静默时段、每日上限、一键暂停 |
| **文案依赖 LLM** | 幻觉数字/赔率/承诺，合规风险 | 推送用确定性模板 + payload 白名单；LLM 只做站内摘要，不写数字 |
| **扇出无批量/索引/积压策略** | 用户量上来后 worker 慢、重复插入、队列堆积 | `(user_id,event_id,channel)` 唯一；批量 insert；索引；TTL；死信 |
| **无到达/打开观测** | JPush 接收≠送达，无法判断质量 | 厂商回执 + 深链打开/点击 + 站内已读；按事件类型统计 |
| **冷启动无关注用户收不到** | 新用户觉得“什么都没发生” | 每日简报 + 引导关注 1 场；无关注也能收到 1 条日报（可关） |
| **记忆表只有 key/value/source** | 无法表达五类/置信/过期 | 扩展 `category/confidence/expires_at/last_used_at`；派生需 ≥3 次观察 |
| **Android 细节不足** | 权限/厂商通道/冷启动深链失败 | `POST_NOTIFICATIONS`、厂商通道、token 刷新、深链冷启动路由、通道分级 |

### 修正后的推送红线

- 每日**主动**推送 ≤2；终场/结算是用户预期内的事务消息，单独计数但也要合并。
- 静默 23:30–08:00（PRD）；拦截类例外仅限已关注/已下注。
- 推送文案只用模板槽位，数字必须来自 payload；不出现“买/注/赔率/推荐/稳赚”。
- 任何推送都可一键关闭；连续忽略自动降频。

---

## 16. 插件化边界：建议「模块化单体 + 扩展点」，不要做插件框架

### 结论

**现在不建议做通用插件系统（动态加载、第三方插件市场、独立生命周期）。**
建议做**模块化单体 + 明确的 ports/adapters + 注册表**，把“可替换的东西”插件化，把核心业务焊死。

### 应该插件化的（扩展点）

| 扩展点 | 实现 | MVP |
|---|---|---|
| 数据源 | `DataSourceAdapter`：sporttery / the-odds-api / football-data / Understat / API-Football / Open-Meteo | 先内置，接口统一 |
| 推送渠道 | `PushProvider`：inapp / jpush /（后续 apns/fcm/wechat） | inapp + jpush |
| 监控规则 | `MonitorRule`：verdict_change / close / settlement / daily / lineup / odds | 4 条 |
| LLM 提供方 | `LLMProvider`：GLM / DeepSeek / OpenAI-compatible | 1 主 + 1 备 |
| 记忆推导 | `MemoryDeriver`：favorite_team / risk / active_hours / push_tolerance | 3–4 条 |
| 文案渲染 | `Renderer`：事件类型 × 渠道（站内/推送），模板 + 槽位 | 模板优先 |

### 不要插件化的（核心）

- 三关/判决/修订/封存链；
- 认证/权限/计费；
- 数据库 schema 与迁移；
- 合规扫描/禁用词；
- 管理后台权限与审计。

这些一旦允许插件改写，审计和合规会失控。

### 接口形态（Python Protocol）

```python
class PushProvider(Protocol):
    name: str
    def send(self, token: str, msg: PushMessage) -> PushResult: ...

class MonitorRule(Protocol):
    name: str
    def detect(self, ctx: MonitorContext) -> list[EventDraft]: ...

class DataSourceAdapter(Protocol):
    name: str
    def fetch(self, ctx: FetchContext) -> list[RawRecord]: ...
```

注册表 + 配置启用，不做 `importlib` 扫目录：

```python
PUSH_PROVIDERS = {"inapp": InAppProvider, "jpush": JPushProvider}
MONITORS = {"verdict_change": VerdictChangeMonitor, ...}
```

配置：

```text
JQ_PUSH_PROVIDERS=inapp,jpush
JQ_MONITORS=verdict_change,close,settlement,daily
JQ_LLM_PROVIDER=glm
```

### 为什么不做通用插件框架

1. **当前只有一个团队、一个部署单元**，插件隔离收益低；
2. 动态加载带来安全、版本、依赖、迁移、调试成本；
3. 推送/监控的复杂度在**规则与投递语义**，不在“插件运行时”；
4. 现有 `app/modules` 已经模块化，加 registry 就够；
5. 真需要第三方扩展时，再把 registry 升级为 entry points/独立进程。

### 什么时候再考虑真插件化

- 有外部开发者/第三方数据源接入；
- 多租户需要各自启用不同规则；
- 单个适配器需要独立部署/独立扩缩容；
- 插件需要独立权限/计费/审计。

到那时再把 `PushProvider`/`DataSourceAdapter` 抽成独立进程或 entry points，不用现在付这个成本。


---

## 17. 代码评审记录（2026-11-03）

> 以下是当时的实现快照，文中 `157 passed` 为 2026-11-03 数值；当前全量测试为 **251 passed**（2026-11-05），全栈修复历史见 `docs/reviews/2026-11-04-full-stack.md`。

> 本节是评审当时（P0 开发前）的记录；已修复/已实现项见 §18。

### 17.1 评审范围

- 后端：`app/models.py`、`app/routers/w6.py`、`app/modules/users.py`、`app/modules/chat.py`、`app/modules/messaging.py`、`app/routers/api.py`、`app/routers/admin_api.py`、`app/main.py`；
- 测试：`python -m pytest -q`，**251 passed（当前）**（修复 6 个墙钟依赖后）；
- 管理后台：`/admin`、`/admin` 运维页、`/admin`（旧变体页已删除）、`/admin/ops`。

### 17.2 已确认可用

| 能力 | 证据 |
|---|---|
| 认证/JWT/refresh/设备令牌 | `auth.py` + `auth_w5.py`；生产 fail-loud |
| 人设持久化 | `users.persona` + `PATCH /me`（zhuanjia/laopao/meng 校验） |
| 记忆冲突 | `Memory` 唯一键 + `upsert_memory` 冲突 409；聊天写入 |
| 下注/连败保护/休息/周报/归因 | W6 已上线；423 + confirm |
| 判决/修订/封存链 | `Verdict` / `VerdictRevision` / `sealchain` |
| 流接口 | `/stream` 返回 verdicts/watch/onsale/avoid + 缓存 |
| 控制台登录 | 密码 + IP 白名单 + 5 次锁 10 分钟 + 会话 TTL |
| 测试 | 157 passed（审计/契约/W2–W8 + assistant 8） |

### 17.3 评审发现

| 级别 | 问题 | 影响 | 建议 |
|---|---|---|---|
| **P1** | `chat.respond` 没有读取 `user.persona`，聊天文案不随人设变化 | F19 只在 UI 层生效，跨端/通知不一致 | 在 `respond` 输出前加 persona 渲染层；规则意图不变 |
| **P1** | 前端 `personaSet` / 资料保存只写 localStorage，不调用 `PATCH /me` | 换机/多端人设、昵称丢失；后端字段空转 | 登录态下同步 `PATCH /me`（persona/display_name）；头像先本地 |
| **P1** | `Memory` 只有 key/value/source | 无法表达五类、置信、过期、派生 | 扩展 `category/confidence/expires_at/last_used_at`；迁移兼容 |
| **P1** | 无 follows 表/API | F21 无法跨端；实时卡/终场推送无对象 | 新建 `watch_targets`（match/team/league） |
| **P1** | 无 events/notifications/push_tokens/notify_settings | 主动推送全链路缺失 | 按本文 P0 建表 + worker |
| **P1** | 控制台无 assistant/push/AI/memory 页 | 无法看事件、队列、到达、AI 成本 | 新增 `/admin` 运维页、`/admin` 运维页、`/admin` 模型用量页 |
| **P1** | 控制台 token 走 URL/表单 query；cookie 未设 `Secure/SameSite`；POST 无 CSRF token；变体页未转义队名 | 令牌进日志/Referer；后台被 CSRF/存储型 XSS 的风险 | 改用 HttpOnly+SameSite=Strict+Secure cookie；去掉 URL token；加 CSRF；`html.escape` |
| **P2** | `_VARIANT_POOL` 进程内存，重启丢失 | 运营标记不可持久 | v1.5 落 `narrative_pool` 表 |
| **P2** | `/stream` 有 `onsale`，但前端 `mapStream` 只取 verdicts/watch/avoid | 吉祥物选比赛少一类数据源 | `mapStream` 接 `onsale`；或建 `/matches` 分类接口 |
| **P2** | `app.main` 版本字符串仍是 `0.7.0-w7` | 版本展示/排障不一致 | 升到 w8/实际版本 |
| **P2** | 6 个测试依赖墙钟：21:55 后 `future_kickoff` 落到次日 21:55，超出竞彩日窗口 | 夜间跑测试误报 rest_day/0 场 | 已修：`future_kickoff` 回落到次日 02:00；157 passed |

### 17.4 本次实际修复

- `tests/conftest.py::future_kickoff`：过期时不再“同日时刻 +1 天”，改为**次日 02:00**，保证落在 `当日 00:00–次日 04:59` 的竞彩窗口内；
- `tests/test_w2_gaps.py::_seed_n`：固定“次日 02:00”种子，避免 21:30 后漂移；
- 结果：`157 passed`（新增 assistant 8 项；原 149 项全保留）。

### 17.5 结论

- 现有后端/控制台**基础扎实**：认证、判决、修订、记忆冲突、下注/保护、周报/归因、封存链、限流、控制台防爆破都已可用；
- 距离“AI 助理运行时”还差的是**行动层**（follows/events/notifications/push）和**记忆扩展**；
- 不建议为了这些重写架构；在现有模块化单体上加 `app/assistant/` + registry 即可；
- 控制台安全项（token/CSRF/XSS）建议在接外部运营前修掉。


---

## 18. P0 实现记录（2026-11-03）

### 已落地

| 层 | 内容 |
|---|---|
| 表 | `events` / `notifications` / `watch_targets` / `push_tokens` / `notify_settings` / `user_events` / `assistant_state`；`memories` 增 `category/confidence/expires_at/last_used_at` |
| 事件 | `app/assistant/events.py`：payload hash + `dedupe_key` + 幂等写入 |
| 监控 | `app/assistant/monitors.py`：结论变化、停售、终场、结算、每日简报；`last_revision_id` 游标 |
| 扇出 | `app/assistant/fanout.py`：关注/下注关系、静默时段、每日上限、站内信/推送分渠道、唯一约束幂等 |
| 推送 | `app/assistant/providers.py`：`PushProvider` + JPush；未配 `JQ_JPUSH_APPKEY/SECRET` 自动 dry-run |
| Worker | `app/assistant/worker.py`：`--once` / `--loop`；租约、重试、失败计数、token 失效 |
| API | `/me/inbox`、`/me/inbox/unread-count`、`/read`、`/read-all`、`/click`、`/me/watch`、`/me/notify-settings`、`/push/register`、`/push/unregister` |
| 控制台 | `/admin` 运维页、`/admin` 运维页；导航已接 |
| 部署 | `deploy.py` 增加每分钟 assistant worker cron（`JQ_DAILY_BRIEF_HOUR=19`） |
| 隐私 | `purge_expired_deletions` 覆盖 notifications/watch/push/user_events/notify_settings |
| 测试 | `157 passed`（新增 8 项：监控幂等、扇出、inbox、push dry-run、静默/上限、iOS 拒绝、控制台页、删除清理） |

### 部署与验证

- 已部署腾讯云 `43.128.24.244:8100`，后端 `0.8.0-w8+assistant`；
- `JQ_CORS_EXTRA_ORIGINS` 已写入 `deploy.py` 的 systemd unit（避免重部署丢 CORS）；
- 每分钟 assistant worker cron 已安装；
- `/review/freeze` 重新 adopt：**79 路由，clean**；
- 生产 smoke：设备登录 → 关注比赛 → 推送注册 → 事件 → 站内信 → 点击深链 → push dry-run `sent`；
- 前端实时模式：`/stream` 12 场，吉祥物选比赛 12 行；
- 前端 persona/display_name 在 JWT 登录态下同步 `PATCH /me`；prod 设备登录关闭时不会触发（符合安全策略）。

### Monorepo 重构启动（2026-11-04）

- 新增 `AGENTS.md`、`docs/architecture.md`、ADR-0001/0002/0003、`justfile`、`docker-compose.yml`；
- assistant 已迁移为后端 feature slice：`app/features/assistant/`，旧 `app/assistant` 移除；
- 新增 `apps/mobile`：Expo RN + TypeScript + Expo Router + TanStack Query 基座；
- 新增 `packages/api-client`：OpenAPI 生成契约占位与运行时 client；
- 新增 Alembic scaffold 与 Postgres Compose；
- 全量测试 `157 passed`；
- 下一步：Alembic baseline、`services/api/` 目录迁移、mobile 核心页面接入真实接口。

### 仍需 P1/P2

- 前端接 `/me/inbox`、`/me/watch`、`/me/notify-settings` 的 **UI**（persona/display_name 同步已接）；
- 真实 JPush AppKey/Master Secret + Android 厂商通道 + 深链冷启动；
- `chat.respond` 读取 persona；前端 `PATCH /me` 同步人设/昵称；
- 派生记忆（favorite/risk/active_hours/push_tolerance）与五类展示；
- 未决 T-30m、T-3h 动态触发、盘口异动/阵容监控；
- `/admin` 模型用量页、`/admin`（规划）；
- 控制台 token 仍在 URL、POST 无 CSRF token（cookie SameSite/HttpOnly、变体输出转义已修）；freeze baseline 已 adopt。

### 运行

```bash
# 单次（cron 用法）
python -m app.assistant.worker --once

# 常驻
python -m app.assistant.worker --loop --interval 60

# 本地/预发：JPush 未配置时自动 dry-run，不需要真凭证
JQ_DAILY_BRIEF_HOUR=19 python -m app.assistant.worker --once
```


---

## 19. 二次代码评审修正（2026-11-03 夜）

| 问题 | 风险 | 修正 |
|---|---|---|
| `emit_event` 用完整 key 查询、却存截断 160 字符的 key | 超长 dedupe key 会重复插入/返回 None | 查询与存储统一用截断后的 key |
| worker 无 rollback；cron 每分钟可能重叠 | 事务异常后 session 脏；两个 worker 抢同一事件 | `run_once`/loop 加 rollback；`flock` 文件锁防 cron 重叠 |
| JPush 网络/5xx 失败也累计 token 失败并停用 | 一次厂商抖动会误杀正常设备 | 只有明确 token 无效（1011/invalid/registration/not found）才累计/停用 |
| 结算扫描用 CN 时间字符串比 UTC `settled_at` | 最近结算被误过滤（差 8 小时） | 统一转 UTC naive 后比较；新增回归测试 |
| 终场事件只按 home/away 反查判决 | 同对阵历史比赛可能串到旧 `match_id` | 加 result date ±1 天 kickoff 窗口 |
| 通知 title/body/deeplink 可能超列宽 | PostgreSQL 下 insert 失败/截断 | 入队前按 128/512/256 截断 |
| provider 异常可能拖垮 worker | 单条推送异常中断整批 | `send()` 包 try/except 转 `PushResult(False)` |

**历史快照（2026-11-03）仍未修**：控制台 token 在 URL / POST 无 CSRF；`_VARIANT_POOL` 进程内存；chat persona；前端 inbox/关注 UI；真实 JPush 凭证/厂商通道；派生记忆；AI 分析层。

**2026-11-04 更新**：控制台 token 已移出 URL（cookie-only + logout）；前端 inbox/关注/通知设置已接。

**2026-11-05 更新**：后台 CSRF + RBAC（viewer/operator/admin）+ 会话撤销 + `admin_audit` 审计已上线，旧 `/console` 下线、统一 `/admin`；W8 冻结基线已重新采纳（145 路由）。`_VARIANT_POOL` 持久化、真实 JPush、派生记忆/AI 分析仍未完成。

**测试**：`python -m pytest -q` → **251 passed（当前）**。
