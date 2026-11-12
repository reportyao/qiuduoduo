# v4.1 交付验证（2026-11-12）

> 分支：`feat/v4-plan-settlement`  
> 范围：4 Tab、HeaderMetrics、每日 AI 战绩、4 场定投计划、会员权益/手动开通、90 分钟结算、人设 chat、OPC 后台。  
> 结论：**代码、文档、腾讯云生产部署与 v4 APK 安装验收均已通过；正式签名/上架未做。**

## 1. 自动验证

| 项 | 命令 | 结果 |
|---|---|---|
| 后端 | `cd jieqiu-backend && python -m pytest -q` | **349 passed**（1309 warnings，主要为 NumPy/Pandas 弃用告警） |
| 前端 | `cd apps/mobile && corepack pnpm test -- --run` | **53 passed / 15 files** |
| 类型 | `corepack pnpm typecheck` | 通过 |
| Lint | `corepack pnpm lint` | 通过 |
| Bundle | `corepack pnpm exec expo export --platform android --output-dir .export-check --clear` | 通过（Metro + Hermes） |
| OpenAPI | 读取 `packages/api-client/openapi.json` | **158 路径 / 174 方法** |
| 迁移 | `alembic heads` / 迁移文件 | 单一 head `20261112_24`，up/down 成对 |

后端新增测试重点：

- `tests/test_v4_core.py`：90 分钟 outcome、整数亚盘 void、稳健计划 4 场、Max 计划门控、计划结算、引擎 uptime、过期候选过滤、chat persona/record。
- `tests/test_admin_v4.py`：后台 v4 视图、工作台未知年龄文案、App 用户手机/邮箱脱敏、手动开通/撤销、引擎配置、OPS、计划列表。
- `tests/test_sportmonks_model.py`：Sportmonks 1X2 概率校验/过期、正确比分推导让球盘、DC 缺阵时后备模型判决。
- `tests/test_recommendations.py`：判决降级后旧 published 快照必须过期，不能继续出现在 `/recommendations/today`。

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
| 首页显示 0 核验/0 发布，欧国联无数据 | Sportmonks 新订阅下 6 场 fixture 全部映射成功；补 `欧国联 → soccer_uefa_nations_league` 的 Odds API 映射，预测/赔率/情报全部入库 |
| 让球盘误把 1X2 模型概率套到 hhad | 解析 Sportmonks 正确比分分布，按竞彩让球线推导 hhad 概率；无比分分布则诚实 pending |
| 判决降级后旧 published 快照仍在首页 | `build_snapshots()` 主动过期不再是 promoted/settled 的 active 快照 |
| 右上角“今日采集全网 X 条数据点” | 改为“今日采集 X 条数据点” |
| 首页聚焦卡不在对话流里、返回/重开丢历史 | 选中比赛后由助理在对话末尾追加比赛页卡；按用户+竞彩日写入 AsyncStorage，返回/重开恢复今日对话；长页卡按顶部对齐滚动 |
| 底部输入框过大常驻 | 默认收起为右下角圆形图标，点击展开输入条，可收起；发送后保持展开便于连续追问 |
| 详情页把 Sportmonks 模型标成“模型影子” | 概率对比与详情徽章显示“Sportmonks 模型/预测”，并保留未验证状态 |
| 聚焦页显示“首发/伤停未接入、积分榜未同步” | 新增 `sportmonks_fixture_intel/predictions/markets`；首发/阵型/伤停/积分榜/H2H/天气/裁判/教练/多市场预测落库并接入 Focus |
| 详情页缺少阵容、积分榜、环境、预测参考 | 新增 `SportmonksIntelSection`：首发与阵型、积分榜与近况、场地与环境、Sportmonks 预测参考、赛前动态、赛后复盘 |
| AI 情报只有 H2H 摘要 | AIResearch fact pack 扩展为首发/伤停/积分榜/场地天气/裁判/多市场预测；focus facts 17 条、unknowns 清空 |
| HeaderMetrics 把 5/7 配置当实际数据 | 改为“5 盘口 · N 预测 · N 场首发”，数据来自 pulse；数据状态页增加 Sportmonks 阵容/积分榜/环境源 |
| 后台矩阵缺少阵容/积分榜覆盖 | 增加 `with_lineups/with_standings/with_predictions` 与逐场阵容、阵型、积分榜、天气、伤停、预测列 |
| 赛后只有比分，没有 xG/事件 | 赛果回填后同步 `xGFixture/events` 到 intel payload 的 `postmatch`，详情页可展示比分、xG、进球时间线 |

## 5. 明确未完成

- 真实支付/订单/回调；会员只能后台手动开通。
- 多盘口完整数据：计划仍只处理 1X2/让球；HeaderMetrics 已改为真实预测维度/首发覆盖，大小球/BTTS/半全场/正确比分只做情报展示，未进入计划或付费区。
- 计划自训练模型：只有 `feature_snapshots/model_registry/training_runs` 脚手架。
- 计划更新提醒/收藏；不做跟单/自动记注/代购。
- 生产 Postgres 切库、备份/PITR 恢复演练。
- v4 APK 已由 GitHub Actions 构建（最终 run `43191064481`，commit `8a6a461`）并在 MuMu 安装验证；正式签名/上架、iOS、真机 JPush 仍未做。安装包：`C:/Users/26363/Downloads/qiuduoduo-v41-20261112-intel.apk`。
- 生产部署已完成（2026-11-12 11:38 CST）：`deploy.py` 部署到 `43.128.24.244`，`/health` 200，OpenAPI 158/174，管理后台静态资源 v=20261112d；生产仍为 SQLite。部署前备份在 `/home/ubuntu/backups/`（代码 `jieqiu-backend-20261112-113522.tar.gz`、库 `jieqiu-20261112-113522.db`）。
- Sportmonks 订阅更新后（2026-11-12 13:44 CST）：生产重新同步 6/6 场欧国联，全部有 Pinnacle 去水赔率、1X2 预测和正确比分分布；AI 情报 6/6 同步。重建后 `周四001` 为 verified/promoted，`周四002/004/005` 为市场参考，`周四003/006` 不建议；`/recommendations/today` 返回 1 published snapshot + 3 references。重算前库备份：`/home/ubuntu/backups/jieqiu-20261112-134211-pre-rebuild.db`。

## 6. 回滚

- 代码：回到上一提交/发布目录；本分支未部署，生产不受影响。
- 数据库：`alembic downgrade 20261111_22` 会删除 v4 新增表并移除 `match_results` 的 90 分钟字段；执行前必须备份。
- 会员：后台“撤销”立即生效；计划可停止生成，不影响既有历史。
- 配置：`engine_config` 改动写审计，可按 before/after 恢复。
