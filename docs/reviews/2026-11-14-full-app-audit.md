# 2026-11-14 全站设计系统 + 交互逻辑审查

> 基于 ui-ux-pro-max 设计规则 × 交互逻辑走查 × 代码扫描 × 生产数据一致性核对。
> 覆盖：全部 20+ 页面 / 路由 / 组件 / 状态 / 可访问性 / 性能 / 触控 / 动效。

---

## 〇、执行结果（2026-11-14 全部五轮已落地，commit `434b94c`）

| 轮次 | 状态 | 实现要点 |
|---|---|---|
| Round 1 P0 | ✅ | ErrorBoundary 根布局包裹；开关 hitSlop 补足 44pt；a11y role/label 补齐；选场按 conversation.messages 去重；四段切换 scrollTo(y:0) |
| Round 2 数据体验 | ✅ | verdict/predictions 详情 RefreshControl；chooseDate 不再 clearFocus + prevFocusRef 恢复；简报按日期显示"今日/历史简报"；MatchTimeline 累计比分改 useMemo（修复误从 react-native 导入 useMemo + hooks 顺序违规）；badge 16px 容器/12px 字号；Skeleton + BootScreen + HeaderMetrics 全部 reduced-motion |
| Round 3 设计系统 | ✅ | 全部散落 hex/rgba 提取至 tokens（Button/Toast/Chip/IconButton/Probability*/Gates/SportmonksPredictionBoard/PredictionCard）；触觉：关注=light、三关全过=success（按 verdict id 一次）、下拉刷新=light、发送消息=light；会员页 Skeleton + ErrorState retry；NetInfo 离线横幅（OfflineBanner）+ queries `networkMode:"offlineFirst"` + 恢复联网 invalidateQueries；PredictionGroupBoard「展开全部 25 维」；EvidenceChainCard 改 Set 多选展开 |
| Round 4 暗色模式 | ✅ | tokens.ts 内置 lightColors/darkColors 同名 token 全量覆盖；模块初始化按 `Appearance.getColorScheme()` 一次选定（运行中切换系统主题需重启/刷新生效，H5 刷新即跟随）；StatusBar 跟随 scheme；暗色 hero 比页面更深一档保层次；双用途色修正：Button primary fg→`onGreen`、Toast success bg→`toastSuccessBg`、TabBar badge→`dangerPressed`；关键组合对比度脚本实测全部 ≥4.5（最低 subtle/surface 4.56，badge 白字 5.18） |
| Round 5 打磨 | ✅ | Button `android_ripple`（whiteSoft, foreground）；Sheet `keyboardShouldPersistTaps`、Toast `accessibilityLiveRegion`、工具页 keyboardType 复查发现已在早轮修复 |

**验证**：typecheck + lint 全绿；前端 64 tests、后端 364 tests 全过；Android Hermes bundle 3.61MB 出包成功；H5 已部署生产（200）。APK 由 tag `apk-20261114-ux5` 构建（netinfo 为新增原生依赖，JS-only 推送不覆盖）。

### 复核整改（同日第二轮 review，commit `4860234`，tag `apk-20261114-ux6`）

首轮交付后的复查抓出 8 处问题，全部修复：

| # | 问题 | 修复 |
|---|---|---|
| 1 | netinfo 装了 `^12.0.1`，Expo bundledNativeModules 期望 `11.4.1`，Gradle 能过但运行时兼容无保证 | 降级对齐 11.4.1 |
| 2 | Chip solid 选中态白字踩 `colors.green`（暗色 1.9:1） | 改 `onGreen` |
| 3 | Button danger 白字踩暗色亮 danger（3.0:1）；danger 同时承担文字色与实心底两种语义 | 新增 `dangerSolid`/暗色 `dangerPressed`=#8A4638，实心底与文字色分离 |
| 4 | `android_ripple` 固定 whiteSoft 在浅底按钮不可见；`foreground:true` 圆角不裁 | ripple 按 PALETTE 分变体（浅底 `inkOverlay8`），去 foreground + `overflow:hidden` |
| 5-6 | 用户气泡/发送键/FAB 白字踩绿底（ChatComposer×2、assistant×2、index×1） | 全部改 `onGreen` |
| 7 | 串关选中赔率白字踩绿底 | 改 `onGreen` |
| 8 | TanStack onlineManager 在 RN 上拿不到真实网络状态（navigator.onLine 恒 true），mutation 的 pause/resume 语义失效 | offlineStore 驱动 `onlineManager.setOnline`；恢复联网时 `resumePausedMutations()` |

复核后验证：typecheck/lint/64 tests 全绿，Android bundle 出包成功，H5 全量替换部署（旧哈希产物一并清除）并回验线上 entry 为新哈希。修复后对比度：badge 5.18、danger 按钮暗色 5.18/按下 6.97、onGreen 7+。

**暗色模式边界说明**：app.json 的原生 SplashScreen 仍是浅色（启动瞬间），深色启动图需后续 native 配置；`Appearance.addChangeListener` 的运行中热切换因全站模块级 StyleSheet 缓存而不做，属已知取舍。

---


---

## 一、设计系统审查

### P0 · CRITICAL

#### DS-1 无暗色模式

- **问题**：`theme.ts` 硬编码暖白色板，全站无 `useColorScheme()`，夜间使用白屏刺眼。
- **涉及**：`src/theme/tokens.ts`（唯一色板源，无暗色变体）
- **方案**：
  - `theme.ts` 新增 `darkPalette`，同一 token 名导出 `getColors(scheme)`。
  - 暗色色板基于现有墨绿品牌（非纯黑）：

    | Token | Light | Dark |
    |---|---|---|
    | bg | `#F6F3EC` | `#0D1A12` |
    | surface | `#FFFEFB` | `#13291F` |
    | ink | `#17221C` | `#E8EDE8` |
    | muted | `#59655E` | `#8AA094` |
    | line | `#E5E0D4` | `#1E3D2C` |
    | green | `#0C6549` | `#34C28B` |
    | heroBottom | `#08130E` | `#060F0B` |

  - 以下组件有硬编码颜色需同步适配：

    | 组件 | 硬编码 | 修复 |
    |---|---|---|
    | `Button.tsx` | `pressed: "#8CD6B8"` | 提取 token |
    | `Toast.tsx` | 4 个 hex | 提取 token |
    | `AccuracyCard` | `rgba(255,255,255,0.12)` track | 暗色变体 |
    | `ProbabilityBreakdown` | `rgba(255,255,255,0.22)` 段 | 暗色变体 |
    | `Sheet.tsx` | 背景色/遮罩 | 暗色变体 |

  - `gradients.verdict` 的 heroTop/heroBottom 在暗色下已够暗，不变。
- **工作量**：3-4 天（含逐组件适配 + 对比度测试）
- **验收**：暗色下所有文本对比度 ≥ 4.5:1；91 处 ScrollView 无破色；Toast/Sheet/Button 正常。

---

#### DS-2 全站 91 处 ScrollView + .map，0 处 FlatList/SectionList/FlashList

- **问题**：AGENTS.md 明确要求"列表使用 FlashList"，但全站无一处使用。长列表（账本 >100 条、票单 >100 条）会内存膨胀、掉帧。
- **涉及**：
  - `records/ledger.tsx` — 账本列表（可能 >100 条）
  - `records/index.tsx` — 票单列表（可能 >100 条）
- **不需要改的**：
  - 比赛列表（~10-40 条，<50 不需要虚拟化）
  - 助理对话流（聊天气泡已够轻）
  - 选场浮层（~10-20 条）
- **方案**：仅账本 + 票单两个页面改 FlatList（或 FlashList），其余保留 ScrollView。
- **工作量**：30 分钟
- **验收**：100 条数据滚动不掉帧，内存不持续增长。

---

#### DS-3 触控目标 < 44pt

- **问题**：`Controls.tsx:100` 开关 `height: 28`（含 `width: 22`），低于 iOS 44pt / Android 48dp 标准。
- **方案**：开关轨道高改 32，`Pressable` 的 `hitSlop` 至少扩展 8pt 使实际触控区 ≥ 44×44。
- **工作量**：30 分钟
- **验收**：手指在开关中心 ±22pt 范围内可触发。

---

#### DS-4 ~20 处 Pressable 无 accessibilityLabel

- **问题**：`FloatingAssistant`、`Controls.tsx`、`BottomTabBar`、`Chip` 等基础组件的 Pressable 缺少 `accessibilityLabel` / `accessibilityRole`，屏幕阅读器无法识别。
- **涉及**（精确到行，含跨行 JSX）：

  | 文件 | 缺什么 |
  |---|---|
  | `Controls.tsx` 开关 | `accessibilityRole="switch"` + `accessibilityState={{ checked }}` |
  | `FloatingAssistant.tsx` | 有 `accessibilityLabel` 但缺 `accessibilityRole="button"` |
  | `Chip.tsx` | 有 `accessibilityLabel` 但缺 `accessibilityRole="button"` |
  | `Sheet.tsx` 关闭按钮 | 有 label 但缺 `accessibilityRole="button"` |

  实际精确缺失约 5-8 处（此前粗扫 20 处为假阳性，多数 label 在 JSX 下一行）。
- **工作量**：1 小时
- **验收**：VoiceOver/TalkBack 可朗读所有可交互元素。

---

### P1 · HIGH

#### DS-5 reduced-motion 只覆盖 4 个组件

- **问题**：Skeleton（20 处使用）、`FloatingAssistant`、`HeaderMetrics` 的循环动画没有全部检查 `useReducedMotion`。前庭障碍用户会眩晕。
- **涉及**：
  - `ui/States.tsx` — Skeleton 循环闪烁动画，无 reduced-motion 检查
  - `HeaderMetrics.tsx` — AI 在线点循环脉冲
  - `FloatingAssistant.tsx` — squeeze/reveal 动画（已有检查 ✅）
  - `ConversationShell.tsx` — 打字指示器（已有检查 ✅）
- **方案**：Skeleton 组件内部加 `useReducedMotion()`，reduced 时静态灰块。
- **工作量**：1 小时

---

#### DS-6 原始 hex 硬编码在非 token 文件

- **问题**：不在 `tokens.ts` 中的 hex 会在暗色模式改色时被遗漏。
- **涉及**：

  | 文件 | 硬编码 |
  |---|---|
  | `Button.tsx:55` | `pressed: "#8CD6B8"` |
  | `Toast.tsx:33-34` | `"#FFD99B"`, `"rgba(90,58,14,0.96)"` 等 |
  | `AccuracyCard` | `"rgba(255,255,255,0.12)"` |
  | `ProbabilityBreakdown` | `"rgba(255,255,255,0.22)"` |
  | `BottomTabBar` | `"rgba(255,255,255,0.16)"` |

- **方案**：全部提取到 `tokens.ts` 或改用已有 token。
- **工作量**：30 分钟

---

#### DS-7 触觉反馈覆盖不足

- **问题**：只有 `BetSheet.tsx` 用了 `haptic()`。以下操作应有触觉反馈但完全没有。
- **建议**：

  | 操作 | 时机 | 文件 |
  |---|---|---|
  | 关注比赛 | `haptic("light")` | verdict detail |
  | 三关全过展示 | `haptic("success")` | VerdictMessage |
  | 下拉刷新完成 | `haptic("light")` | matches / plans / index |
  | 发送消息 | `haptic("light")` | ChatComposer |

- **工作量**：1 小时

---

#### DS-8 会员页缺空态/错误/加载态

- **问题**：`membership.tsx` → 0 error / 0 empty / 0 skeleton。`useMembershipQuery` 失败时页面空白。
- **方案**：加 `useMembershipQuery` 的 loading skeleton 和 error retry。
- **工作量**：30 分钟

---

#### DS-9 BottomTabBar 徽标 10px 字号

- **问题**：`badgeText: { fontSize: 10 }` 低于 12px 最低可读标准。
- **方案**：提到 12px，badge 最小宽从 14 提到 16。
- **工作量**：10 分钟

---

### P2 · MEDIUM

#### DS-10 Sheet 缺 keyboardShouldPersistTaps

- **问题**：Sheet 内含输入框时，点击输入框外不会收起键盘（RNW）。
- **方案**：Sheet 内部 ScrollView 加 `keyboardShouldPersistTaps="handled"`。

---

#### DS-11 Toast 缺 aria-live

- **问题**：Toast 组件没有 `accessibilityLiveRegion`，屏幕阅读器不会播报。
- **方案**：Toast 外层 View 加 `accessibilityLiveRegion="polite"`。

---

#### DS-12 Button 缺 android_ripple

- **问题**：Android 上按钮按下无 Material ripple（当前用 opacity，感知弱）。
- **方案**：`Button.tsx` 加 `android_ripple={{ color: colors.greenPressed, borderless: false }}`。

---

#### DS-13 概率条纯颜色区分

- **问题**：`ProbabilityBreakdown` 堆叠条用颜色区分主/客/平，色盲用户无法区分。
- **状态**：已有图例文本（主胜 47% 等），满足 `color-not-only` 规则。但可在条上直接标注百分比减少眼球移动。
- **优先级**：可暂缓。

---

#### DS-14 键盘类型不一致

- **问题**：部分数字输入框未显式设置 `keyboardType`。
- **方案**：数字输入统一 `keyboardType="number-pad"` 或 `"decimal-pad"`。
- **现状**：登录/工具页已设置 ✅，其他页面零散。

---

### P3 · LOW

| 项 | 说明 | 状态 |
|---|---|---|
| mascot 图无 alt | accessibilityLabel 缺失 | P3 |
| 手势导航冲突 | 不用 swipe，无冲突 | ✅ |
| Toast 自动消失 | 1800ms 在 3-5s 范围内 | ✅ |
| 色彩语义正确 | hit=green / miss=danger / push=amber + 文字 | ✅ |
| 密码管理器支持 | 登录页已用 keyboardType | ✅ |

---

## 二、交互逻辑审查

### INT-1 同一比赛可重复选入对话（无去重）

- **严重度**：高（污染对话流）
- **现象**：用户从简报卡 / 浮层 / TodayBriefCard 选同一场比赛多次，每次都往对话追加重复的"看这场"+ 比赛卡。
- **涉及**：`app/(tabs)/index.tsx` 的 `selectBriefOption` 和 `homeSelectionStore` 消费 effect
- **方案**：追加前检查 `conversation.messages.some(m => m.kind === "match" && m.option.matchId === option.matchId)`，已存在则只 setFocus 不追加。
- **工作量**：15 分钟

---

### INT-2 切换日期后焦点永久丢失

- **严重度**：高（用户迷失当前查看的比赛）
- **现象**：选中比赛 A → 切到前一天 → 焦点被 `clearFocus()` 清掉 → 切回原日期 → 焦点没有恢复。
- **涉及**：`app/(tabs)/index.tsx:173` 的 `chooseDate`
- **方案**：不清除 focus，改为记住焦点日期，切回时自动恢复。
- **工作量**：30 分钟

---

### INT-3 详情页四段切换不回到顶部

- **严重度**：高（用户看到另一段的内容尾部）
- **现象**：在"预测"段滚到底 → 切到"市场"段 → 视口停在底部。
- **涉及**：`app/verdict/[id].tsx` — ScrollView 无 ref
- **方案**：加 ScrollView ref，section 变化时 `scrollTo({ y: 0 })`。
- **工作量**：15 分钟

---

### INT-4 详情页无下拉刷新

- **严重度**：中（比赛进行中无法刷新比分）
- **现象**：verdict 详情和 prediction 详情均无 `RefreshControl`。
- **涉及**：`app/verdict/[id].tsx`、`app/predictions/[id].tsx`
- **方案**：ScrollView 加 RefreshControl。
- **工作量**：20 分钟

---

### INT-5 无全局 ErrorBoundary

- **严重度**：高（任何渲染错误导致白屏）
- **现象**：`_layout.tsx` 无 ErrorBoundary，组件 render 抛异常 → App 白屏。
- **方案**：新建 ErrorBoundary 类组件，在根布局包裹。
- **工作量**：30 分钟

---

### INT-6 无网络状态检测

- **严重度**：中（用户分不清断网 vs 服务器挂了）
- **现象**：无 `NetInfo` 监听，无全局离线提示。断网时零散 ErrorState 但无统一"已离线"横幅。
- **方案**：NetInfo + 顶部琥珀色横幅 + TanStack Query `networkMode: "offlineFirst"`。
- **工作量**：1 小时

---

### INT-7 TodayBriefCard 历史日期仍显示"今日简报"

- **严重度**：低（文案误导）
- **现象**：切到昨天，简报卡标题仍写"今日简报"。
- **方案**：接收 `isToday` prop，非今日显示"历史简报"。
- **工作量**：5 分钟

---

### INT-8 MatchTimeline 累计比分 Strict Mode 翻倍

- **严重度**：低（当前未启用 Strict Mode）
- **现象**：`home`/`away` 计数器在 `goals.map()` 闭包内 mutable 累加，React Strict Mode double-invoke 会翻倍。
- **方案**：改 `useMemo` 预计算。
- **工作量**：15 分钟

---

### INT-9 预测分组无"全部展开/收起"

- **严重度**：低
- **现象**：25 维分 6 组，默认 2 组展开，看全部需逐组点 6 次。
- **方案**：分组标题行加"全部展开/收起"。
- **工作量**：15 分钟

---

### INT-10 证据链同时只能展开一条

- **严重度**：低
- **现象**：`expanded: number | null`，点新条自动收起旧条，无法对比两条依据。
- **方案**：改 `Set<number>` 多选展开。
- **工作量**：15 分钟

---

## 三、逐页面审查

### 引导页（Onboarding）
| 检查项 | 状态 |
|---|---|
| 430px 居中 | ✅ |
| 按钮高度 48 | ✅ |
| 隐私提示清晰 | ✅ |
| mascot 图无 accessibilityLabel | ⚠️ P3 |

### 助理首页
| 检查项 | 状态 | 关联问题 |
|---|---|---|
| 简报卡（简报/下一场/重点） | ✅ | |
| 对话流 | ✅ | INT-1 去重 |
| 输入浮层不占布局 | ✅ | |
| 浮动头像 | ✅ | DS-4 a11y label |
| Composer 收起态 | ✅ | |
| 日期切换 | ✅ | INT-2 焦点丢失 |

### 比赛中心
| 检查项 | 状态 | 关联问题 |
|---|---|---|
| 三段 Tab | ✅ | |
| 即时空态显示下一场 | ✅ | |
| 预测战绩看板四块 | ✅ | DS-2 列表虚拟化 |
| 按联赛拆分 | ✅ | |
| 日期导航 | ✅ | |
| 25 维分组折叠 | ✅ | INT-9 全部展开 |

### 比赛详情（四段工作台）
| 检查项 | 状态 | 关联问题 |
|---|---|---|
| 概览（证据链 + AI 情报） | ✅ | |
| 预测（25 维分组） | ✅ | |
| 市场（概率对比 + 分歧） | ✅ | |
| 复盘（归因） | ✅ | |
| 底部操作栏 | ✅ | |
| 安全区适配 | ✅ | |
| 分段切换回顶 | ❌ | INT-3 |
| 下拉刷新 | ❌ | INT-4 |

### 预测复盘详情
| 检查项 | 状态 | 关联问题 |
|---|---|---|
| 时间轴（进球 + 半场对照） | ✅ | INT-8 Strict Mode |
| 概率分布（堆叠条/网格） | ✅ | DS-13 纯颜色 |
| 命中率汇总 | ✅ | |
| 计入/对照分段 | ✅ | |
| 下拉刷新 | ❌ | INT-4 |

### 计划页
| 检查项 | 状态 |
|---|---|
| 深色收益主卡 | ✅ |
| 风险切换 | ✅ |
| 历史期数列表 | ✅ |
| 会员锁 | ✅ |

### 我的页
| 检查项 | 状态 | 关联问题 |
|---|---|---|
| 个人资料卡 | ✅ | |
| 快捷入口 | ✅ | |
| 设置分组 | ✅ | |
| 空态处理 | ⚠️ empty:0 — 需加 | |

### 其他页面
| 页面 | 状态 | 关联问题 |
|---|---|---|
| 工具页 | ✅ | 纯计算，无需空态 |
| 记录页 | ✅ | DS-2 列表虚拟化 |
| 公开账本 | ✅ | DS-2 列表虚拟化 |
| 会员页 | ⚠️ | DS-8 缺加载态 |
| 登录页 | ✅ | |
| 隐私政策 | ✅ | |
| 串关参谋 | ✅ | |

---

## 四、设计令牌审查

### 当前令牌完整性

| 类别 | 状态 | 缺口 |
|---|---|---|
| 颜色（light） | ✅ 完整 | |
| 颜色（dark） | ❌ 无 | DS-1 |
| 字号 | ✅ 12-34 全覆盖 | |
| 行高 | ✅ 同步放大 | |
| 间距 | ✅ 4-40 | |
| 圆角 | ✅ 10-999 | |
| 阴影 | ✅ 三档 | |
| 动效时长 | ✅ 4 档 | |
| 布局 | ✅ maxWidth / padding / height | |
| 触觉 | ❌ 无 token（haptic 直调字符串） | 可补 |
| z-index | ❌ 无 scale（组件硬编码 20/30） | 可补 |
| 图标尺寸 | ❌ 无 token（各处 14-24 不等） | 可补 |

---

## 五、建议实施路线图

### 第一轮（P0 · 防崩溃 + 可用性合规）
| 编号 | 项目 | 工作量 |
|---|---|---|
| INT-5 | ErrorBoundary | 30 min |
| DS-3 | 触控目标修复 | 30 min |
| DS-4 | a11y label 补齐（~5 处） | 1 hr |
| INT-1 | 选场去重 | 15 min |
| INT-3 | 分段回顶 | 15 min |
| 合计 | | **~2.5 hr** |

### 第二轮（P1 · 数据体验）
| 编号 | 项目 | 工作量 |
|---|---|---|
| INT-4 | 详情页下拉刷新 | 20 min |
| INT-2 | 焦点保持 | 30 min |
| INT-7 | 简报标题 | 5 min |
| INT-8 | 时间线 Strict Mode | 15 min |
| DS-9 | badge 字号 | 10 min |
| DS-5 | reduced-motion 补齐 | 1 hr |
| 合计 | | **~2.5 hr** |

### 第三轮（P1 · 设计系统补全）
| 编号 | 项目 | 工作量 |
|---|---|---|
| DS-6 | hex 提取到 token | 30 min |
| DS-7 | 触觉反馈补齐 | 1 hr |
| DS-8 | 会员页加载态 | 30 min |
| INT-6 | 网络状态检测 | 1 hr |
| INT-9 | 预测分组全部展开 | 15 min |
| INT-10 | 证据链多选展开 | 15 min |
| 合计 | | **~3.5 hr** |

### 第四轮（P0 · 暗色模式，独立出）
| 编号 | 项目 | 工作量 |
|---|---|---|
| DS-1 | 暗色色板 + useColorScheme | 2 hr |
| DS-1 | 逐组件适配（Button/Toast/Sheet/图表等） | 1.5 hr |
| DS-6 | hex 提取（与第三轮合并可省） | — |
| 合计 | | **~3.5 hr** |

### 第五轮（P2 · 打磨，可并行）
| 编号 | 项目 | 工作量 |
|---|---|---|
| DS-10 | Sheet keyboard | 15 min |
| DS-11 | Toast aria-live | 15 min |
| DS-12 | Button android_ripple | 15 min |
| DS-14 | keyboardType 补齐 | 15 min |
| 合计 | | **~1 hr** |

---

## 六、明确不做（本轮排除）

| 项 | 理由 |
|---|---|
| 全局搜索接口 | 用户已确认不做 |
| 决定时刻标注 | 需逐事件回放推演，P2 |
| Storybook / 组件文档 | 无前端团队需求 |
| E2E 测试（Detox/Maestro） | 需要独立基建 |
| 视觉回归测试 | 需要独立基建 |
| Postgres 切库 | 独立运维任务 |

---

## 七、验证命令

```bash
# 后端全量
cd jieqiu-backend && python -m pytest -q

# 前端全量
cd apps/mobile
corepack pnpm typecheck && corepack pnpm lint && corepack pnpm test

# Android bundle
corepack pnpm exec expo export --platform android --output-dir .export-check --clear

# H5 构建
just mobile-web-export

# 部署
just h5-publish
```
