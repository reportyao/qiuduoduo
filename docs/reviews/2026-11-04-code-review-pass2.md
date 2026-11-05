# 全项目代码复审第二轮（2026-11-04）

> **历史快照（2026-11-04）**：本文的测试数/路径数/结论反映当时状态，不是当前事实。当前事实见 [docs/README.md](../README.md)：261 tests / 128 路径 / 143 方法 / Alembic `20261105_12`。

范围：`jieqiu-backend`、`apps/mobile`、`packages/api-client`、`sp-collector`；在上一轮全栈深审之后继续修剩余并发/资源/边界问题。

## 本轮修复

### 后端并发与事务

1. **验证码并发消费**：`verify_code` 改为条件 UPDATE 原子增加 attempts、条件 UPDATE 消费；并发正确请求只有一个成功，错误尝试不能绕过上限。
2. **首次登录/设备登录/记忆/通知偏好/推送注册竞态**：`get_or_create_by_phone/email`、`link_identity`、`login_device`、`upsert_memory`、`notify_put`、`push_register` 捕获唯一键冲突并回读/重试，避免双击或并发请求 500。
3. **结算监控全表扫描**：`scan_settlements` 改为 SQL 过滤 `settled_at >= since`，新增 Alembic `20261104_04` 与 ORM 索引 `ix_verdicts_settled_at`；不再先 LIMIT 200 再在 Python 里丢旧数据。
4. **封存时间闪烁**：重建 screening/killed 判决不再清空 `sealed_at`，避免每轮 seed 让“已封存”状态来回跳。
5. **分享卡跨用户串号**：weekly/streak payload 加入 owner 哈希，不同用户即使统计相同也生成不同 share_id；A 注销不会删掉 B 的公开链接。
6. **请求体上限**：中间件拒绝 `Content-Length > 1MB`（413）和非法 Content-Length（400），防止无界 JSON/表单打满内存。

### 采集器

7. **硬编码 SFTP 密码移除**：`sp-collector/collector.py` 改为 `JQ_COLLECTOR_PASSWORD` 环境变量；host/user 也可配置。
8. **坏 SP 入库**：采集器解析时过滤 `SP <= 1`，与后端契约一致，避免脏快照进入管道。

### 前端

9. **登录页自动返回竞态**：只有“进入页面时已登录”才自动返回；提交登录后的跳转统一由 submit 处理，避免 600ms 定时器和提交双重导航。
10. **资料保存后导航**：组件卸载后不再执行返回。
11. **关注删除/周报分享双击**：删除和分享增加 pending 守卫。
12. **为什么不推深链日期**：未带 date 时默认当前竞彩日，不再显示 `--`。
13. **分享验真页 URL 解析**：按 `/verdicts/{id}` 路径段解析，兼容绝对 URL/额外前缀。
14. **账号级本机状态清理**：退出/注销统一重置人设/赔率/头像/PGSI，并删除本机头像文件；“恢复助理形象”也会删除头像文件。

## 验证

- 当时后端：**182 passed**（当前 246）
- 当时 Alembic：空库 `upgrade head` 到 `20261104_04`，`alembic check` 无漂移
- 前端：typecheck / ESLint / **20 Vitest** 通过
- Android Hermes bundle：**3.61 MB `.hbc`** 成功

## 仍保留的风险

- 真实 Postgres/备份/PITR、TLS/反代、控制台 CSRF token、多进程会话仍未完成。
- 真实 JPush、支付、OCR、服务端合规同步、真实 live feed/进球提醒仍未接入。
- `model_runs` 每轮 seed 写放大、静默时段推送计数口径仍待后续优化。
- iOS 原生构建/真机验收未执行。
