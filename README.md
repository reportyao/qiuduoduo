# 球多多 Monorepo

产品：有判断、有参考组合的赛前决策助手；Decision Snapshot → AI Review → Publish 主链已接，`/admin` 运营台已上线，付费与外部合规接入待做，不承诺结果。当前生产前端是 `apps/mobile/`（Expo RN，Android 先发），生产后端仍在 `jieqiu-backend/`（FastAPI），接口契约由 `packages/api-client/` 生成。

| 事实 | 当前值（2026-11-05） |
|---|---|
| 版本 | `0.8.0-w8+assistant` |
| OpenAPI | 128 路径 / 143 方法 |
| 后端测试 | 251 passed |
| 前端测试 | 22 passed + typecheck/lint/bundle |
| 数据库 | 境内 PostgreSQL 16（云托管优先 / 自建兜底，ADR-0004）；未设置 `JQ_PROD_DATABASE_URL` 时仍是旧 SQLite |
| Alembic head | `20261105_12` |

工程入口见 [AGENTS.md](./AGENTS.md)，完整文档索引见 [docs/README.md](./docs/README.md)，2026-11-04 全栈审查（历史快照）见 [docs/reviews/2026-11-04-full-stack.md](./docs/reviews/2026-11-04-full-stack.md)。首页聚焦导航已实现（选中比赛→回首页聚焦）；后端 focus/pulse/interactions 已实现，前端数据脉搏首屏与 `intel_items`/`match_coverage`/`pulse_daily` 情报表仍为设计稿。详见 [docs/focused-decision-flow.md](./docs/focused-decision-flow.md)；新口径下的赛前判断/串关参谋/审核发布见 [docs/recommendation-product.md](./docs/recommendation-product.md)；多模型 fast/deep 路由见 [docs/llm-gateway.md](./docs/llm-gateway.md)（Phase 1 已实现：登录用户 open_chat→fast；匿名 0 LLM；deep/解读待做）。

当前结构：`jieqiu-backend/`（FastAPI 后端，过渡期目录）、`apps/mobile/`（Expo RN）、`packages/api-client/`（OpenAPI 生成 client）、`sp-collector/`（竞彩 SP 采集器）。下文描述仓库内的 SP 采集器。

---

# 竞彩 SP 采集器 v0.1

**采集内容**：体彩官网在售竞彩场次 + SP 赔率（had/hhad 双池 + 让球线 + 单关标记），每 5 分钟一张快照存 SQLite。

**为什么存在**：竞彩无商业数据 API，官方 SP 时间序列必须自采。它是三件东西的数据底座——数②③重测、判决卡实时 SP、竞彩滞后验证（商业模式核心假设）。

## 运行

```bash
export JQ_COLLECTOR_PASSWORD='...'   # SFTP 备份密码；不再写进代码
# 可选：JQ_COLLECTOR_HOST / JQ_COLLECTOR_USER
python collector.py        # 前台
# 当前已以分离进程常驻运行（日志 collector.log）
```

- 出口：**必须家宽**（体彩 WAF 拒机房 IP，服务器直连 567）
- 备份：每 30 分钟 SFTP 推送到 43.128.24.244:/home/ubuntu/jieqiu-sp/
- 容错：连续失败 20 次自动退出（人工重启）；单轮失败只计数不中断

## 表结构

- `matches`: match_no/match_id/league/home/away/kickoff/single_flag
- `sp_snapshots`: match_id/pool/goal_line/sp_h/sp_d/sp_a/captured_at（只追加）

## 已知限制与升级路径

| 限制 | 对策（W2 内定） |
|---|---|
| 依赖本机开机+家宽 | ① 4G 迷你主机 ② 住宅代理+云机 ③ 与常开设备共存 |
| 5min 固定轮询 | 后续：停售前 60min 加密至 60s（尚未实现） |
| 无赛果回填 | 赛果由后端 `sync_results_football_data` 回填，不由采集器写 `settled` |
