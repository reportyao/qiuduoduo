# Mobile 生产前端验收记录（2026-11-04）

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
