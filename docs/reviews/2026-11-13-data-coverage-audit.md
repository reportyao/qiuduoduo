# 2026-11-13 数据覆盖审计

范围：当前竞彩日（2026-11-13 00:00 ~ 2026-11-14 04:59）的 9 场比赛；逐项核对“采集 → 落库 → 接口 → 前端展示”。

## 结论

不是同一个问题：

| 现象 | 判定 | 原因 | 处理 |
|---|---|---|---|
| 周五001 新加坡 vs 巴拉圭 无预测/阵容/积分榜 | **数据源覆盖问题（拉取侧）** | Sportmonks 在 11-10 ~ 11-15 的 fixture 列表中没有这场；球队存在，但没有任何 fixture。`candidate_fixtures` 全为 0 相似度 | 不伪造数据；前端改为“第三方未覆盖”，coverage 从 75 降到 10（insufficient） |
| 大小球全部是 2.5，没有竞彩盘口 | **拉取侧 + 进程未重启** | 家宽采集器进程仍是旧代码，SQLite 没有 `sp_pool_snapshots`；生产 `sp_pool_snapshots=0` | 重启 watchdog 加载新 collector；已产生 66 条 ttg/hafu/crs；生产导入后 open 快照按 TTG 隐含概率得到 2.5/3.5 |
| 黑山 vs 拉脱维亚 缺天气 | **拉取时机问题** | 首次抓取 intel 时 Sportmonks 尚未生成 weatherReport（该场为 `type=actual`）；赛后不再自动刷新 | 手动重拉该场 intel，天气已补为“中雨” |
| 完整预测页只显示 3 个市场 | **处理问题（已修复）** | `_market_board` 只取了 1X2 / 亚盘 / 大小球 3 类，Sportmonks 同一响应还有进球线、半场亚盘、半场大小、半场胜平负、主客队总进球、角球让球/大小 | 扩展到 11 类，全部来自现有 Pinnacle 响应，不增加 API 调用 |
| 大小球/角球盘口只有一条线 | **处理问题（已修复）** | 原逻辑大小球固定 2.5； Sportmonks 实际有多条 total 线 | 按每类市场选择最接近常见主盘口的线，并保留市场原始概率/价格 |
| 完整预测页正确比分只有 3 个 | **前端处理问题** | `SportmonksIntelSection.predictionValue` 对 `scores` 做了 `slice(0,3)` | 改为全部比分按概率排序展示；H5 已实测显示 16 个比分 |
| 周四001/002 没有出现在预测战绩 | **历史边界，不是漏拉** | 两场开球早于快照功能上线；现有 25 维是开球后同步的，不能当作赛前快照 | 按“无赛前快照不补造”原则不补；页面注明仅统计有快照场次 |
| expectedLineups / prematchNews 全为空 | **源数据为空** | Sportmonks 对这批国家联赛返回空数组 | 不展示空模块，不伪造 |
| 伤停 0 / H2H 1~6 场 | **真实数据量** | 部分场次确实没有公开伤停；H2H 历史场次有限 | 正常展示 |
| 11-14 部分比赛未映射 | **尚未到同步窗口** | 当前竞彩日只到 11-14 04:59；07:00 后的比赛属于下一个竞彩日 | 次日 05:35 自动同步，不是丢数据 |

## 当前覆盖

- 当前竞彩日 9 场：8 场有 Sportmonks mapping；8/8 有 25 维预测、完整 intel、AIResearch ready、verdict。
- 周五001：Sportmonks 无 fixture（源覆盖缺口），剩余 8 场完整。
- 预测快照：12 条（4 场已锁定 + 8 场 open）；周四001/002 因开球早于功能上线无快照。
- 大小球：8 场 open 快照已使用 `sporttery_ttg_implied`，其中 2.5/3.5 各 4 场；不再固定 2.5。
- 天气：当前在售/未开赛场次均有；已完赛的黑山场次手动补齐。
- 正确比分：完整预测页展示全部 16~19 个比分桶。
- 市场：完整预测页展示 11 类 Sportmonks/Pinnacle 市场；不再只有 3 类。

## 复现命令

```bash
# 采集器是否加载新代码
python -c "import sqlite3; c=sqlite3.connect('sp-collector/sp_data.db'); print(c.execute('select count(*) from sp_pool_snapshots').fetchone())"

# 生产导入采集库
cd jieqiu-backend && python -m app.seed /home/ubuntu/jieqiu-sp/sp_data.db

# 重新冻结/结算
python -m app.sportmonks_cli sync --date 2026-11-13
python -m app.sportmonks_cli freeze
python -m app.sportmonks_cli settle
```

## 判定口径

- **拉取问题**：源站没有 fixture、订阅不覆盖、采集进程未更新、API 尚未生成该字段。
- **处理问题**：源数据存在但解析/归一化/截断/前端条件导致不展示。
- **历史边界**：功能上线前已开赛，不能补造赛前快照。
