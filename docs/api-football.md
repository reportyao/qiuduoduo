# API-Football 接入（免费档优先）

> 状态：代码已接入，默认关闭；配置 `JQ_API_FOOTBALL_KEY` 后启用。当前免费档按 **100 请求/日** 设计，应用默认只用 90，留 10 次人工排查。**2026-11-05 生产未配置**：当前 key 属于 **apifootball.com**（不是 API-Sports/RapidAPI），已实测 Free 档可访问 countries/leagues/standings；但免费档 events 不覆盖五大联赛，英超等返回 `404 No event found (please check your plan)`。五大联赛/欧冠需 European $21/月起；升级后再接入 `apifootball` provider；当前代码的 provider 仅支持 `apisports` / `rapidapi`。`deploy.py` 已修复为合并远端 env 并自动备份，不会再因重部署丢失已有 key。

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
JQ_API_FOOTBALL_LINEUP_HOURS=6
JQ_API_FOOTBALL_MAX_REQUESTS_PER_RUN=20
```

- `apisports`：请求头 `x-apisports-key`。
- `rapidapi`：请求头 `x-rapidapi-key` + `x-rapidapi-host`；**必须在同一 RapidAPI 账号订阅 API-Football（免费 $0 档也要点 Subscribe）**，否则 key 存在也会返回 `403 You are not subscribed to this API`。
- `401 Invalid API key` 是 key 本身无效/缺失；`403` 是订阅未生效，两者不要混为一谈。

免费档额度会被持久化到 `api_football_usage`（按 day+endpoint）；超限返回 `ApiFootballBudgetExceeded`，同步任务停止，不影响判决主链。

## 3. 同步命令

```bash
cd jieqiu-backend
python -m app.api_football_cli status --json
python -m app.api_football_cli sync --date 2026-11-04 --json
python -m app.api_football_cli link --fixture 12345 --match 2042508

# 直接验订阅（RapidAPI；不要把 key 打进命令历史）
curl -sS -o /tmp/af.json -w '%{http_code}
'   -H "x-rapidapi-key: $JQ_API_FOOTBALL_KEY"   -H "x-rapidapi-host: ${JQ_API_FOOTBALL_RAPIDAPI_HOST:-api-football-v1.p.rapidapi.com}"   'https://api-football-v1.p.rapidapi.com/v3/status'
cat /tmp/af.json
```

cron：**配置了 `JQ_API_FOOTBALL_KEY` 的部署，`deploy.py` 会自动安装每日 06:15 的 sync cron**（无需手装）；未配置则不装。手动执行或自定义频率时参考：

```cron
# 每天拉当日 fixtures；只拉一次（deploy 自动安装的是 15 6 * * *）
15 6 * * * cd /home/ubuntu/jieqiu-backend && python -m app.api_football_cli sync --date $(date +\%F) >> /home/ubuntu/jieqiu-backend/api_football.log 2>&1
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
