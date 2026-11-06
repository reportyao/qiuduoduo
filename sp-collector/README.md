# 竞彩 SP 采集器

每 5 分钟抓一次体彩官方在售场次与 SP，写 `sp_data.db`，每 30 分钟 SFTP 推送到
`/home/ubuntu/jieqiu-sp/sp_data.db`。后端 `app.seed` 再导入 `SPMatch`/`SPSnapshot`。

## 出口是硬约束

体彩 `webapi.sporttery.cn` 会按出口 IP 拦截机房网络：2026-11-06 从生产服务器
`43.128.24.244` 直连返回 **HTTP 567**（WAF 页面），因此**采集器不能直接跑在腾讯云
服务器上**。必须满足其一：

1. **家宽/住宅出口（当前方式）**：采集器跑在家宽机器上，服务器只接收 SFTP 推送。
2. **服务器 + 住宅代理**：服务器上运行，`JQ_COLLECTOR_PROXY` 指向住宅代理；
   代理出口仍必须是住宅 IP，否则同样 567。

## 家宽模式：做成常驻服务

不要把采集器放在一个会关掉的终端里。Linux 用 systemd：

```ini
# /etc/systemd/system/jieqiu-collector.service
[Unit]
Description=Jieqiu SP collector
After=network-online.target

[Service]
WorkingDirectory=/home/you/sp-collector
Environment=JQ_COLLECTOR_HOST=43.128.24.244
Environment=JQ_COLLECTOR_USER=ubuntu
EnvironmentFile=/etc/jieqiu-collector.env   # JQ_COLLECTOR_PASSWORD
ExecStart=/usr/bin/python3 collector.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Windows 用「任务计划程序」创建“计算机启动时”任务，程序 `python.exe`，参数
`collector.py`，起始目录 `sp-collector`，勾选“失败后重新启动”。

服务器侧用 `sp_data.db` 的 mtime 做心跳；超过 15 分钟未更新即视为采集器掉线：

```bash
# crontab -e（服务器）
*/5 * * * * test $(( $(date +%s) - $(stat -c %Y /home/ubuntu/jieqiu-sp/sp_data.db) )) -lt 900 || logger -t jieqiu-sp "collector stale"
```

后续可把这条告警接到站内信/推送；当前至少留下 journal。

## 服务器 + 住宅代理模式

```bash
export JQ_COLLECTOR_PROXY='http://user:pass@residential-proxy:port'
python3 collector.py
```

`collector.py` 的 `fetch()` 会走该代理；不设置则直连。没有住宅代理时不要在服务器
启用这个服务，否则会连续 567、20 次后退出。

## 与 Odds API 的配合

后端 `sync_the_odds_api` 现在：

1. 只按**当日竞彩联赛**选 sport key（`sports_for_trade_date`）；
2. 先调免费的 `/sports/{sport}/events`；
3. 只把与 `SPMatch` 队名 + 开赛时间（±4h）匹配的 `eventIds` 传给 `/odds`；
4. 没有匹配赛事就不请求 `/odds`，不花 credit；
5. 默认 `regions=eu`（Pinnacle 在 eu），1 市场 = 1 credit/sport。

采集器的 `matches.league` 必须在 `subMatchList` 里取 `leagueAbbName`（旧代码读顶层
block，导致联赛全空），否则第 1 步会选不到 sport key。
