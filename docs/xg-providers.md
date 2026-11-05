# xG 数据源选型（2026-11-06）

## 现状

API-Football / API-Sports 提供 fixtures、lineups、injuries、standings，但**不提供 xG**。
当前模型仍使用：

- 静态 `xg_matches.csv`（到 2024-25）
- `football-data.co.uk` 进球代理（`goals_proxy`，不是真 xG）

所以模型闸会长期 `pending_data`，这不是 API-Football key 能解决的。

## 候选

| 平台 | xG 能力 | 覆盖 | 成本/门槛 | 适合 |
|---|---|---|---|---|
| **Sportmonks** | 有 `expected`/xG 端点，含阵容、积分榜、赔率 | 2,200+ 联赛，五大联赛/欧战 | Starter €29/5 联赛；xG & Pressure Index 约 €24/月 add-on；14 天试用 | **首选生产候选** |
| Stats Perform / Opta | 最完整的事件与 xG | 全球主流联赛 | 企业合同，价格高 | 有预算/商业授权时 |
| Sportradar | xG/事件数据 | 全球主流联赛 | 企业合同 | 同上 |
| StatsBomb Open Data | 历史事件数据可算 xG | 部分历史赛事 | 免费 | **回测/模型研究**，不是实时 API |
| FBref | 页面展示 xG（StatsBomb 口径） | 主流联赛历史 | 免费网页，无官方 API；抓取受条款/频率限制 | 历史回测，谨慎抓取 |
| SofaScore（RapidAPI 等封装） | 比赛统计含 xG | 主流联赛 | 有免费/低价档；非官方、条款与稳定性风险 | 低成本试验/补充 |
| Understat | 页面提供 xG | 五大联赛 | 无官方 API；云服务器常被挑战页拦截 | 不建议生产 |
| API-Football / API-Sports | **无 xG** | — | — | 不能替代 xG 源 |

## 推荐

1. **有预算、要稳定生产**：选 **Sportmonks**。xG、lineups、standings、odds 一家就能覆盖；先买 Starter 5 联赛 + xG add-on，确认五大联赛和欧战实际覆盖后再扩。
2. **只做模型回测/校准**：用 **StatsBomb Open Data**，或用 FBref 历史 xG 离线落档；不要让线上请求依赖网页抓取。
3. **先低成本验证**：可以用 SofaScore 封装接口做小样本对照，但必须把它标成实验源，不能作为唯一模型输入。
4. **不要**把 Understat 作为生产源：没有官方 API，云 IP 已被挑战页拦截，稳定性不可控。

## 接入原则

- 先落一张 `xg_snapshots`（match_id、source、xg_home、xg_away、captured_at、data_cutoff、raw_hash），再做模型特征。
- 任何 xG 源都必须带 `source` 和 `captured_at`；缺失时回退到进球代理，并在证据里标明口径。
- 不要把不同供应商的 xG 直接混算；先做同源回测，再决定是否融合。
- 采购前用 5–10 场已知比赛对照官方 xG，确认字段不是“射门数代理”。

> 以上价格来自 Sportmonks 公开页面（2026-11-06），实际以销售报价为准；采购前先确认 xG 端点是否包含在当前套餐/add-on。
