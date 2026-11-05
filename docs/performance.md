# 性能基线（2026-11-05）

环境：腾讯云香港 `43.128.24.244`，2 vCPU / 3.7GB，SQLite + WAL，单 uvicorn 进程。
测量：服务端 loopback `httpx` 20 次/接口，p50/p95；客户端在中国大陆，公网 RTT 约 172ms。
复现：`cd jieqiu-backend && venv/bin/python scripts/perf_bench.py`（可设 `JQ_BENCH_BASE` / `JQ_ADMIN_PASSWORD`）。

## 优化前 → 优化后

| 接口 | 优化前 p50 / p95 | 优化后 p50 / p95 | 说明 |
|---|---|---|---|
| `/health` | 7.0 / 10.2 ms | 6.3 / 9.8 ms | 轻量探针 |
| `/health?detailed=1` | 9.2 / 11.0 ms | 8.7 / 9.7 ms | 全表计数 |
| `/stream?limit=50` | 4.3 / 5.4 ms | 4.6 / 5.1 ms | 已缓存组装 |
| `/matches/on-sale` | 29.9 / 35.0 ms | **3.6 / 4.2 ms** | 15s 进程内缓存 + 覆盖批量化 |
| `/stats/pulse` | 77.3 / 176.3 ms | **3.0 / 11.5 ms** | 30s 缓存 + 去掉逐行 strptime |
| `/matches/{id}/focus` | 11.9 / 15.0 ms | 12.5 / 18.3 ms | 单场聚合 |
| `/recommendations/today` | 5.4 / 8.6 ms | 5.7 / 6.9 ms | 复核记录批量查询 |
| `/personas` | 6.5 / 7.3 ms | 6.6 / 7.3 ms | 配置读取 |
| `/admin/api/overview` | — | 14.9 / 18.6 ms | 后台总览 |
| `/admin/api/data` | — | 34.7 / 38.8 ms | 含内容供给/国际盘诊断 |
| `/admin/api/ops` | — | 18.6 / 21.5 ms | 运维聚合 |
| `POST /interactions`（写） | — | 10.6 / 16.3 ms | SQLite 单次提交，30 次顺序 |

> 缓存类接口的 p95 包含首次 miss（约 130–150ms）；命中后接近 0ms。上表为 20 次连续请求的统计。

## 本轮已做的优化

1. **`/stats/pulse`**
   - 30s 进程内缓存（`env=test` 关闭，避免测试串数据）。
   - `_in_window` 改为 ISO 前 19 位字典序比较，去掉每行 `strptime`（原每请求约 1900 次）。
   - 查询数从 30/次 降到首次 30、命中 0。
2. **`/matches/on-sale`**
   - 15s 进程内缓存；覆盖计算不再每次全量重算。
3. **推荐复核记录**
   - `/recommendations/today` 的 `ReviewRun` 改为一次 `IN` 查询 + 内存映射，消除 N+1。
4. **传输压缩**
   - 加 `GZipMiddleware`（>1KB）。`/matches/on-sale` 从 10,494B → 981B（-91%）。
5. **SQLite**
   - WAL 下 `synchronous=NORMAL`、`temp_store=MEMORY`、`cache_size≈20MB`、`mmap_size=64MB`。
6. **后台静态资源**
   - `Cache-Control: no-cache` 允许 ETag/304 复用（原 `no-store` 每次全量下载）。
7. **移动端包体**
   - `@expo/vector-icons/Ionicons` 直接导入，避免打包全部图标字体。
   - Android Hermes bundle **3.68MB → 3.37MB**，静态资源 45 → 27，字体 19 → 1。
8. **移动端轮询**
   - stream / on-sale / today / pulse / inbox 从 60s 调到 120s；focus 保持 60s。
   - 首页并发请求从 5 次/分钟降到约 2–3 次/分钟。

## 结论与限制

- **应用内计算已不是瓶颈**：除首次 pulse 外，所有公开接口 p50 ≤ 13ms；后台最慢的数据源页 35ms。
- **真正的延迟来自网络和部署位置**：香港到大陆实测 RTT ~172ms，单次请求约 350–400ms；移动端 5 个接口并行时首屏主要受 RTT 影响。
- **并发基准的注意事项**：在 2 vCPU 服务器上同时跑 20 个压测线程会与 uvicorn 抢 CPU，得到 600–900ms 的 p50，不代表外部真实并发；外部压测应使用独立客户端。
- **SQLite 仍是单写者**：WAL 提升了读写并发，但高并发写入/多 worker 仍应切 PostgreSQL（ADR-0002/0004）。
- **尚未做**：APK 实际体积/启动时间、HTTP/2、CDN、Postgres 压测、真机弱网首屏。

## 下一步建议

1. 生产入口加 **CDN/全站加速** 或迁到大陆/香港 CN2 线路，优先解决 RTT。
2. 上 **PostgreSQL** 后做 50–100 并发压测；SQLite 阶段不要把并发目标定得过高。
3. 移动端首屏加 **骨架屏 + 请求合并**（stream/today/pulse 可由一个 `/home/bootstrap` 聚合，减少请求数）。
4. 对 `pulse` 首次 miss 做启动预热或后台定时刷新，避免缓存过期后的首个用户等待。
