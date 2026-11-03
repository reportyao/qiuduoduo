# 前端功能 ↔ 后端接口 ↔ 数据流 完整映射 v1.0

| 项目 | 内容 |
|---|---|
| 范围 | UI 演示 23 视图 × 50 交互 × 46 功能点，逐项映射到后端 API / 数据表 / 后端模块 |
| 用途 | ① 前端开发对照表 ② 后端开发任务清单 ③ 联调验收单 ④ 文档一致性保障 |
| 配套 | PRD v5.1 · TechSpec v2.1 · Release-plan v1.1 |

---

## 使用方法

每个功能一行，五列：**前端交互 → 用户看到什么 → 调什么 API → 后端哪个模块处理 → 读/写哪张表**。
末列标注 `✓ 已定义` / `✗ 本次补` / `— 纯前端`。

---

## Tab ① 首页（判决流）

| 功能 | 前端交互 | 用户看到 | API | 后端模块 | 数据表 | 版 |
|---|---|---|---|---|---|---|
| 判决流拉取 | 进入首页自动 | 判决卡+哨兵+避雷+复盘 | `GET /stream?cursor=` | verdict+messaging | verdicts+messages | v0.5 |
| 判决卡"为什么" | 按钮→详情页 | 三层渐进披露 | `GET /verdicts/{id}` | verdict | verdicts | v0.5 |
| 判决卡"买了" | 按钮→弹层→金额→确认 | 卡变"已记✓"+安抚卡+5s撤销 | `POST /verdicts/{id}/react` | verdict+bets | bets | v0.5 |
| 判决卡"不同意" | 按钮→AI 不顺从回应 | 反方数据+仓位减半建议 | `POST /verdicts/{id}/react` | verdict | feedback | v0.5 |
| 判决卡"⋯"菜单 | 按钮→弹层 | 分享/关注/不看 | `POST /verdicts/{id}/react` | messaging | follows | v1.0 |
| 判决卡封存行点击 | 点击→哈希详情弹层 | 全哈希+验证方法+账本链接 | `GET /verdicts/{id}/seal` | verdict | verdicts.payload_hash | v1.0 |
| 建议词 chip | 点击→自动发送 | 对话结果卡 | `POST /chat` | narrate+model | messages | v1.0 |
| 输入框 Enter | 打字→发送 | 对话结果卡 | `POST /chat` | narrate+model | messages | v1.0 |
| 📷 按击 | 按钮→ActionSheet | 拍票/截图/赛程三选 | — (前端路由) | — | — | v1.0 |
| "今天不看了" | 点击→休息卡 | 吉祥物+休息文案 | `POST /me/rest` | users | users.rested_at | v0.5补 |
| 状态条点击 | 点击→今日在售 | 跳工具 Tab | `GET /matches/on-sale` | ingest | sp_matches | v0.5 |
| 串关体检横幅 | 点击→构建器 | 四步流程 | `POST /parlay/check` | market+model | parlay_reports | v1.0 |
| 引擎状态点击 | 点击→日志弹层 | 9 行分析日志 | `GET /analysis-log?date=` | model | model_runs | v0.5补 |
| ticker 点击 | 点击→跳账本 | 公开账本页 | `GET /ledger` | leaderboard | verdicts(公开) | v1.0 |
| 通知软请求 | 首次渲染→内嵌卡 | "以后赛前提醒你" | `POST /devices` | push | push_tokens | v1.0 |
| 吉祥物点击 | 点击→选比赛浮层 | 分类 chips+场次行 | `GET /matches/on-sale` | ingest | sp_matches | v1.0 |
| 选比赛→页卡入流 | 点击场次行 | 分析卡插到流中 | `GET /matches/{id}/cost` | market | odds_snapshots | v1.0 |

## Tab ② 工具

| 功能 | 前端交互 | 用户看到 | API | 后端模块 | 数据表 | 版 |
|---|---|---|---|---|---|---|
| 串关体检·构建 | 勾腿+金额→提交 | 核算序列动画 | `POST /parlay/check` | market+model | — | v1.0 |
| 串关体检·报告 | 自动跳转 | 健康分+发现四层+附录 A | `GET /parlay/{id}/report` | market | parlay_reports | v1.0 |
| 串关体检·方案 | 点击"看方案" | A/B/C 三方案 | `GET /parlay/{id}/plans` | market | — | v1.0补 |
| 串关出单 | 点方案 C→确认 | 拆单+文案复制 | `POST /parlay/{id}/confirm` | verdict+bets | bets | v1.0补 |
| 拍票记账 | 📷→拍照→自动识别 | 票面信息+抽水+期望 | `POST /vision/scan` | risk+vision(RapidOCR) | bets | v1.0 |
| 截图鉴别 | 📷→选截图 | 三问题+独立判断 | `POST /vision/scan` | narrate+moderation | — | v1.0 |
| 今日在售 | Tab 或 strip 点击 | 场次列表+同步状态+过闸标签 | `GET /matches/on-sale` | ingest | sp_matches | v0.5 |
| 水位榜 | 工具宫格点击 | 抽水最浅 3 场 | `GET /water-rank` | market | odds_snapshots | v0.5 |
| 为什么不推 | 工具宫格或避雷行 | 死在哪关+原因 | `GET /matches/{id}/why-not` | verdict | verdicts.gates | v0.5 |
| 盘口哨兵 | 工具宫格点击 | 异动提示列表 | `GET /agents/sentinel/feed` | market | events | v1.0 |
| 黑话翻译 | 工具宫格点击 | 术语翻译 | `POST /chat`(术语匹配) | narrate | — | v1.5 |

## Tab ③ 记录

| 功能 | 前端交互 | 用户看到 | API | 后端模块 | 数据表 | 版 |
|---|---|---|---|---|---|---|
| 我的票单 | Tab 点击 | 注数+状态列表 | `GET /bets` | verdict | bets | v0.5 |
| 票单死因回访 | 卡片点击 | "死在第 2 关"+what-if | `GET /bets/{id}/postmortem` | verdict | bets.legs+match_facts | v1.0 |
| 周报 | Tab 点击 | 采纳/归因/眼光分/砍场 | `GET /weekly-report` | leaderboard | bets+verdicts | v0.5 |
| 公开账本 | Tab 点击 | 全部结论+连败 | `GET /ledger` | leaderboard | verdicts(公开) | v0.5 |
| 记忆管理 | Tab 点击 | 可见可删列表 | `GET|DELETE /memories` | users | memories | v1.0 |
| 导出数据 | Tab 点击 | JSON 下载 | `GET /me/export` | users | 全表 | v1.0 |

## Tab ④ 我的

| 功能 | 前端交互 | 用户看到 | API | 后端模块 | 数据表 | 版 |
|---|---|---|---|---|---|---|
| 人设选择 | 行点击→试读→✓ | 试读样句+立即生效 | `PATCH /me` | users | users.persona | v1.0 |
| 连败保护开关 | Toggle | 开/关 | `PATCH /me/discipline` | compliance | budgets | v0.5补 |
| 合规中心·自排除 | 选项→二次确认 | 生效横幅+热线 | `POST /compliance/self-exclusion` | compliance | compliance_events | v0.5 |
| 合规中心·PGSI | 量表→提交 | 分级结果 | `POST /compliance/self-assessment` | compliance | compliance_events | v0.5 |
| 界面语言 | 行点击→弹层 | Tab+按钮即切 | `PATCH /me` | users+i18n | users.locale | v1.0 |
| 赔率格式 | 行点击循环 | 数字变化 | `PATCH /me` | users | users.odds_format | v1.0 |
| 订阅 | 行点击→付费页 | 四态：可购/处理/成功/失败 | `POST /billing/*` | billing | subscriptions | v1.5 |
| 导出 | 行点击→下载 | JSON 文件 | `GET /me/export` | users | 全表 | v1.0 |
| 注销 | 行点击→冷静期 | 7 天可撤回 | `DELETE /me` | auth | users.status | v1.0 |

## 全局

| 功能 | 触发 | API | 后端模块 | 数据表 | 版 |
|---|---|---|---|---|---|
| 年龄门 | 首次启动 | `POST /gate/verify` | auth | consents | v0.5 |
| 登录/注册（按国家） | 点买了/订阅触发 | `POST /auth/*` | auth | users + auth_identities + refresh_tokens | v0.5 |
| 通知软请求 | 首次看判决后 | `POST /devices` | push | push_tokens | v1.0 |
| 实况卡 | 看比赛详情 | `GET /matches/{id}/live` | collector+market | sp_snapshots+match_facts | v1.0 |
| 进球提醒 | 实况卡开关 | `POST /matches/{id}/goal-alert` | push | push_tokens.scopes | v1.0 |
| 语言切换 | 弹层 | `PATCH /me` | users+i18n | users.locale | v1.5 |
| 赔率格式切换 | 偏好循环 | `PATCH /me` | users | users.odds_format | v1.0 |
| 深链路由 | 推送点击 | `jieqiu://verdict/{id}` | — (前端路由) | — | v1.0 |
| 分享卡生成 | 分享按钮 | `POST /share/card` | narrate | — | v1.0 |
| PGSI 自评 | 合规中心 | `POST /compliance/self-assessment` | compliance | compliance_events | v1.0 |
| 功能旗全量 | 启动时拉取 | SDK 内置 | PostHog | — | v1.0 |

---

## 本次审计发现并补充的 9 个缺失 API

| # | API | 服务的前端功能 | 说明 |
|---|---|---|---|
| 1 | `GET /matches/{id}/live` | 实况卡 | 事件时间线+走盘计算 |
| 2 | `POST /matches/{id}/goal-alert` | 进球提醒开关 | 仅本场，终场自动过期 |
| 3 | `GET /parlay/{id}/plans` | 方案对比 | A/B/C 三方案 |
| 4 | `POST /parlay/{id}/confirm` | 拆单出票 | 确认+入账 |
| 5 | `POST /me/rest` | 今天不看了 | rested 状态 |
| 6 | `PATCH /me/discipline` | 连败保护开关 | 开/关 |
| 7 | `GET /analysis-log?date=` | 分析日志弹层 | 9 行分析日志 |
| 8 | `POST /me/under18-lock` | 未成年锁定 | 受限模式 |
| 9 | `GET /me/comfort` | 买后安抚卡内容 | 也可流内推 |

以上 9 个已全部写入 TechSpec §6 API 列表。

---

## 后端模块 ↔ 数据表 ↔ API 覆盖度

| 后端模块 | 服务的 API 数 | 读的表 | 写的表 |
|---|---|---|---|
| auth | 6 | auth_identities, consents | users, auth_identities, consents |
| users | 5 | users, memories, bets | users, memories |
| ingest | 3 | sp_matches, odds_snapshots | sp_matches, odds_snapshots |
| align | 1 | team_aliases | team_aliases |
| model | 3 | matches, odds_snapshots, match_facts | model_runs, match_facts |
| market | 2 | odds_snapshots, matches | — |
| verdict | 5 | verdicts, matches, model_runs | verdicts, match_facts, bets |
| narrate | 3 | verdicts, match_facts, glossary | narrative_pool, verdicts.locale_texts |
| messaging | 3 | verdicts, match_facts | messages, narrative_pool |
| push | 2 | push_tokens | push_tokens |
| billing | 3 | subscriptions, payments | subscriptions, payments |
| compliance | 4 | compliance_events, users | compliance_events, users.status |
| i18n | 1 | glossary | glossary |
| risk | 2 | events, bets | — |
| audit | 1 | audit_log | audit_log |
| collector | 1 | sp_matches, sp_snapshots(只读镜像) | — |
| moderation | 2 | — | tickets, moderation_log |
| leaderboard | 1 | verdicts(公开), bets | — |
| editor_console | 5 | narrative_pool, model_runs, compliance_events | narrative_pool.status |
| reconciliation | 1 | payments, subscriptions | reconciliation |

---

## AI 助理运行时（P0，2026-11-03）

| 功能 | 前端动作 | 后端接口 | 表 | 状态 |
|---|---|---|---|---|
| 站内信列表 | 红点/消息中心 | `GET /me/inbox` | notifications | ✅ |
| 未读数 | 顶部红点 | `GET /me/inbox/unread-count` | notifications | ✅ |
| 标记已读 | 点开一条 | `POST /me/inbox/{id}/read` | notifications | ✅ |
| 全部已读 | 消息中心 | `POST /me/inbox/read-all` | notifications | ✅ |
| 点击深链 | 点开通知 | `POST /me/inbox/{id}/click` | notifications | ✅ |
| 关注比赛 | 关注开关 | `GET/POST /me/watch`、`DELETE /me/watch/{id}` | watch_targets | ✅ |
| 通知设置 | 设置页 | `GET/PUT /me/notify-settings` | notify_settings | ✅ |
| 推送注册 | Android 启动 | `POST /push/register` | push_tokens | ✅ |
| 推送解绑 | 退出登录 | `POST /push/unregister` | push_tokens | ✅ |
| 事件/推送运维 | 管理后台 | `GET /console/assistant`、`/console/push` | events/notifications/push_tokens | ✅ |
| 前端接 inbox/关注 | 首页/我的 | 上述接口 | — | ⏳ 待接 |
| 真实 JPush 厂商通道 | Android 包 | provider | push_tokens | ⏳ 凭证 |

## 联调验收清单（每个功能的"做完了"标准）

| 检查项 | 说明 |
|---|---|
| API 返回 200 | 接口通了 |
| UI 正确渲染 API 返回的数据 | 数据到了前端且展示对了 |
| 错误态处理 | 404/500/超时各有一个用户可理解的提示 |
| 拦截态处理 | 未登录/未成年/自排除/rested 四种状态的行为正确 |
| 埋点上报 | PostHog 能看到该功能的事件 |
| 禁用词扫描 | 涉及文案的功能已过 CI 扫描 |
| 空数据态 | 数据为空时显示空态（不是白屏） |
| 移动端适配 | 375px 宽度下不破版 |

## W2 实现状态（2026-11-03 · jieqiu-backend v0.2 @43.128.244:8100）

- ✅ `GET /stream?cursor=&limit=`（游标分页已实现，next_cursor 契约）
- ✅ `GET /analysis-log?date=`（v0.5补 #7，model_runs 驱动，每场每闸最新一条）
- ✅ `GET /matches/on-sale`（提前自 W3 落地，数据现成）
- ✅ `GET /verdicts/{id}` + `/seal`（封存哈希独立复算验证通过）
- ⏳ `GET /matches/{id}/why-not`（F6 属 W3，随三道闸引擎一起上）
- ⏳ 其余 v0.5补 用户态 API（me/rest、under18-lock 等）待 W5 auth 后开
- 采集管道已原子上传（tmp+rename）+ seed 读前拷贝，消除 SFTP 并发半截文件风险

---

*Feature-API-Mapping v1.0 完 · 46 功能点 × 41 API × 20 表全覆盖*
