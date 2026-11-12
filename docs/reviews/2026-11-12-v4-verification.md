# v4.1 交付验证（2026-11-12）

> 分支：`feat/v4-plan-settlement`  
> 范围：4 Tab、HeaderMetrics、每日 AI 战绩、4 场定投计划、会员权益/手动开通、90 分钟结算、人设 chat、OPC 后台。  
> 结论：**代码与文档通过本地测试与模拟器验收；生产未部署、v4 APK 未构建。**

## 1. 自动验证

| 项 | 命令 | 结果 |
|---|---|---|
| 后端 | `cd jieqiu-backend && python -m pytest -q` | **341 passed**（1309 warnings，主要为 NumPy/Pandas 弃用告警） |
| 前端 | `cd apps/mobile && corepack pnpm test -- --run` | **47 passed / 13 files** |
| 类型 | `corepack pnpm typecheck` | 通过 |
| Lint | `corepack pnpm lint` | 通过 |
| Bundle | `corepack pnpm exec expo export --platform android --output-dir .export-check --clear` | 通过（Metro + Hermes） |
| OpenAPI | 读取 `packages/api-client/openapi.json` | **158 路径 / 174 方法** |
| 迁移 | `alembic heads` / 迁移文件 | 单一 head `20261112_23`，up/down 成对 |

后端新增测试重点：

- `tests/test_v4_core.py`：90 分钟 outcome、整数亚盘 void、稳健计划 4 场、Max 计划门控、计划结算、引擎 uptime、过期候选过滤、chat persona/record。
- `tests/test_admin_v4.py`：后台 v4 视图、工作台未知年龄文案、App 用户手机/邮箱脱敏、手动开通/撤销、引擎配置、OPS、计划列表。

## 2. 管理后台浏览器验收

环境：本机 `/admin`，Playwright/IAB 1280×720；管理员 `admin`（dev 环境）。逐页点击了工作台、AI 计划、用户与会员、异常队列，并验证了以下动作/确认框：

- 工作台：AI 体检、刷新、采集器重启确认、同步动作确认、卡点/名词解释；
- AI 计划：三种风险列表、计划生成确认、结算/重算、legs 展示；
- 用户与会员：搜索、免费/Pro/Max 筛选、当前等级按钮禁用、变更为 Pro/Max 确认、撤销确认；
- 异常队列：异常渲染、标记处理、引擎配置保存、最近任务状态/时间/错误渲染。

本轮后台修复见 §3。

## 3. 模拟器验收

环境：MuMu x86_64，debug APK 以 `adb install --abi x86_64` 安装；后端 `127.0.0.1:8100`，Metro `8081`。

已走通：

- onboarding → 年龄门；
- 首页助理对话流、HeaderMetrics、每日战绩、聚焦卡；
- 比赛 Tab → 在售/筛选/详情；
- 计划 Tab → 三种风险、当前期、历史期、Max 锁定态；
- 计划详情 → 预算/投入/盈亏/回报率/回撤、legs；
- 我的 → 会员与权益、我的记录、人设/记忆入口；
- 会员页 → 当前 tier、到期、额度、价格卡、充值假 UI；
- 聊天 → 发送、persona 透传、回复。

## 4. 本轮修复

| 问题 | 修复 |
|---|---|
| 计划 legs 只显示 `home`/空队名 | `_leg_payload()` 输出 `match_no/league/home/away`；方向存中文“主胜/平局/客胜” |
| 计划 0 盈亏显示 `+¥0` | 0 显示 `¥0`，颜色中性 |
| 会员副标题被截断 | 改为“充值暂未开放” |
| 已是 Max 仍显示“选择 Max” | 当前 tier 按钮显示“当前方案”并 disabled |
| HeaderMetrics 显示“0 条数据点” | 0 显示“今日数据同步中” |
| 计划页底部被 TabBar 遮挡 | 增加底部 padding |
| 登录前计划/会员查询闪锁定态 | queryKey 带 userId，`enabled: authReady`，详情用 isPending 骨架 |
| 计划不会自动结算 | `settle_open_cycles` 接入赛果同步与 seed |
| 整数亚盘 push 被算赢 | 结算返回 `won=None`，统一写 void，账本/周报/复盘排除 |
| 免费额度在 AI 失败前被扣 | 先 precheck，成功后才 consume |
| 计划候选含已开赛/过期场次 | `_candidates()` 过滤 kickoff 与 snapshot expires_at |
| 后台回显完整手机/邮箱 | `mask_phone/mask_email` |
| 已注销账号仍能访计划/会员 | 增加 `is_deleted` 守卫 |
| 工作台“SP 文件 未知前更新” | 未知时只显示“SP 文件 未知”，有年龄才拼“前更新” |
| AI 计划已发布卡片被画成草稿样式 | 按 `plan.status` 输出 `published/settled/draft` class；已发布走绿色左边线 |
| AI 计划 legs 只显示 `m-ui-1` | 显示竞彩编号、主客队、联赛、赔率、模型/市场概率、edge、质量、选择理由 |
| 计划投注状态显示 `pending`/原始赔率 | 状态映射为待结算/已中/未中/走水；赔率统一两位小数；结算后展示盈亏 |
| 计划“生成今日计划”直接写库 | 增加确认弹窗，明确会新建一期并发布 |
| 用户与会员无搜索/筛选、当前等级仍可点 | 增加搜索、免费/Pro/Max 筛选、当前等级禁用；变更/撤销均加确认 |
| 异常队列引擎配置四个超宽输入 | 改为四列配置网格 + label + 说明，窄屏自动 1 列 |
| 任务/异常缺时间、状态英文 | 增加开始/时间列；status 映射运行中/失败/待处理/已确认/已处理 |
| 工作台重启采集器无确认 | 加入确认弹窗，说明离线时需 watchdog/人工启动 |
| 首页选中比赛后聚焦区不可见 | 把 FocusSection 提到开场简报上方；选中/换场后“正在看”直接出现在首屏，不再藏在页面底部 |
| 完整预测页报“判决数据不完整” | `/verdicts/{id}` 补 `match_id`；详情适配器不再因缺 matchId 误判数据不完整 |
| 详情页在无情报时写“情报已封存/模型与市场一致” | 无证据时改为“情报待同步/不编造”；有证据才区分已封存/待封存 |
| 运行日志页报 `config is not defined` | 删除 `loadLogs()` 里误贴的模型效果代码，只保留日志加载/切换 |
| 调用用量页所有路由都显示“正常”，即使 fast/deep 未配 Key | 按 profile `configured` 显示“未配置”；补 `workbench_diagnose` 中文名 |
| 推荐撤回弹窗提交无响应 | 把 submit 绑定移入按钮点击作用域，撤回后可刷新并写审计 |
| 手动映射失败弹窗无关闭按钮 | 加载态/错误态都提供“取消/关闭”，避免弹窗卡死 |
| 采集器页显示“— · —前” | 无时间戳时不再拼接“前”；同步延迟超 30 分钟显示“数据过期” |
| 工作台推送“正常”但 JPush 未配置 | 改为“需关注 + dry-run”，下一步提示配置 AppKey/Master Secret |
| 数据页“市闸无法通过”与“市闸 4 过”矛盾 | 阻断文案改为“市场覆盖为 0”，不再断言市闸失败 |
| 数据页 SM 映射 0/4、AI 情报 0/4 仍用绿色 | 缺口时改为 amber；调用用量未配置路由改为 amber |
| 总览“模型池健康”与“模型配置未配 Key”混淆 | KPI 改为“文案模型池”，待办改为“LLM 接入未配 Key”并列出 fast/deep |
| 推荐主链“运行主链”直接改线上内容 | 增加确认弹窗，说明会 build→复核→发布 |
| 后台禁用账号状态显示原始 `muted` | 增加“已停用”状态；运维 low 告警显示“提示”而非“跳过” |

## 5. 明确未完成

- 真实支付/订单/回调；会员只能后台手动开通。
- 多盘口完整数据：计划与 HeaderMetrics 的“5 盘口”目前是配置展示，实际计划只处理 1X2/让球。
- 计划自训练模型：只有 `feature_snapshots/model_registry/training_runs` 脚手架。
- 计划更新提醒/收藏；不做跟单/自动记注/代购。
- 生产 Postgres 切库、备份/PITR 恢复演练。
- v4 正式 APK 构建/签名/发布、iOS、真机 JPush。
- 生产部署已完成（2026-11-12 11:38 CST）：`deploy.py` 部署到 `43.128.24.244`，`/health` 200，OpenAPI 158/174，管理后台静态资源 v=20261112d；生产仍为 SQLite。部署前备份在 `/home/ubuntu/backups/`（代码 `jieqiu-backend-20261112-113522.tar.gz`、库 `jieqiu-20261112-113522.db`）。

## 6. 回滚

- 代码：回到上一提交/发布目录；本分支未部署，生产不受影响。
- 数据库：`alembic downgrade 20261111_22` 会删除 v4 新增表并移除 `match_results` 的 90 分钟字段；执行前必须备份。
- 会员：后台“撤销”立即生效；计划可停止生成，不影响既有历史。
- 配置：`engine_config` 改动写审计，可按 before/after 恢复。
