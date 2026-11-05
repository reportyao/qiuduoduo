# Mobile 生产前端验收记录（2026-11-04）

> **历史快照（2026-11-04）**：本文的测试数/路径数/结论反映当时状态，不是当前事实。当前事实见 [docs/README.md](../README.md)：265 tests / 128 路径 / 143 方法 / Alembic `20261105_13`。


范围：`apps/mobile` 从 0 重写的生产前端，真实后端 `0.8.0-w8+assistant`，390×844 手机视口逐页点击验收。

## 已走通的真实链路

- 首启：年龄门 → 价值介绍 → 首页
- 首页：三条横幅 → 日期切换（今天/昨天/前天）→ 深色已过三关卡 / 浅色复核卡 → 三关数值 → 封存
- 详情：AI 情报四维 → 三关明细 → 证据逐条展开 → 反方 → 封存自检 / payload / 链位
- 记一注：金额 → 确认 → 成功 → 5 秒撤销（真实 `DELETE /bets/{id}`）
- 关注：详情心形 → 关注列表 → 比赛名称 / 倒计时 / 终端提醒说明
- 工具：8 个工具全部可用；串关选腿/金额/结果；抽水、赔率、仓位、回本线；今日在售；不推列表；公开账本
- 记录：真实票单 → 注单复盘 → 周报；空态
- 我的：资料（昵称/头像预设/本地上传）、人设热切换、通知设置保存、收件箱、合规中心、隐私、关于、法律
- 登录：手机号验证码（dev_code 自动填入）→ JWT；游客注单/记忆/关注合并
- 拦截：未成年只开公开账本；本机自排除进入 paused；深链冷启动不误跳 onboarding

## 验收中发现并修复

1. **根布局**：水合前用 BootScreen 替换 Stack，Expo Router 报 “Attempted to navigate before mounting Root Layout” → 改 Stack 常驻 + BootScreen 覆盖。
2. **详情适配**：`/verdicts/{id}` 的 `match_id` 在 payload 内，详情被判“数据不完整” → 适配器兼容顶层/payload。
3. **详情 gate**：详情 gate 是对象、列表是字符串，三关全显示待定 → `gateResult` 同时支持两种形状；阈值从 payload 回退。
4. **卡片宽度**：`Card` 的 Pressable 包裹层没有宽度，工具网格被压成 55px → 合并 Pressable/内容样式。
5. **底栏裁字**：React Navigation 默认标签在 390 宽把中文裁半行 → 自绘 `BottomTabBar`，44+ 触控、未读徽标、键盘隐藏。
6. **后端 watch**：response_model 过滤了新增 match 字段 → 补模型；前端不再显示裸 match_id。
7. **冷启动 401**：深链在设备身份就绪前请求收件箱 → 用户查询 `enabled: authReady`，并按 userId 隔离缓存。
8. **入口分流**：index 在 prefs 水合前读默认 unknown，已成年用户被误送 onboarding → 水合完成前不 Redirect。
9. **星期错位**：+08:00 凌晨场用 UTC 星期，显示前一天 → 按中国日期重算。
10. **格式设置无效**：赔率格式只改设置不改显示 → 记注/串关/出票文案统一走 `decimalToFormat`。
11. **登录丢账**：手机号登录创建新用户，游客注单/记忆/关注丢失 → 后端 `merge_device_account` + 前端携带 device_token；退出改为新游客令牌。
12. **文案/合规**：去掉“400-000-0000”占位与“稳赚”字样；技术报错改为用户可读；自排除/未成年页明确本机拦截边界。
13. **分享/封存**：封存 UTC 时间 +8 小时 → `utcIso()`；封存页自检/链位/原文可读。
14. **周报空态**：0 结算不再显示 “0.0% 是真实比例”。
15. **昵称/头像**：保存与本地相册上传（仅本机）；相册权限最小化，移除了 image-picker 默认 RECORD_AUDIO。

## 验证结果

- 后端：159 passed；Alembic check 无差异
- mobile：typecheck / lint / Vitest 19 项通过
- `expo install --check`：依赖全匹配
- `expo export --platform android`：Metro + Hermes 成功，3.55 MB `.hbc`
- `expo config`：Android 仅 `POST_NOTIFICATIONS`，无多余麦克风权限

## 未在本机执行

- `expo run:android` / 真机 APK：本机无 Android SDK，Hyper-V 未启用；JS/Hermes bundle 与 web 交互已验证。
- iOS 原生构建：MVP 后补。
- JPush 真机 token、支付、OCR、直播、服务端合规同步：后端/凭证未就绪，前端未造假按钮。

---

## 二次逐文件深审（2026-11-04）

逐文件检查后修复的高优先级问题：

1. **会话刷新竞态**：登出/换号期间旧 refresh 回来会把旧 JWT 写回 → 增加 authEpoch + 会话对象双重校验；登出先清本地再异步撤销。
2. **登录令牌降级**：刷新失败不再把账号设备令牌伪装成匿名会话；JWT 不可恢复时创建新游客，账号数据必须重新登录。
3. **存储回退复活**：SecureStore 读到 null 时不再回落 AsyncStorage；删除时双清，避免旧 JWT 在登出后复活。
4. **冷启动路由**：年龄门页可打开 legal；index 等 prefs/compliance 水合后再分流；自排除用户进入 tabs 前先重定向 paused。
5. **自排除到期**：增加共享时钟/前台刷新，永久排除单独标记；到期自动离开 paused。
6. **注销账号**：成功后结束本地会话并回游客，避免 410 循环；410 全局触发退出。
7. **合并**：不再把游客设备令牌升级为账号永久凭证；冲突记忆保留为“（登录前）”而不是静默删除；清理孤儿通知设置。
8. **详情保护态**：详情页读取 /me 的连败状态；423 的 streak 从错误体读取，不再显示“0 场”。
9. **分享**：使用当前人设；新增 `app/share/[id].tsx` 落地验真页；重复点击防抖。
10. **比赛选择器**：使用 on-sale 的 verdict_id/status，所有已加载页；每行携带自己的 trade_date，避免拿昨日日期打开今日在售。
11. **竞彩日界**：新增 05:00 边界 helper；首页/串关/关注/在售/不推/通知深链统一使用 trade_date；后端 on-sale 取每场最新判决，why-not 支持跨日回退。
12. **P&L 正确性**：Bet 增加 `sp` 快照（新 Alembic revision），赢=本金×(SP−1)，输=−本金；同步 /bets、周报、连败 P&L、复盘。
13. **下注规则**：已结算/已停售禁止补记；删除有 10 秒服务端窗口；重复下注唯一键冲突返回 409。
14. **周报口径**：`you.bets` 只统计近 7 天，不再拿累计注数冒充本周。
15. **多账号隔离**：stream 的 you 块、me/bets/weekly/inbox/watch/notify/export 全部按 userId 入 key；刷新失败自动游客。
16. **缓存错误态**：首页/详情/收件箱/关注/票单在后台刷新失败时保留旧数据，显示紧凑重试条。
17. **工具**：串关识别让球盘/让球线；串关/记注统一赔率格式；重复点当前日期不清腿；PGSI 触控目标。
18. **资料**：头像复制到 documentDirectory + 加载失败回退；退出清理头像/赔率；人设 PATCH 失败回滚。
19. **聊天**：清空与在飞回复的竞态；冲突记忆防重复提交；消息 id 递增。
20. **安全**：OAuth `email_verified` 字符串/缺失校验与 iss 校验；已注销账号禁止助理接口/扇出；推送 token 不可被其他账号抢占；/review/* 需控制台登录。
21. **网络**：API client 12s 超时；callApi 将 fetch rejection 归一为 ApiError(0)。

最终验证：后端 161 passed；Alembic `upgrade head` + `check` 无差异；前端 typecheck/lint、20 个单测通过；Android Hermes bundle 3.59 MB。
