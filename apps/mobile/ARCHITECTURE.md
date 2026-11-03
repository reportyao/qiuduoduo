# 解球 Mobile · 开发与交接说明

面向 Android 先发、iOS 后补的 Expo React Native 生产前端。本文是给后续开发者/AI 的入口：先读这里，再读 `AGENTS.md`。

## 1. 技术栈与原则

- Expo SDK 52 / React Native 0.76.9 / React 18 / TypeScript strict
- Expo Router（文件路由）；TanStack Query（服务端状态）；Zustand（会话/偏好/合规本地状态）
- `@jieqiu/api-client`：只从 `packages/api-client/openapi.json` 快照离线生成，禁止手写接口类型
- 页面只做薄壳；数据适配、领域模型、查询、组件按 feature 分片
- 所有网络响应先经过 `src/domain/*Adapters.ts`，异常形状降级而不是崩溃
- 所有颜色/字号/圆角/动效只从 `src/theme/tokens.ts` 取

## 2. 目录

```text
app/                         Expo Router 路由（只做布局与页面组合）
  (tabs)/                    首页 / 工具 / 记录 / 我的
  verdict/[id].tsx           判决完整账
  match/[id].tsx             为什么不推 / 复核中说明
  tools/*                    8 个工具
  records/*                  周报 / 公开账本
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
| `/(tabs)` | 今日判决流（三条横幅 + AI 实体 + 卡片 + 对话入口） |
| `/verdict/[id]` | 完整账：三关明细、情报、证据、封存、记一注、关注、分享 |
| `/match/[id]?date=` | 为什么不推；404 时明确显示“没有判决记录” |
| `/tools/parlay` | 本地串关计算（日期可选、最多 4 腿、赔率格式跟随设置） |
| `/tools/rake` | 抽水 / 返还率 / 去水概率 / 公平赔率 |
| `/tools/odds` | 欧/港/印尼/美式换算 |
| `/tools/stake` | 凯利仓位（默认半凯利 + 5% 本金上限） |
| `/tools/break-even` | 回本胜率与单注期望 |
| `/tools/on-sale` | 今日在售、筛选、关注 |
| `/tools/why-not` | 已砍 / 复核中列表 |
| `/records` `/records/weekly` `/records/ledger` | 票单 / 周报 / 公开账本 |
| `/me` + `/settings/*` | 设置中心 |
| `/assistant` | 多轮助理对话（`POST /chat`） |

## 4. 数据层约定

### 4.1 适配器

- 后端大量端点没有强类型 `response_model`，因此使用 `unknown` + `src/domain/*Adapters.ts` 显式映射。
- 详情接口的 `match_id` 在 `payload.match_id`，列表接口在顶层；`adaptVerdictSummary` 两者都兼容。
- 时间：`kickoff/generated_at/data_cutoff` 是中国竞彩时间（按 +08:00 解析）；`sealed_at/created_at/notification.created_at` 是 UTC naive，必须经 `utcIso()` 补 `Z`。
- Gate：列表返回 `"pass"` 字符串，详情返回 `{result:"pass"}` 对象；`gateResult()` 两者都兼容。

### 4.2 查询

- 公共数据：`on-sale` / `ledger` / `verdict detail` 无需登录；`stream` 含个人 `you` 块，queryKey 也带 userId。
- 用户数据：`me` / `bets` / `weekly` / `inbox` / `watch` / `notify-settings` 的 queryKey 都带 `userId`，防止切换账号后串数据。
- 所有需要登录的查询都 `enabled: authReady`；深链冷启动不会在设备身份就绪前打 401。
- 写入后按前缀失效（如 `["bets"]`）即可匹配带 userId 的 key。

### 4.3 会话

`src/features/auth/authStore.ts`：

1. 启动读 `jieqiu.session.v1`（native SecureStore，Web/不可用时 AsyncStorage）。
2. 无会话 → `POST /auth/device` 创建游客身份。
3. JWT 到期前 30s 自动 `POST /auth/refresh`；只有 401/403 才结束会话并创建新游客，5xx/429/网络错误保留会话，避免瞬时故障把账号降级成游客。
4. 所有登录/设备登录/刷新都带 `authEpoch`；旧响应不能覆盖新会话。退出单飞并做 2 秒去重，避免多个 410 连环创建游客。
5. 手机号验证码登录会携带 `device_token`，后端把游客的注单/记忆/关注/通知合并到手机号账号（见 `merge_device_account`）。
6. 退出登录必须生成新的游客设备令牌，不能复用已合并的旧令牌。
7. 原生 SecureStore 不再回落明文 AsyncStorage；删除失败会写 tombstone，避免旧账号在重启后复活。

## 5. 人设

- `src/features/personas/personas.ts`：三套人设的元数据、样句、所有用户可见文案函数。
- 页面用 `usePersonaContent()`，切换人设时自动重渲染。
- 人设只改语气，不改概率/抽水/三关/封存/合规文本。
- 推送文案由后端保持中性；前端不在通知里写队名或赔率。

## 6. 设计系统

`src/theme/tokens.ts`：暖白背景、深墨绿、危险红、琥珀；字号下限 11px；触控目标 44（小按钮/芯片用 hitSlop 补足）。

自定义底栏 `src/components/BottomTabBar.tsx`：React Navigation 默认标签在 390px Web 会把中文裁半行，这里自绘；原生同样使用。

滚动交互：首页头部固定，AI 实体位于滚动内容中自然滚出；不使用折叠/压缩。

## 7. 空态、错误态与合规拦截

- 首页：无数据/非比赛日/全砍/待生成都有独立空态；不假装“今天有好货”。
- 详情：三关、情报四维、证据逐条、封存自检。
- “为什么不推”：人话标题 + 三关明细 + 再入池条件 + 可折叠技术附录；不透出 `the-odds-api key` 等配置。
- 未成年：只允许公开账本与 legal；根守卫拦截所有其他路由。
- 自排除：本机强制拦截；到期前不可撤销；页面明确“多设备同步是上线前阻塞项”。
- 登录合并：报告合并注数，避免“登录后账没了”。

## 8. 已知后端缺口（前端不伪造）

- 串关报告服务端、OCR/拍票、订阅/支付、自排除/PGSI 服务端同步、真实 live feed/进球提醒：未接入。串关仍是**本地数学计算器**，合规自排除仍是**本机强制拦截**；没有假按钮。
- 后端已提供 `/matches/{id}/live`，但只展示已同步赛果 + SP 快照，`live_feed:false`，不伪造进球时间线。
- JPush 真实 token 注册未接；通知设置/站内信/关注已接服务端。
- 详情/首页已有 `goBackOr` 处理深链冷启动返回；新增页面必须复用 `src/lib/navigation.ts`，不要直接 `router.back()`。
- 服务端新目录接口（`/matches`、`/cost`、`/water-rank`、`/calendar` 等）已生成 client，页面可按需接入；当前主要页面仍使用 `/stream`/`/on-sale`。

## 9. 当前验证状态（2026-11-04）

- 后端 179 passed；OpenAPI 94 路径 / 107 方法。
- 前端 typecheck / ESLint / 20 Vitest passed；Android Hermes bundle 3.6 MB。
- 自排除、401/410、刷新竞态、下注金额、05:00 日界、分享落地页已做回归。

## 10. 验证命令

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

## 11. 加页面 / 加接口的步骤

1. 后端先改 OpenAPI（或至少确认响应形状），重生成 `openapi.json` 与 `schema.d.ts`。
2. 在 `src/domain` 加领域类型与适配器，补单测（异常形状/时间/gate 兼容）。
3. 在对应 `features/<x>/queries.ts` 加 hook；用户数据 key 带 `userId`，登录相关 `enabled` 看 `authReady`。
4. 页面只组合组件；文案走人设/常量，不散落。
5. 跑 typecheck/lint/test + Android bundle；涉及交互的页面在浏览器/模拟器实际点一遍。
