# 球多多 · 竞彩主数据模型（JC-first）

> 目标：以中国竞彩场次为唯一事实源，外部数据源（Sportmonks / API-Football / The Odds API / 未来任何源）只做增强，不允许反向生成或覆盖竞彩场次。
>
> 本文是目标结构；现有 `sp_matches` / `sp_snapshots` / `team_aliases` 通过增量迁移演进，不一次性重写。

## 1. 设计原则

1. **竞彩 `match_id` 是根主键。** 体彩官方 `matchId` 唯一、稳定；`match_no`（周六001）只用于展示，不能当主键。
2. **`trade_date` 是竞彩业务日。** 以中国时间 05:00 切日，一场 03:00 开赛的比赛属于前一个销售日；不能用 `kickoff` 的日历日代替。
3. **赔率只追加，不更新。** `jc_odds_snapshots` 是 append-only；最新值用视图/窗口查询，历史快照必须可复算。
4. **外部源只挂接，不建场。** 任何 fixture 必须先映射到已有 `match_id`；映射不上的外部比赛可以存原始快照，但不能进入竞彩主表、不能进入推荐链。
5. **每个外部快照都带来源与截止时间。** `source`、`source_ref`、`captured_at`、`data_cutoff`、`payload_hash` 五件套缺一不可。
6. **未映射的竞彩场次仍然合法。** 它只有 SP、没有国际盘/阵容；`coverage.deep_eligible=false`，AI 解读显示“数据不足”，不能伪造。
7. **所有写入幂等。** 用 `UNIQUE` + `ON CONFLICT`；采集器重跑、网络重试、SFTP 重推都不能产生重复快照。

## 2. 关系图

```text
jc_leagues 1 ── n jc_matches
jc_teams   1 ── n jc_matches (home_team_id / away_team_id)
jc_matches 1 ── n jc_odds_snapshots
jc_matches 1 ── n jc_source_links ── n 外部 fixture（Sportmonks / API-Football / Odds API）
jc_matches 1 ── n jc_match_features
jc_matches 1 ── 1 jc_results
jc_matches 1 ── n ai_analyses
jc_leagues 1 ── n jc_league_daily
```

## 3. 表结构

### 3.1 `jc_fetch_raw`：原始抓取层（可选但推荐）

保存每次采集的原始 JSON，用于回放、排错、审计。生产可按月分区/定期归档。

```sql
CREATE TABLE jc_fetch_raw (
  id            BIGSERIAL PRIMARY KEY,
  source        VARCHAR(16)  NOT NULL,          -- sporttery
  endpoint      VARCHAR(64)  NOT NULL,          -- getMatchCalculatorV1
  trade_date    VARCHAR(10)  NOT NULL,          -- 抓取时所属竞彩日
  fetched_at    TIMESTAMPTZ  NOT NULL,
  payload_hash  CHAR(64)     NOT NULL,          -- sha256(payload)
  payload       JSONB        NOT NULL,
  UNIQUE (source, endpoint, payload_hash)
);
```

### 3.2 `jc_leagues`：联赛/杯赛字典

```sql
CREATE TABLE jc_leagues (
  id                     SERIAL PRIMARY KEY,
  code                   VARCHAR(32)  NOT NULL UNIQUE,  -- ITA_SERIE_A / ENG_EFL_TROPHY
  name_cn                VARCHAR(64)  NOT NULL UNIQUE,  -- 意甲 / 英锦标赛
  name_en                VARCHAR(128) NOT NULL DEFAULT '',
  country_code           CHAR(2)      NOT NULL DEFAULT '',  -- IT / GB / CN
  is_cup                 BOOLEAN      NOT NULL DEFAULT FALSE,
  sportmonks_league_id   INTEGER      NULL,
  api_football_league_id INTEGER      NULL,
  active                 BOOLEAN      NOT NULL DEFAULT TRUE,
  created_at             TIMESTAMPTZ  NOT NULL DEFAULT now()
);
```

要点：中文联赛名是竞彩口径；`code` 是内部稳定标识，避免中文改名导致映射断裂。

### 3.3 `jc_teams` + `team_aliases`：球队字典

```sql
CREATE TABLE jc_teams (
  id                    SERIAL PRIMARY KEY,
  name_cn               VARCHAR(128) NOT NULL UNIQUE,  -- 规范中文名
  name_en               VARCHAR(128) NOT NULL DEFAULT '',
  country_code          CHAR(2)      NOT NULL DEFAULT '',
  sportmonks_team_id    BIGINT       NULL UNIQUE,
  api_football_team_id  BIGINT       NULL UNIQUE,
  active                BOOLEAN      NOT NULL DEFAULT TRUE,
  created_at            TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 现有 team_aliases 增加 team_id，保留 alias/canonical 兼容旧代码
ALTER TABLE team_aliases ADD COLUMN team_id INTEGER NULL REFERENCES jc_teams(id);
```

要点：`alias` 是归一化后的中文别名；`canonical` 保留给旧逻辑；新逻辑一律用 `team_id`。

### 3.4 `jc_matches`：竞彩场次主表

```sql
CREATE TABLE jc_matches (
  match_id        VARCHAR(32) PRIMARY KEY,          -- 体彩官方 matchId
  match_no        VARCHAR(16) NOT NULL,             -- 周六001，展示用
  trade_date      VARCHAR(10) NOT NULL,             -- 竞彩业务日 YYYY-MM-DD
  league_id       INTEGER     NOT NULL REFERENCES jc_leagues(id),
  league_name_cn  VARCHAR(64) NOT NULL DEFAULT '',  -- 抓取时快照
  home_team_id    INTEGER     NOT NULL REFERENCES jc_teams(id),
  away_team_id    INTEGER     NOT NULL REFERENCES jc_teams(id),
  home_name_cn    VARCHAR(128) NOT NULL DEFAULT '', -- 抓取时快照
  away_name_cn    VARCHAR(128) NOT NULL DEFAULT '',
  kickoff_cn      VARCHAR(32) NOT NULL,             -- "YYYY-MM-DD HH:MM:SS" 中国时间
  kickoff_utc     TIMESTAMPTZ NOT NULL,             -- 用于跨源对齐
  sell_status     VARCHAR(16) NOT NULL DEFAULT 'unknown', -- on_sale/closed/cancelled/unknown
  single_flag     BOOLEAN     NOT NULL DEFAULT FALSE,
  pool_codes      JSONB       NOT NULL DEFAULT '[]',-- ["had","hhad"]
  source          VARCHAR(16) NOT NULL DEFAULT 'sporttery',
  first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (trade_date, match_no)
);

CREATE INDEX ix_jc_matches_trade_league ON jc_matches (trade_date, league_id);
CREATE INDEX ix_jc_matches_kickoff_utc  ON jc_matches (kickoff_utc);
CREATE INDEX ix_jc_matches_home         ON jc_matches (home_team_id);
CREATE INDEX ix_jc_matches_away         ON jc_matches (away_team_id);
```

要点：

- `match_no` 只在同一 `trade_date` 内唯一；跨周会重复，不能做全局唯一。
- `home_name_cn/away_name_cn/league_name_cn` 是抓取快照，队名归一化后仍保留原值，方便回溯。
- `kickoff_utc` 必须由 `kickoff_cn` 换算，统一 UTC；不要用本地时区猜。

### 3.5 `jc_odds_snapshots`：SP 快照（追加式）

```sql
CREATE TABLE jc_odds_snapshots (
  id           BIGSERIAL PRIMARY KEY,
  match_id     VARCHAR(32) NOT NULL REFERENCES jc_matches(match_id),
  pool_code    VARCHAR(8)  NOT NULL,          -- had / hhad
  goal_line    NUMERIC(4,1) NOT NULL DEFAULT 0, -- hhad 让球线；had 为 0
  sp_home      NUMERIC(6,3) NOT NULL,
  sp_draw      NUMERIC(6,3) NOT NULL,
  sp_away      NUMERIC(6,3) NOT NULL,
  captured_at  TIMESTAMPTZ NOT NULL,
  source       VARCHAR(16) NOT NULL DEFAULT 'sporttery',
  raw_id       BIGINT NULL REFERENCES jc_fetch_raw(id),
  CHECK (sp_home > 1.0 AND sp_draw > 1.0 AND sp_away > 1.0),
  UNIQUE (match_id, pool_code, goal_line, captured_at)
);

CREATE INDEX ix_jc_odds_match_time ON jc_odds_snapshots (match_id, captured_at DESC);
```

最新 SP 用视图，不物理覆盖：

```sql
CREATE VIEW jc_odds_latest AS
SELECT DISTINCT ON (match_id, pool_code, goal_line)
       match_id, pool_code, goal_line, sp_home, sp_draw, sp_away, captured_at
FROM jc_odds_snapshots
ORDER BY match_id, pool_code, goal_line, captured_at DESC;
```

### 3.6 `jc_source_links`：竞彩 ↔ 外部 fixture 映射

```sql
CREATE TABLE jc_source_links (
  id                    BIGSERIAL PRIMARY KEY,
  match_id              VARCHAR(32) NOT NULL REFERENCES jc_matches(match_id),
  source                VARCHAR(16) NOT NULL,       -- sportmonks / api_football / the_odds_api
  external_fixture_id   VARCHAR(64) NOT NULL,
  external_league_id    VARCHAR(64) NULL,
  external_home_team_id VARCHAR(64) NULL,
  external_away_team_id VARCHAR(64) NULL,
  confidence            NUMERIC(3,2) NOT NULL DEFAULT 1.00,
  method                VARCHAR(16) NOT NULL DEFAULT 'exact', -- exact/alias/manual
  verified_at           TIMESTAMPTZ NULL,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source, external_fixture_id),
  UNIQUE (match_id, source),
  CHECK (confidence >= 0 AND confidence <= 1)
);

CREATE INDEX ix_jc_source_links_match ON jc_source_links (match_id);
```

要点：

- 一个竞彩场次在一个源里只能有一个 fixture；一个外部 fixture 也只能挂一个竞彩场次。
- `confidence < 1` 的自动映射必须进人工复核队列；`method='manual'` 才允许覆盖自动结果。
- 不删除旧映射；改映射用新增行 + `verified_at`，保留审计。

### 3.7 `jc_match_features`：派生特征快照

```sql
CREATE TABLE jc_match_features (
  id           BIGSERIAL PRIMARY KEY,
  match_id     VARCHAR(32) NOT NULL REFERENCES jc_matches(match_id),
  cutoff_at    TIMESTAMPTZ NOT NULL,
  feature_ver  VARCHAR(16) NOT NULL,          -- feat-v1
  features     JSONB NOT NULL,
  coverage     JSONB NOT NULL,                -- {"sp":true,"market":true,"lineup":false,...}
  input_hash   CHAR(64) NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (match_id, cutoff_at, feature_ver)
);
```

`coverage` 至少包含：

```json
{
  "sp": true,
  "market": true,
  "lineup": false,
  "injury": false,
  "xg": false,
  "form": true,
  "deep_eligible": false,
  "missing": ["lineup", "injury"]
}
```

### 3.8 `jc_results`：赛果

```sql
CREATE TABLE jc_results (
  match_id     VARCHAR(32) PRIMARY KEY REFERENCES jc_matches(match_id),
  home_goals   SMALLINT NOT NULL,
  away_goals   SMALLINT NOT NULL,
  result       VARCHAR(8) NOT NULL,            -- home/draw/away
  source       VARCHAR(16) NOT NULL,
  settled_at   TIMESTAMPTZ NOT NULL,
  payload_hash CHAR(64) NOT NULL
);
```

现有 `match_results` 按 (home, away, match_date) 唯一，容易撞名/跨赛季；新链路统一用 `match_id`。旧表保留做历史回填。

### 3.9 `jc_league_daily`：联赛场次日聚合

用于选联赛槽位、运营工作台、覆盖率报表；由 `jc_matches` + `jc_source_links` 每日重算。

```sql
CREATE TABLE jc_league_daily (
  trade_date             VARCHAR(10) NOT NULL,
  league_id              INTEGER     NOT NULL REFERENCES jc_leagues(id),
  match_count            INTEGER     NOT NULL DEFAULT 0,
  single_count           INTEGER     NOT NULL DEFAULT 0,
  had_count              INTEGER     NOT NULL DEFAULT 0,
  hhad_count             INTEGER     NOT NULL DEFAULT 0,
  mapped_count           INTEGER     NOT NULL DEFAULT 0,
  market_covered_count   INTEGER     NOT NULL DEFAULT 0,
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (trade_date, league_id)
);
```

## 4. 联赛选槽：按竞彩场次量，不按外部 key

90 天滚动排名：

```sql
SELECT l.name_cn,
       SUM(d.match_count)  AS matches,
       SUM(d.single_count) AS singles,
       COUNT(*)            AS days
FROM jc_league_daily d
JOIN jc_leagues l ON l.id = d.league_id
WHERE d.trade_date >= to_char(
        (now() AT TIME ZONE 'Asia/Shanghai')::date - INTERVAL '90 days',
        'YYYY-MM-DD')
GROUP BY l.name_cn
ORDER BY matches DESC, singles DESC;
```

选槽规则：

1. 先按 `matches` 降序；
2. 同场次按 `singles`（单关场次）降序；
3. 杯赛与联赛分开看：杯赛只在有赛程的窗口占用名额；
4. 每月复核一次，不把 5 个名额锁死整年。

### 4.1 当前 10 天样本（临时结论）

采集库 2026-11-02 ~ 11-12，有效联赛字段 52 场：

| 联赛 | 场次 |
|---|---:|
| 意甲 | 7 |
| 西甲 | 6 |
| 英超 | 6 |
| 德甲 | 6 |
| 荷甲 | 4 |
| 英锦标赛 | 4 |
| 葡超 | 3 |
| 日职 | 3 |
| 韩职 / 澳超 / 法甲 | 各 2 |
| 荷乙 / 英冠 / 瑞超 / 法乙 / 日乙 / 德乙 / 巴甲 | 各 1 |

按这个样本，**只选 5 个：意甲、西甲、英超、德甲、荷甲**。

注意：样本只有 10 天，且 11-02 ~ 11-06 有 51 场旧数据联赛字段为空（旧解析 bug），所以这只是临时名单；正式名单以 `jc_league_daily` 的 90 天滚动结果为准。英锦标赛与荷甲同为 4 场，若当期有英锦标赛赛程，可临时把第 5 个名额换给英锦标赛。

## 5. 写入流程

```text
采集器抓竞彩
  → jc_fetch_raw（原始 JSON，幂等）
  → upsert jc_matches（match_id 主键）
  → append jc_odds_snapshots（唯一键去重）
  → 队名/联赛归一化（jc_teams / jc_leagues / team_aliases）
  → jc_source_links（Sportmonks / API-Football / Odds API）
  → 外部增强快照（阵容/伤停/xG/积分/国际盘）
  → jc_match_features（带 cutoff 和 coverage）
  → ai_analyses / verdicts / decision_snapshots
```

每一步都必须能单独重跑；任何一步失败不能回滚已采集的竞彩原始数据。

## 6. 迁移路径（不一次性重写）

1. **加列**：`sp_matches` 增加 `trade_date`、`league_id`、`home_team_id`、`away_team_id`、`kickoff_utc`、`sell_status`、`first_seen_at/last_seen_at`。
2. **建字典**：`jc_leagues`、`jc_teams`、`team_aliases.team_id`，从现有联赛名/队名回填。
3. **建新表**：`jc_fetch_raw`、`jc_odds_snapshots`、`jc_source_links`、`jc_match_features`、`jc_results`、`jc_league_daily`。
4. **双写**：采集器/入库服务同时写 `sp_*` 与 `jc_*`；读路径先读旧表。
5. **切读**：校验 7 天无差异后，读路径切到 `jc_*`；`sp_matches` 变成兼容视图。
6. **停旧写**：保留一个版本周期后停写 `sp_*`，最后删除旧表/视图。

## 7. 明确不做

- 不用 Sportmonks/API-Football 的 fixture 反向创建竞彩场次。
- 不用中文队名做跨源主键；中文名只做展示和别名。
- 不在 `jc_odds_snapshots` 上 UPDATE 赔率；只追加。
- 不把 `trade_date` 当日历日；不把 `kickoff` 当 UTC。
- 不在映射置信度不足时自动发布推荐；`confidence < 0.9` 必须人工确认。
