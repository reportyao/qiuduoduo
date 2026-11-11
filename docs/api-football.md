# API-Football 接入（免费档优先）

> **2026-11-11 收口**：主市场已切到 Sportmonks Pinnacle，API-Football 只作辅助数据源（阵容 / 伤停 / 积分榜），不参与发布前置。后台不再展示 API-Football 大卡片，只在「辅助数据」表和运维页显示额度/覆盖。

> 状态：**生产已配置 API-Sports `apisports` Free 档**（100 请求/日、10 请求/分钟）。已跑通当天+次日 fixtures、已链接场次的 lineups/injuries；2026-11-05 实测目标窗口 23/23 场全部链接；后台按“今日/明日”分开显示，次日未同步不会误报。**当前赛季 standings 被 Free 档拒绝**（`Free plans do not have access to this season`）；lineups 通常在停售前才发布，由每小时 `sync-enrich` 补充。`apifootball.com` 是另一家 provider（`APIkey` 查询参数），当前代码未接入。生产设置 `JQ_API_FOOTBALL_STANDINGS_ENABLED=false`，避免 Free 档每次同步浪费 standings 请求；升级付费档后改为 true。

后台 `/admin` 的「数据源/运维」页现在展示 API-Football 结构化卡片：目标场次链接数、目标阵容/伤停、积分榜、今日额度条、剩余次数与 warnings（未链接/阵容待发布/积分榜关闭/额度不足）。

## 1. 用途

补当前 Sporttery 采集没有的客观情报：

- fixtures：赛程、状态、联赛/球队 ID
- lineups：首发、阵型、教练、替补
- injuries：伤停/停赛
- standings：积分榜、近况

只做事实，不参与概率预测；缺失就保持 `missing/unknown`，不编造。

## 2. 配置

```env
# API-Sports 官方直连（key 形如 32/64 位十六进制）
JQ_API_FOOTBALL_PROVIDER=apisports
JQ_API_FOOTBALL_KEY=
JQ_API_FOOTBALL_BASE_URL=https://v3.football.api-sports.io

# 或 RapidAPI 市场（key 是 RapidAPI key，不是 API-Sports key）
# JQ_API_FOOTBALL_PROVIDER=rapidapi
# JQ_API_FOOTBALL_RAPIDAPI_HOST=api-football-v1.p.rapidapi.com

JQ_API_FOOTBALL_DAILY_LIMIT=90
JQ_API_FOOTBALL_MIN_INTERVAL_S=7
JQ_API_FOOTBALL_LINEUP_HOURS=6
JQ_API_FOOTBALL_MAX_REQUESTS_PER_RUN=10
```

- `apisports`：请求头 `x-apisports-key`。
- `rapidapi`：请求头 `x-rapidapi-key` + `x-rapidapi-host`；**必须在同一 RapidAPI 账号订阅 API-Football（免费 $0 档也要点 Subscribe）**，否则 key 存在也会返回 `403 You are not subscribed to this API`。
- `401 Invalid API key` 是 key 本身无效/缺失；`403` 是订阅未生效，两者不要混为一谈。

免费档额度会被持久化到 `api_football_usage`（按 day+endpoint）；超限返回 `ApiFootballBudgetExceeded`，同步任务停止，不影响判决主链。API-Sports Free 还有 **10 次/分钟**限制，`_request` 默认 7 秒节流；否则会返回 429。2026-11-05 实测 Free 档 **当天+次日 fixtures 可用**，但 **当前赛季 standings 被拒绝**（`Free plans do not have access to this season`）。

## 3. 同步命令

```bash
cd jieqiu-backend
python -m app.api_football_cli status --json
python -m app.api_football_cli sync --date 2026-11-05 --next-day --json
python -m app.api_football_cli sync-enrich --lineups-max 2 --injuries-max 1 --json
python -m app.api_football_cli link --fixture 12345 --match 2042508

# 验订阅（API-Sports 直连；不要把 key 打进命令历史）
curl -sS -o /tmp/af.json -w '%{http_code}\n' \
  -H "x-apisports-key: $JQ_API_FOOTBALL_KEY" \
  'https://v3.football.api-sports.io/status'
cat /tmp/af.json
```

cron：**配置了 `JQ_API_FOOTBALL_KEY` 的部署，`deploy.py` 会自动安装每日 06:15 的 sync cron**（无需手装）；未配置则不装。手动执行或自定义频率时参考：

```cron
# 每天 06:15 拉今天+明天 fixtures，并补一次阵容/伤停
15 6 * * * cd /home/ubuntu/jieqiu-backend && python -m app.api_football_cli sync --date $(date +\%F) --next-day >> api_football.log 2>&1
# 比赛日 0–4 / 10–23 点每小时只补 2 场阵容 + 1 场伤停
0 0-4,10-23 * * * cd /home/ubuntu/jieqiu-backend && python -m app.api_football_cli sync-enrich --json >> api_football.log 2>&1
```

免费档不要每 5 分钟全量拉；fixtures 每日 1 次（今天+明天），lineups 只补开赛前 6 小时窗口，injuries 补 24 小时窗口。`sync-enrich` 单次只发 2+1 个请求，靠每小时 cron 逐步补齐；lineups 常见于停售前 1 小时才发布，空数组是正常现象，不能当失败。

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
