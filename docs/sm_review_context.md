# 评审上下文：球多多项目事实（供独立评审参照，与方案分开给）

## 产品
- 中国竞彩足球**赛前**预测 App（Expo RN 移动端 + FastAPI 后端 + 管理后台）。只做赛前，无滚球功能。
- 发布链：采集 → 入库对齐 → 模型 → 三闸（价/市/模）→ 封存（哈希链）→ 复核（L1 规则/L2 数字/L3 人设/L4 对抗/L5 发布门）→ published → 推送。
- 合规约束：文案只允许"预测方向/预测概率/置信度"，禁止"必中/稳赚/推荐"；推送中性；第三方内容必须标注来源。
- 单人运营，预算约 €114/月。生产目前 SQLite（Postgres 迁移规划中），采集器跑在用户家宽 Windows 机（服务器 IP 被竞彩官网 WAF 567 拦截，只能家宽采）。

## 当前预测技术栈（重构对象）
- **模型闸**：Dixon-Coles。训练数据 = Understat xG（抓取，仅五大联赛，10,707 场 2019-2025）。指数衰减半衰期 180d、窗口 540d、Poisson 网格 0..10 + DC tau（rho=-0.06）、min_matches=3。**只对五大联赛球队出概率**；日职/英锦标赛等全部无模型输出（model pending）。
- **价闸**：竞彩 SP（胜平负/让球）去水算抽水，阈值门槛。
- **市闸**：竞彩去水 ⊕ 国际盘（The Odds API 免费 500 credit/月，按当日联赛选 sport key，±4h 窗口对齐），逐结果最大离散 < 5pp。EFL Trophy 等无 key（404）。
- **情报层**：API-Football 免费档（100 次/天）拿 lineups/injuries/standings——经常拿不到。
- **结算**：football-data 免费源 + Understat 结果代理。
- 现有表：sp_matches/sp_snapshots/intl_odds/team_aliases/verdicts/verdict_revisions/match_results/model_runs/model_evals/api_football_fixtures/match_lineups/match_injuries/team_standings/intel_items/match_coverage/decision_snapshots/recommendation_plans/review_runs/llm_* 等。
- LLM 网关已有：fast/deep 双 profile（TokenRhythm 中转，deepseek-v4.1-flash / qwen3.8-flash），带缓存/预算/用量表。

## 近两月竞彩场次分布（真实统计，2026-09-09~11-09，860 场/38 赛事）
意甲80 西甲78 德甲63 英超63 欧冠59 欧国联52 欧联43 法甲34 荷甲31 日职29 巴甲28 葡超24 亚冠23 韩K1 21 英冠21 瑞超21 挪超18 亚运男足15 友谊赛14 美职13 日乙13 芬超13 澳超12 解放者杯11 荷乙11 英联杯9 德乙7 法乙7 英锦标赛7 日联杯6 欧协联5 沙特联4 亚冠联2 4 德国杯4 巴西杯2 荷杯1。墨超/智利/哥伦比亚/西乙/意乙=0。

## Sportmonks 事实（已核实，评审时可依赖）
- Growth €99/月 任选 30 联赛、2,500 次/实体/小时、per_page 最大 50；年付 -20%。
- Predictions 加购：Basic €23/月（Growth 档），Advanced €63/月（=Basic+滚球 1X2 每分钟）。Odds & Predictions 捆绑 €15/月（档位未明示，需问客服）。
- 预测类型 36 种：237=1X2、240=比分矩阵(含 Other_1/2/X 兜底)、231=BTTS、234/235/335/1679=大小球、239=双 chance、232=HT/FT、33=Valuebet、241-245=模型性能指标、37072=PREDICTION_STATUS(values.predictable)。赛前 21 天可用、逐日刷新。不是每场都出（predictable 标志过滤）。
- predictability（type 243）是**定性**评级 high/medium/poor/unchanged，按联赛×市场。
- 赔率：Odds add-on €14-69（随套餐）；标准 feed 含 pre-match+inplay，50+ 庄家 150+ 市场，历史回溯 ~2018；Premium feed 另收费（更快+时间戳，历史仅 7 天）。
- xG 是独立加购：Basic 赛后 €19-99/月，Advanced 实时 €199-399/月。按 team/player 出 xG 值。
- lineups 是 fixture include（有 confirmed lineups；"Premium Expected Lineups"是独立高级加购；教程里有 predicted lineups include，未确认是否含在基础档）。
- sidelined = 伤停/停赛（fixture include 或 sidelined 教程页）。
- 结算赛果：fixtures 端点含 state/scores；历史数据默认每联赛只给最近 3 个赛季，更早需 historical data 加购（Enterprise 部分豁免）。
- locale=zh 为 Beta 翻译（12 类实体 name 字段，低级别覆盖不全），数值不翻译。
- 配额按"实体/小时"；无公开 coupon；免费档丹麦超+苏超可先验证字段结构。
- DC 模型自验基线：2023-24 英超 backtest log loss 0.9191（tests 断言 <0.95）。行业 1X2 现实准确率 50-55%；收盘赔率去水是最强概率基准。
