# v4.1 交付验证（2026-11-12）

> 分支：`feat/v4-plan-settlement`  
> 范围：4 Tab、HeaderMetrics、每日 AI 战绩、4 场定投计划、会员权益/手动开通、90 分钟结算、人设 chat、OPC 后台。  
> 结论：**代码与文档通过本地测试与模拟器验收；生产未部署、v4 APK 未构建。**

## 1. 自动验证

| 项 | 命令 | 结果 |
|---|---|---|
| 后端 | `cd jieqiu-backend && python -m pytest -q` | **338 passed**（1309 warnings，主要为 NumPy/Pandas 弃用告警） |
| 前端 | `cd apps/mobile && corepack pnpm test -- --run` | **47 passed / 13 files** |
| 类型 | `corepack pnpm typecheck` | 通过 |
| Lint | `corepack pnpm lint` | 通过 |
| Bundle | `corepack pnpm exec expo export --platform android --output-dir .export-check --clear` | 通过（Metro + Hermes） |
| OpenAPI | 读取 `packages/api-client/openapi.json` | **158 路径 / 174 方法** |
| 迁移 | `alembic heads` / 迁移文件 | 单一 head `20261112_23`，up/down 成对 |

后端新增测试重点：

- `tests/test_v4_core.py`：90 分钟 outcome、整数亚盘 void、稳健计划 4 场、Max 计划门控、计划结算、引擎 uptime、过期候选过滤、chat persona/record。
- `tests/test_admin_v4.py`：后台 v4 视图、App 用户手机/邮箱脱敏、手动开通/撤销、引擎配置、OPS、计划列表。

## 2. 模拟器验收

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

## 3. 本轮修复

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

## 4. 明确未完成

- 真实支付/订单/回调；会员只能后台手动开通。
- 多盘口完整数据：计划与 HeaderMetrics 的“5 盘口”目前是配置展示，实际计划只处理 1X2/让球。
- 计划自训练模型：只有 `feature_snapshots/model_registry/training_runs` 脚手架。
- 计划更新提醒/收藏；不做跟单/自动记注/代购。
- 生产 Postgres 切库、备份/PITR 恢复演练。
- v4 正式 APK 构建/签名/发布、iOS、真机 JPush。
- 生产部署：本轮只提交代码/文档，未执行 `deploy.py`。

## 5. 回滚

- 代码：回到上一提交/发布目录；本分支未部署，生产不受影响。
- 数据库：`alembic downgrade 20261111_22` 会删除 v4 新增表并移除 `match_results` 的 90 分钟字段；执行前必须备份。
- 会员：后台“撤销”立即生效；计划可停止生成，不影响既有历史。
- 配置：`engine_config` 改动写审计，可按 before/after 恢复。
