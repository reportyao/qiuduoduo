# 全栈深度审查与修复记录（2026-11-04）

> **历史快照（2026-11-04）**：本文的测试数/路径数/结论反映当时状态，不是当前事实。当前事实见 [docs/README.md](../README.md)：265 tests / 128 路径 / 143 方法 / Alembic `20261105_13`。

范围：`jieqiu-backend`（业务/事务/鉴权/推送/封存链）、管理后台 `/console`、OpenAPI 契约、`apps/mobile`（会话/合规/交易/交互）。

## 审查方式

- FastAPI 路由/ORM/任务逐文件阅读，并对可疑路径做内存 SQLite 复现；
- 管理后台按攻击面检查（会话、CSRF、XSS、爆破、白名单、错误页）；
- 移动端按真实用户流程检查（冷启动、登录/退出、下注、撤销、后台恢复、跨 05:00 日界）；
- 全量测试 + typecheck/lint + Android Hermes bundle。

## 已修复（高优先级）

### 后端

1. **模型闸门与最终 pick 不一致**：原来按 `max(p_model)` 放行，却发布 EV 最大的方向，可能 20% 概率的客胜高赔被 55% 主胜“带过闸”。改为按实际 `pick.prob` 放行；补测试。
2. **推送 worker 崩溃后永久卡 `sending`**：`sending` 行没有回收路径，且认领不是原子操作。改为 `pending` + 过期 `sending` 都可认领，条件 UPDATE + rowcount 抢占；超过重试上限标记失败；补测试。
3. **单条 SP=1.0 拖垮整日判决**：契约改为 `>1.0`，`build_verdicts` 对坏快照逐场跳过，不再让整轮 seed 失败。
4. **封存链**：
   - 迟到的过去日修订触发重建旧锚会永久破坏后一天链；`build_anchor` 现在拒绝重写已出现更晚锚点的日期；
   - `link_revision` 只取链尾 hash，不再加载整日 payload（O(n²) → O(1) 查询/节）；
   - Postgres 下用事务级 advisory lock 串行化链尾，避免两个 seed 同时分叉。
5. **交易窗口重叠**：统一为 `[D 05:00, D+1 04:59]`；新增 `modules/timeutil.py`，修正 `seed`、`/stream`、`/matches/on-sale`、`/matches/sale-schedule`、catalog 日期窗口；`seed` 用墙钟决定销售日，避免 00:20 生成第二天的重复判决。
6. **close_soon 事件不失效**：事件写入 `expires_at=kickoff`，worker 积压后不会在开赛后发“还有 N 分钟”。
7. **team/league 关注无法触发**：在事件源接入前明确 422，不再保存一个永远不会通知的“假关注”。
8. **check-then-insert 竞态**：watch/follow 与分享卡创建捕获唯一键冲突并返回已存在记录；分享验证增加 `share_id == content_hash[:12]` 校验。
9. **大表无界读取**：`ledger_stats` 只取 `settled` 一列 + COUNT；`killed_outcomes` 在 SQL 里按 7 天过滤；`sp_movements` 改范围查询；`/matches/{id}/cost` 只取最新快照 + COUNT。
10. **chat 跨日期乱推荐**：只取今日 promoted/killed；周报只统计 `0 <= age <= 7` 且不超过今天。
11. **hhad 空让球线按 1x2 结算**：空让球线场次跳过，避免标签与结算口径不一致。
12. **旧注单 P&L 高估**：无 SP 的赢单返回未知，不再按 +100% 利润计算。
13. **输入边界**：手机号/邮箱/purpose/token/device_token/memory/push token 等加 `max_length`；int 路径参数加 `ge/le`，超大 id 返回 422 而非 500。
14. **auth fail-open**：`auth_stub` 只在显式 `dev/test` 生效；staging/development 等拼写不再返回 dev_code/假 OAuth；`.env.example` 改 `JQ_ENV=dev`、`JQ_AUTH_STUB=false`。
15. **设备 region 校验**：非法 region 在创建/已有设备路径都返回 422，不再只校验新建账号。

### 管理后台

1. **存储型 XSS**：`/console` 日报的球队/编号/状态/锚点/快照时间全部 `html.escape`；变体表单属性也转义。
2. **会话令牌进 URL/日志**：登录重定向、导航、表单不再带 `?t=`；`_authed` 只认 HttpOnly cookie；新增 `/console/logout`。
3. **每请求白名单**：`_authed` 现在每次校验 IP 白名单，支持 CIDR；不再只在登录时检查。
4. **非 ASCII 密码 500**：改用 SHA-256 摘要后 `compare_digest`；错误密码返回 401 并计数。
5. **配置来源**：`console_password`/`console_ip_whitelist` 进入 `Settings`，`.env` 生效；非 dev/test 未配置密码 fail closed。
6. **登录爆破**：失败计数加锁，超限清理不再整体清空所有 IP；返回 `Retry-After`。
7. **安全头**：控制台页面加 `Cache-Control: no-store`、`Referrer-Policy: no-referrer`、`X-Frame-Options: DENY`、`nosniff`、CSP。
8. **告警页坏时间戳**：格式异常时显示告警而不是整页 500。
9. **部署**：控制台密码/白名单写入 0600 env 文件，SFTP 写后先 chmod；生产显式 `JQ_AUTH_STUB=false`。

### 前端

1. **刷新失败销毁账号**：只有 401/403 才清会话；5xx/429/网络错误保留 session。
2. **设备登录竞态**：`loginWithDevice` 增加 authEpoch，旧响应不能覆盖新登录/退出；logout 单飞 + 2 秒去重，避免多个 410 连环创建游客。
3. **401 恢复**：统一触发一次 logout/新游客，不再永久卡在 401。
4. **自排除持久化**：写失败不再显示“已生效”；读取失败标记 `storageError`；UI 保存成功后才跳转。
5. **下注金额不一致**：成功页/复制文案使用服务端返回的 `created.amount`；提交中锁金额 stepper/chips。
6. **连败保护提示**：正确解析 423 的 `detail.detail.streak`。
7. **撤销窗口**：用绝对截止时间重算，后台/定时器节流后不会显示虚假剩余秒数。
8. **串关缺 rake**：无抽水快照的复核场直接排除，不再按 0 成本计算返还率。
9. **05:00 日界**：首页/串关在跨日后自动跟随今天，用户手动选旧日期时不打扰。
10. **分享**：后端增加 `/s/{share_id}` 公开 HTML 落地页；App 分享包含 HTTPS 链接 + 深链。
11. **深链返回**：新增 `goBackOr`，24 个页面冷启动返回键不再失效。
12. **收件箱**：先按本地深链导航，已读/点击上报 best-effort；不支持链接给出提示。
13. **缓存隔离**：通知设置只更新当前 userId 的精确 query key，不再污染其他账号。
14. **未保存草稿**：通知/资料页前台刷新不再覆盖正在编辑的内容。
15. **通知类型**：用 `__none__` 哨兵支持“最后一个类型也能关”；后端 fanout 对哨兵自然不匹配。
16. **SecureStore 复活**：原生端不再回落明文 AsyncStorage；删除失败写 tombstone，防止旧账号复活。
17. **法务页**：对 `privacy` 字段缺失做 optional chaining。
18. **构建校验**：release 构建必须 HTTPS API URL，否则启动 fail loud；计时器在请求完成/失败后清理。
19. **记录/我的**：补下拉刷新和错误态；在售倒计时使用共享时钟。

## 验证

- 当时后端：**179 passed**（当前 246）
- 前端：typecheck / ESLint / **20 Vitest** 通过
- Android Hermes bundle：**3.6 MB `.hbc`** 成功
- 当时 OpenAPI client：重新生成快照（94 路径 / 107 方法；当前 128/143）并 typecheck
- 新增回归：模型闸门、worker 过期租约、封存锚冻结、XSS、分享 HTML、超大 path id、交易窗口、auth stub fail-closed

## 仍未修复 / 上线前必须补

- **真实 TLS/反代**：控制台当前仍由 uvicorn 直连；生产必须 TLS 终止并将 uvicorn 绑定内网/localhost。代码只保证 cookie/URL 不再泄漏。
- **CSRF token**：控制台已移除 query token + SameSite=Strict，但表单仍没有显式 CSRF token。
- **多进程后台**：`_SESSIONS`/`_VARIANT_POOL` 仍是进程内存；多 worker 需 Redis/DB 会话。
- **推送频控**：静默期 scheduled_at 与今日 cap 的计数口径仍可优化；真实 JPush 凭证未接。
- **合规服务端**：自排除/PGSI 仍本机强制，多设备同步未实现。
- **索引/写放大**：`scan_settlements` 的 `settled_at` 仍未加索引，`model_runs` 每次 seed 仍写三行/场；需下一轮数据层优化。
- **前端剩余**：Profile 头像文件清理、年龄门跨账号重置、Toast 在原生 Modal 内可见性、部分大字体布局、iOS 原生构建未验证。
- **响应模型**：老端点仍有大量 dict 返回，未在本次全面改成 Pydantic（避免破坏现有移动端契约）。

## 复核命令

```bash
cd jieqiu-backend && python -m pytest -q
cd ../apps/mobile && corepack pnpm typecheck && corepack pnpm lint && corepack pnpm test
EXPO_PUBLIC_API_BASE_URL=https://api.example.com EXPO_PUBLIC_APP_ENV=staging \
  corepack pnpm exec expo export --platform android --output-dir .export-check --clear
```
