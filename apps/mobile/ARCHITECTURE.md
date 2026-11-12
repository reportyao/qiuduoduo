# 球多多 Mobile · 开发与交接说明

面向 Android 先发、iOS 后补的 Expo React Native 生产前端。本文是给后续开发者/AI 的入口：先读这里，再读仓库根 `AGENTS.md` 与 [v4.1 方案](../../docs/qiuduoduo-v4-final-plan.md)。

## 1. 技术栈与原则

- Expo SDK 52 / React Native 0.76.9 / React 18 / TypeScript strict
- Expo Router（文件路由）；TanStack Query（服务端状态）；Zustand（会话/偏好/合规本地状态）
- `@jieqiu/api-client`：只从 `packages/api-client/openapi.json` 快照离线生成，禁止手写接口类型
- 页面只做薄壳；数据适配、领域模型、查询、组件按 feature 分片
- 所有网络响应先经过 `src/domain/*Adapters.ts`，异常形状降级而不是崩溃
- 所有颜色/字号/圆角/动效只从 `src/theme/tokens.ts` 取
- 当前产品结构：**助理 / 比赛 / 计划 / 我的** 4 Tab；计划只展示、不跟单

## 2. 目录

```text
app/                         Expo Router 路由（只做布局与页面组合）
  (tabs)/                    助理 / 比赛 / 计划 / 我的
  plans/[id].tsx             计划详情（Max 看完整 legs）
  membership.tsx             会员与权益（充值按钮是假 UI）
  verdict/[id].tsx           预测完整页
  match/[id].tsx             为什么不推 / 复核中说明
  share/[id].tsx             分享落地页（编号可验）
  tools/*                    计算器 / 串关参谋 / 在售 / 为什么不出
  records/*                  我的记录 / 周报 / 公开账本（已从 Tab 移入“我的”）
  settings/*                 资料 / 人设 / 偏好 / 通知 / 合规 / 记忆 / 隐私 / 关于
  assistant.tsx              AI 对话（modal）
  inbox.tsx / watch.tsx      站内信 / 关注
  auth/login.tsx             手机号验证码登录
  onboarding.tsx             年龄门 + 价值介绍
  minor.tsx / paused.tsx     未成年 / 自排除拦截页
  legal.tsx                  服务说明 / 隐私 / AI 说明
src/
  theme/tokens.ts            设计令牌
  domain/                    领域模型 + 后端响应适配器
  features/                  按业务切片：queries / components / 文案
  components/                全局组件（UI 原语、Header、底栏、BootScreen）
  lib/                       api / errors / format / sessionStorage / navigation / toast / haptics
```

## 3. 路由与入口

| 路由 | 作用 |
|---|---|
| `/` | 读本地年龄状态后分流：onboarding / minor / tabs |
| `/(tabs)` | 助理首页：对话流、HeaderMetrics、每日战绩、聚焦卡、今日预测 |
| `/(tabs)/matches` | 比赛页：在售雷达、筛选、关注、串关入口 |
| `/(tabs)/plans` | 计划页：三种风险、累计模拟收益、当前期、历史期数、Max 门控 |
| `/(tabs)/me` | 我的：会员与权益、我的记录、人设、记忆、技能、纪律、设置 |
| `/plans/[id]` | 计划详情：预算/投入/盈亏/回报率/回撤；Max 才返回 bets/legs |
| `/membership` | 会员权益、当前等级/到期/额度；充值按钮只弹“充值暂未开放” |
| `/records` `/records/weekly` `/records/ledger` | 票单 / 周报 / 公开账本（“我的 → 我的记录”） |
| `/verdict/[id]` | 完整账：三关明细、情报、证据、封存、记一注、关注、分享 |
| `/match/[id]?date=` | 为什么不出预测；404 时明确显示“没有预测记录” |
| `/share/[id]` | 分享落地页：编号=content_hash 前 12 位可验，篡改即暴露 |
| `/tools/parlay` | 串关体检 2.0 + 串关参谋：选腿/体检 `POST /tools/parlay/check`；自动配 `POST /tools/parlay/plan`（未复核预览） |
| `/tools/rake` `/tools/odds` `/tools/stake` `/tools/break-even` | 抽水 / 赔率换算 / 凯利仓位 / 回本线 |
| `/tools/on-sale` `/tools/why-not` | 今日在售、筛选、关注；已砍/复核中列表 |
| `/assistant` | 多轮助理对话（`POST /chat`，带 persona） |
| `/inbox` `/watch` | 站内信 / 关注 |
| `/settings/*` | 资料、人设、偏好、通知、合规、记忆、隐私、关于 |

## 4. v4.1 数据层

### 4.1 首页 HeaderMetrics

`src/features/home/components/HeaderMetrics.tsx` 读两个查询：

- `GET /stats/engine`：`version / uptime_hours / today_data_points / markets / models`；
- `GET /stats/record/summary`：最近 30 天每日战绩。

规则：

- 陪伴时长从当前用户 `created_at` 计算；没有用户时显示中性默认；
- 数据点用后台 `engine_config.data_points_factor` 放大后的展示值；为 0 时显示“今日数据同步中”，不显示 0；
- 只保留一个缓慢闪烁绿点，位于“盘口/模型复审”行；`reduceMotion` 时静止；
- 不点击、不展开；不显示源状态和今日场次。

### 4.2 计划

`src/features/plans/queries.ts`：

- `usePlanSummaryQuery` → `/plans/summary`；
- `usePlanCurrentQuery(risk)` → `/plans/current?risk=`；
- `usePlanHistoryQuery(risk)` → `/plans/history?risk=&limit=`；
- `usePlanCycleQuery(id)` → `/plans/cycles/{id}`；
- `useMembershipQuery` → `/membership/me`。

约束：

- 用户相关 queryKey 必须带 `userId`，并 `enabled: authReady`；
- 计划详情首屏用 `isPending` 骨架，避免登录就绪前闪空态；
- 免费/Pro 的 `locked=true`，不渲染 bets/legs；Max 才显示完整方案；
- 文案固定“模拟方案 / 模拟收益 / 只展示不跟单”，不写真实资金或收益承诺；
- 不足 4 场时后端少做，前端不补假场次。

### 4.3 会员

`app/membership.tsx`：

- 展示当前 tier、到期日、今日额度；
- Pro/Max 价格卡与权益说明；
- 当前 tier 的按钮显示“当前方案”并 disabled；
- 其他按钮只弹“充值暂未开放”，不创建订单、不跳支付 SDK；
- 会员真实开通只在 `/admin` 用户与会员页手动操作。

### 4.4 查询与适配

- 公共数据：`on-sale` / `ledger` / `verdict detail` 无需登录；`stream` 含个人 `you` 块，queryKey 也带 userId。
- 用户数据：`me` / `bets` / `weekly` / `inbox` / `watch` / `notify-settings` / `plans` / `membership` 的 queryKey 都带 `userId`，防止切换账号后串数据。
- 所有需要登录的查询都 `enabled: authReady`；深链冷启动不会在设备身份就绪前打 401。
- 写入后按前缀失效（如 `["bets"]`、`["plans"]`）即可匹配带 userId 的 key。
- 后端大量端点没有强类型 `response_model`，因此使用 `unknown` + `src/domain/*Adapters.ts` 显式映射；新接口优先补 OpenAPI。

### 4.5 时间与 Gate

- 时间：`kickoff/generated_at/data_cutoff` 是中国竞彩时间（按 +08:00 解析）；`sealed_at/created_at/notification.created_at` 是 UTC naive，必须经 `utcIso()` 补 `Z`。
- Gate：列表返回 `"pass"` 字符串，详情返回 `{result:"pass"}` 对象；`gateResult()` 两者都兼容。

## 5. 会话

`src/features/auth/authStore.ts`：

1. 启动读 `jieqiu.session.v1`（native SecureStore，Web/不可用时 AsyncStorage）。
2. 无会话 → `POST /auth/device` 创建游客身份。
3. JWT 到期前 30s 自动 `POST /auth/refresh`；只有 401/403 才结束会话并创建新游客，5xx/429/网络错误保留会话，避免瞬时故障把账号降级成游客。
4. 所有登录/设备登录/刷新都带 `authEpoch`；旧响应不能覆盖新会话。退出单飞并做 2 秒去重，避免多个 410 连环创建游客。
5. 手机号验证码登录会携带 `device_token`，后端把游客的注单/记忆/关注/通知合并到手机号账号（见 `merge_device_account`）。
6. 退出登录必须生成新的游客设备令牌，不能复用已合并的旧令牌。
7. 原生 SecureStore 不再回落明文 AsyncStorage；删除失败会写 tombstone，避免旧账号在重启后复活。
8. 退出时 `resetLocalState` 清理账号级偏好与 `lastDailyRecordDate`，避免下一位设备使用者继承。

## 6. 人设

- `src/features/personas/personas.ts`：三套人设的元数据、样句、所有用户可见文案函数。
- 页面用 `usePersonaContent()`，切换人设时自动重渲染。
- 人设只改语气，不改概率/抽水/三关/封存/合规文本。
- `/assistant` 与首页聊天 mutation 把 `persona` 传给后端；后端 `assistant_copy` 用同一事实包渲染，前端只做离线 fallback。
- 推送文案由后端保持中性；前端不在通知里写队名或赔率。

## 7. 设计系统

`src/theme/tokens.ts`：暖白背景、深墨绿、危险红、琥珀；字号下限 11px；触控目标 44（小按钮/芯片用 hitSlop 补足）。

自定义底栏 `src/components/BottomTabBar.tsx`：React Navigation 默认标签在 390px Web 会把中文裁半行，这里自绘；原生同样使用。

滚动交互：首页 Header 随内容滚动；AI 悬浮头像跨 4 Tab 常驻，滚动时缩小但不消失，点击打开“今日比赛”选择器。计划页与会员页底部预留 TabBar 高度，避免内容被遮住。

## 8. 空态、错误态与合规拦截

- 首页：无数据/非比赛日/全砍/待生成都有独立空态；不假装“今天有好货”。
- 计划：无当前期显示“本期方案还没生成，一般 12:00 前更新”，不显示假 `+0`；累计收益为 0 时显示中性 `¥0`。
- 详情：三关、情报四维、证据逐条、封存自检。
- “为什么不推”：人话标题 + 三关明细 + 再入池条件 + 可折叠技术附录；不透出 `the-odds-api key` 等配置。
- 未成年：只允许公开账本与 legal；根守卫拦截所有其他路由。
- 自排除：本机强制拦截；到期前不可撤销；登录/联网后用 `syncPending` 补写服务端，换设备/重装不能绕过。
- 登录合并：报告合并注数，避免“登录后账没了”。

## 9. 聚焦决策流（前后端已接通）

已实现：

- `src/features/home/focusStore.ts`：`FocusTarget` + Zustand focus；
- `GlobalMatchPicker`、首页 `MatchPickerSheet` 选中后 `setFocus → 关弹层 → 回首页`，不再直接跳详情；
- 首页聚焦区：命中当前 stream 时复用 `VerdictMessage`，未命中时 `FocusPending`；提供“换一场 / 今日全部 / 今日其他”；
- 详情页 `DetailActionBar` 新增“让助理看这场”，设置 focus 后回首页；
- `src/domain/focusAdapters.ts` + `useFocusQuery`/`usePulseQuery`：真实接入 `GET /matches/{id}/focus` 与 `GET /stats/pulse`；
- `FocusPanel`：覆盖分/可深读/缺失源/3 条事实/未知项/不能记注原因；
- 首页 `Metrics` 用服务端 `display.data_points`，`DataStatusSheet` 用真实源状态；在售/选择器接 `coverage` 与“覆盖足”筛选；
- `src/features/telemetry/interactions.ts`：`focus_select`/`action_click`/`free_text_send`/`pulse_open` 上报 `POST /interactions`。

待落地：

- 无聚焦时的“数据脉搏 + 选一场”独立首屏形态；输入框默认收起；
- `intel_items`/`match_coverage`/`pulse_daily` 仍是后续表，LLM 深读解读未接。

完整契约见 [docs/focused-decision-flow.md](../../docs/focused-decision-flow.md)。

## 10. 已知后端缺口（前端不伪造）

- **支付/订单**：无支付渠道；会员页只展示，真实开通在后台手动。前端不得伪造支付成功。
- **多盘口**：Max 的“全市场”按已接入市场逐项开放；大小球/BTTS/半全场数据尚未完整入库，前端不对未接市场画假盘。
- **计划自训练**：当前计划选场是规则 + 现有模型概率；`model_registry/training_runs` 只是脚手架，前端不宣称“自训练模型已上线”。
- **计划提醒/收藏**：未实现；不做跟单、自动记注、代购。
- 推荐主链已接：Today Hero 消费 published snapshot（方向/条件/失效条件/AI 复核徽章），组合页 published 优先、`POST /tools/parlay/plan` 为**未复核预览**（UI 标注“参考·未复核”）。新口径见 [docs/recommendation-product.md](../../docs/recommendation-product.md)。
- 合规已服务端闭环：`/gate/verify`、`/me/under18-lock`、`/compliance/state|self-exclusion|self-assessment`；`useComplianceSync` 启动回填服务端状态（服务端不可用时保留本机已生效的自排除，并在联网后补写）；记注被未成年/自排除/休息中硬拦截。
- 后端已提供 `/matches/{id}/live`，但只展示已同步赛果 + SP 快照，`live_feed:false`，不伪造进球时间线。
- JPush Android 6.3.0 已接入：原生桥上报 registration id，通知设置请求系统权限并显示设备绑定状态；厂商通道与服务端 Master Secret 待配置。
- 详情/首页已有 `goBackOr` 处理深链冷启动返回；新增页面必须复用 `src/lib/navigation.ts`，不要直接 `router.back()`。
- 服务端新目录接口（`/matches`、`/cost`、`/water-rank`、`/calendar` 等）已生成 client，页面可按需接入；当前主要页面仍使用 `/stream`/`/on-sale`。

## 11. 当前验证状态（2026-11-12）

- 后端 **341 passed**；OpenAPI **158 路径 / 174 方法**；Alembic head `20261112_23`。
- 前端 **47 Vitest passed**；typecheck / ESLint 通过；Android Hermes bundle 通过（Metro export）。
- MuMu x86_64 模拟器实测：onboarding/年龄门、首页对话与 HeaderMetrics、比赛、计划、计划详情、我的、我的记录、会员页、聊天。
- 本轮修复：计划腿队名/方向缺失、0 盈亏显示 `+¥0`、会员副标题截断、当前会员按钮、HeaderMetrics 0 数据点、计划页底部遮挡、登录前查询闪烁。
- **未做**：正式 release APK 构建/签名、iOS、真机 JPush 验收、Maestro/E2E。

## 12. 验证命令

```bash
cd apps/mobile
corepack pnpm typecheck
corepack pnpm lint
corepack pnpm test
corepack pnpm exec expo export --platform android --output-dir .export-check --clear
corepack pnpm exec expo install --check
```

后端契约变更后：

```bash
just api-client-generate   # 后端代码 → openapi.json → schema.d.ts
```

MuMu / x86_64 模拟器安装 debug APK 时必须显式 ABI，否则可能装到 arm64 包并在启动时崩：

```bash
adb install --abi x86_64 path/to/app-debug.apk
```

## 13. 加页面 / 加接口的步骤

1. 后端先改 OpenAPI（或至少确认响应形状），重生成 `openapi.json` 与 `schema.d.ts`。
2. 在 `src/domain` 加领域类型与适配器，补单测（异常形状/时间/gate 兼容）。
3. 在对应 `features/<x>/queries.ts` 加 hook；用户数据 key 带 `userId`，登录相关 `enabled` 看 `authReady`。
4. 页面只组合组件；文案走人设/常量，不散落。
5. 跑 typecheck/lint/test + Android bundle；涉及交互的页面在浏览器/模拟器实际点一遍。
6. 涉及会员/计划的页面必须同时验证 free / pro / max 三种 tier，不能只看免费态。
