# 解球后端 · W8（功能冻结）

W8 提审基建：`/review/checklist` 提审检查单（自动聚合）· `/review/banned-words/scan` 即席文案扫描 · `/legal/disclosure` 隐私+SDK+权限契约 · `/app/version` OTA · `/review/freeze` 功能冻结（53 路由基线，新增即违规）。禁用词 21 词表 + 反空格/标点/全角绕过，后端库扫描零命中。

---

# 解球后端 · W7

FastAPI 模块化单体。W2-W4：流/判决三关/封存链/账本/叙述/校准。W6：用户域（保护/归因/记忆/路由）。**W7：F20 分享体系 · F18 双区域 · 数据导出 · 注销清除**。

## W7 交付

| 端点 | 功能 |
|---|---|
| `POST /share/verdict/{id}?persona=` | 判决分享卡（公开） |
| `POST /share/weekly` / `/share/streak` | 周报卡 / 连败卡（需登录） |
| `GET /share/{share_id}` | **编号可验**：content_hash = sha256(payload)，编号 = hash 前 12 位；篡改即暴露；幂等（同内容同编号）；深链 `jieqiu://share/{id}` |
| `GET /shares/mine` | 我的分享列表 |
| `GET /me/market-profile` | **F18** 双区域配置（cn：CNY/热线/18+中文；global：USD/BeGambleAware） |
| `GET /me/export` | 全量数据导出（JSON；设备令牌绝不导出） |
| `python -m app.purge_cli` | 注销期满（7 天）清除：用户+bets/memories/shares；每日 03:00 cron |

登录分流：`POST /auth/device` 带 `region: cn|global`（非法 422）。

## API 全景（33 端点）· 测试 99

## 运行

```bash
pip install -r requirements.txt
python -m app.seed ../sp-collector/sp_data.db   # ingest → intl → understat → 三关 → 赛果 → 结算 → 锚点
python -m app.backtest_cli                      # 校准回测
python -m app.purge_cli                         # 注销期满清除
uvicorn app.main:app --port 8100
```

## 部署

```bash
python deploy.py   # VPS：数据代码分离；三 cron（30min 同步 / 周一回测 / 每日 purge）
```
