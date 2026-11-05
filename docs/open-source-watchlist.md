# 开源引用/候选清单（定期复核）

> 最近复核：2026-11-05。口径：GitHub 元数据（push/license/issues/fork）、PyPI 最新版本、release feed、
> 本地克隆实测。**"引用"不等于"依赖"**：只有进入 `requirements.txt` / 运行链路 / 测试 oracle 的才算依赖。

## 结论速览

| 状态 | 项目 |
|---|---|
| 已在用 | penaltyblog（Understat 抓取；已锁 `>=1.13,<2`） |
| 采纳为 oracle/参考 | Johnserf-Seed/SportteryAPI（竞彩赔率数学，17/17 测试通过） |
| 方法论参考 | JetQiao/football-prediction-skill（walk-forward/晋级协议） |
| 输出模板改编 | sahuan14/worldcup-betting-analyst-skill（比赛原型/角色分层/风险语言；停售规则不采用） |
| 借思路不装包 | magicjordan33/sports-betting-claude（anti-bias/CLV） |
| 观察名单 | infersports、ddevetak/footballcharts-mcp、mcp-sports-hub、sportsdata-mcp |
| 研究/离线 | probberechts/soccerdata、ML-KULeuven/socceraction |
| 开发工具 | ruff/mypy/pre-commit/schemathesis/pytest-recording/testcontainers/RNTL/Maestro/Playwright/agent-device/Sentry/Uptime Kuma/Healthchecks |
| 不采用 | strumideld-bit 作为依赖、ccdejene/fotmob-mcp、amosbastian/understat、Portkey、GPTCache、旧 awesome 列表 |

## 明细

### 在用 / 已验证

| 项目 | 最新证据 | 用途 | 结论 |
|---|---|---|---|
| [penaltyblog](https://github.com/martineastwood/penaltyblog) | PyPI 1.13.1（2026-10-05），push 2026-10-19，MIT | `Understat` xG 抓取 | 保留；`requirements.txt` 已锁 `>=1.13,<2`。注意：Understat 站点当前对本机网络返回错误页/超时，属源不可达而非库失效 |
| [Johnserf-Seed/SportteryAPI](https://github.com/Johnserf-Seed/SportteryAPI) | push 2026-11-04，MIT，17 commits，本地 `derive/parlay` 测试 17/17 通过 | 竞彩赔率数学：去水/返还率/凯利/单关过关/500万封顶 | **采纳为 oracle**；纯 TS 无 I/O、带单测，可作为我们 parlay/去水口径的第二实现对拍 |

### 方法论参考（不进运行链）

| 项目 | 最新证据 | 结论 |
|---|---|---|
| [JetQiao/football-prediction-skill](https://github.com/JetQiao/football-prediction-skill) | 31★，12 commits，v0.6.1（2026-07-27），MIT | 借 walk-forward、champion/challenger、预测时点隔离；不把预测话术搬进产品 |
| [magicjordan33/sports-betting-claude](https://github.com/magicjordan33/sports-betting-claude) | 11★，1 commit，无 release | anti-bias/CLV 内容质量高；只借思路，不装包 |
| [sahuan14/worldcup-betting-analyst-skill](https://github.com/sahuan14/worldcup-betting-analyst-skill) | 14★，v1.1.0（2026-06-19），MIT | **输出模板改编**：比赛原型、主推/可选/博取/跳过角色分层、购票小抄、风险语言；改为“优先/关注/高波动/观望”并强制审核后发布。停售时间规则（22/23:00）不采用，继续以官方 `sale_close = kickoff` 为准 |

### 观察名单（可研究，不做生产依赖）

| 项目 | 最新证据 | 结论 |
|---|---|---|
| [infersports/infersports-skill](https://github.com/infersports/infersports-skill) | 32★，16 commits，push 2026-06-11；`api.infersports.dev/docs|openapi.json` 200 | keyless 亚洲盘/去水对照；API 存活但 skill 近 5 个月未更，只做研究对照 |
| [ddevetak/footballcharts-mcp](https://github.com/ddevetak/footballcharts-mcp) | 6★，36 commits，v0.5.0（2026-09-06），push 2026-10-27，MIT | 98 联赛表格/赛果，可作离线研究源 |
| [lacausecrypto/mcp-sports-hub](https://github.com/lacausecrypto/mcp-sports-hub) | 40★，v1.4.1（2026-10-14），MIT | 42 家/410 tools，太重；当目录用 |
| [DanielTomaro13/sportsdata-mcp](https://github.com/DanielTomaro13/sportsdata-mcp) | 32★，v0.33.0（2026-09-28），MIT | 跨庄价差思路好，但深度在澳区，不对口 |

### 研究 / 离线数据

| 项目 | 最新证据 | 结论 |
|---|---|---|
| [probberechts/soccerdata](https://github.com/probberechts/soccerdata) | 2132★，PyPI 2026.43.0（2026-10-19），Apache-2.0 | FBref/Understat/Sofascore 爬虫集合；只做离线研究，遵守 ToS |
| [ML-KULeuven/socceraction](https://github.com/ML-KULeuven/socceraction) | 823★，push 2026-10-18，MIT | 需要 event 数据；暂不引入 |
| [eddwebster/football_analytics](https://github.com/eddwebster/football_analytics) | 2833★，push 2025-10-09 | 阅读索引 |

### 开发工具（按计划引入，均已活跃）

| 工具 | 最新证据 | 结论 |
|---|---|---|
| [ruff](https://github.com/astral-sh/ruff) / [mypy](https://github.com/python/mypy) / [pre-commit](https://github.com/pre-commit/pre-commit) | 2026-11-02~04 | CI/本地质量门 |
| [schemathesis](https://github.com/schemathesis/schemathesis) | v4.33.1（2026-11-04） | OpenAPI 契约测试 |
| [pytest-recording](https://github.com/kiwicom/pytest-recording) | v0.14.1（2026-11-02） | 录制 API-Football 真响应回放 |
| [respx](https://github.com/lundberg/respx) | v0.23.1（2026-04-08） | httpx mock |
| [testcontainers-python](https://github.com/testcontainers/testcontainers-python) | v4.15.0（2026-07-24） | Postgres 集成测试 |
| [Playwright MCP](https://github.com/microsoft/playwright-mcp) | push 2026-11-03 | `/admin` E2E |
| [agent-device](https://github.com/callstack/agent-device) | push 2026-11-04 | 移动端 UI 验证 |
| [Maestro](https://github.com/mobile-dev-inc/Maestro) | push 2026-11-03 | RN E2E |
| [react-native-testing-library](https://github.com/callstack/react-native-testing-library) | push 2026-10-20 | RN 组件测试 |
| [Sentry](https://github.com/getsentry/sentry) / [Uptime Kuma](https://github.com/louislam/uptime-kuma) / [Healthchecks](https://github.com/healthchecks/healthchecks) | 2026-10-27~31 | 错误/健康监控 |

### 不采用 / 降级

| 项目 | 证据 | 原因 |
|---|---|---|
| [strumideld-bit/Football-Prediction-skill](https://github.com/strumideld-bit/Football-Prediction-skill) | 0★，2 commits，无 release（2026-09-08） | 场地切分/支持度思路可借鉴，但项目太薄；事实层我们自己从 `match_results` 计算 |
| [ccdejene/fotmob-mcp](https://github.com/ccdejene/fotmob-mcp) | 10★，20 commits，**无 LICENSE** | 无许可证不可复用；FotMob 非官方接口 |
| [amosbastian/understat](https://github.com/amosbastian/understat) | PyPI 0.1.14（2025-12-16） | 已有更新的 penaltyblog Understat 抓取，没必要换库 |
| [Portkey-AI/gateway](https://github.com/Portkey-AI/gateway) | push 2026-05-25 | 自研 Gateway Phase 1 已够；不引入第二套网关 |
| [zilliztech/GPTCache](https://github.com/zilliztech/GPTCache) | push 2026-09-22 | 当前精确缓存够用，语义缓存有误命中风险 |
| matiasmascioto/awesome-soccer-analytics | 2020-11-17 | 太旧 |
| FaridSafi/react-native-gifted-chat / react-native-chat-ui | — | 与定制 Muse 对话流冲突/停更 |

## 复核方法

1. GitHub repo 元数据：stars/pushed/license/fork/archived/issues。
2. PyPI / release atom：最新版本与日期。
3. 关键项目本地克隆实测：SportteryAPI `derive/parlay` 测试 17/17 通过（Node 22.20）。
4. 活的外部服务探活：`api.infersports.dev/docs|openapi.json` 返回 200。
5. 结合产品规则：推荐/组合必须经审核后发布；可借用输出结构，但不采用会与官方口径冲突的停售规则，也不承诺收益。
