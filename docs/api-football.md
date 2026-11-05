# API-Football 接入（免费档优先）

> 状态：代码已接入，默认关闭；配置 `JQ_API_FOOTBALL_KEY` 后启用。当前免费档按 **100 请求/日** 设计，应用默认只用 90，留 10 次人工排查。

## 1. 用途

补当前 Sporttery 采集没有的客观情报：

- fixtures：赛程、状态、联赛/球队 ID
- lineups：首发、阵型、教练、替补
- injuries：伤停/停赛
- standings：积分榜、近况

只做事实，不参与概率预测；缺失就保持 `missing/unknown`，不编造。

## 2. 配置

```env
JQ_API_FOOTBALL_KEY=
JQ_API_FOOTBALL_BASE_URL=https://v3.football.api-sports.io
JQ_API_FOOTBALL_DAILY_LIMIT=90
JQ_API_FOOTBALL_LINEUP_HOURS=6
JQ_API_FOOTBALL_MAX_REQUESTS_PER_RUN=20
```

免费档额度会被持久化到 `api_football_usage`（按 day+endpoint）；超限返回 `ApiFootballBudgetExceeded`，同步任务停止，不影响判决主链。

## 3. 同步命令

```bash
cd jieqiu-backend
python -m app.api_football_cli status --json
python -m app.api_football_cli sync --date 2026-11-04 --json
python -m app.api_football_cli link --fixture 12345 --match 2042508
```

建议 cron（按免费额度调整频率）：

```cron
# 每天 09:10 拉当日 fixtures；只拉一次
10 9 * * * cd /home/ubuntu/jieqiu-backend && python -m app.api_football_cli sync --date $(date +\%F) >> /home/ubuntu/jieqiu-backend/af.log 2>&1
```

免费档不要每 5 分钟全量拉；fixtures 1 次/日，lineups 默认只补开赛前 6 小时窗口（含开赛 2 小时内），injuries 默认补 24 小时窗口，standings 1 次/日/联赛。

## 4. 表

| 表 | 用途 |
|---|---|
| `api_football_fixtures` | fixture 快照、链接到 `sp_matches.match_id`、同步时间 |
| `match_lineups` | 双方首发/替补，`side=home/away` |
| `match_injuries` | 伤停/停赛，幂等键 `(fixture_id, player_id, type)` |
| `team_standings` | 联赛/赛季/球队积分榜快照 |
| `api_football_usage` | 免费额度按日/endpoint 计数 |

迁移：`20261104_06_api_football.py`；down 会删表。

## 5. 队名链接

Sporttery 是中文队名，API-Football 是英文队名，不能硬匹配。

链接策略：

1. 开赛 ±20 分钟内找 `sp_matches` 候选；
2. 双方队名归一化后精确匹配，或通过 `team_aliases` 的英文别名→中文 canonical 匹配；
3. 双方置信度 ≥0.92 且开赛差 ≤10 分钟 → `auto`；
4. 其余 `none`，在 `/admin` 运维页 输入竞彩 `match_id` 人工链接；
5. `link_fixture` 会同步回填已存在的 lineups/injuries 的 `match_id`。

没有英文别名时自动链接率会低；需要逐步补 `team_aliases`（alias 用归一化后的英文名，canonical 用中文名）。

## 6. focus 集成

`GET /matches/{id}/focus` 会读取：

- 已链接 fixture 的 lineups → `intel.facts(kind=lineup)`，覆盖率 `lineups` 权重 15
- injuries → `kind=injury`
- team_standings → `kind=standing`，覆盖率权重 5

`deep_eligible` 新规则：

```text
price+market+model 都新鲜
&& score >= 70
&& 距停售 >= 30 分钟
&& (首发已确认 || 距开赛 >= 12 小时)
```

首发缺失时仍可走“首发未知”的保守深读，但必须明确标注。

## 7. 管理后台

`/admin` 运维页：

- 免费额度使用/剩余
- fixture / 已链接 / 未链接
- lineups / injuries / standings 数量
- 最近同步
- 未链接 fixture 输入 `match_id` 人工链接

`/admin` 数据源页 同屏显示阵容/伤停/积分榜计数与 API-Football 配置状态。

## 8. 风险

- 免费档 100/日，不能全量追所有联赛；只 sync 已链接、临近停售的场次。同步任务按单进程/单 cron 运行；多进程并发时额度检查仍有竞态，当前不并行跑 sync。
- API-Football 不同联赛阵容质量/发布时间不一致；上线前按联赛验证。
- 外部队名/联赛名需持续维护别名，不自动把英文名写进 canonical。
- 不要把 API-Football 的 prediction 当模型概率；概率仍走自有 DC + 三闸。
