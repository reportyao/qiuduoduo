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

## 本机启动架构（2026-11-10 加固版）

```text
计划任务 JieqiuSPCollector（登录时 +15s 触发，365 天时限，失败每分钟重试）
  └─ cmd /c run_collector.bat   设置 PASSWORD/TOKEN/API 环境变量
       └─ pythonw.exe run_forever.py   无窗口 watchdog
            ├─ collector.lock 防双开（锁内写 PID，ctypes 探活，残留锁接管）
            ├─ SIGINT 忽略：控制台 ^C 只杀子进程，5 秒后自动拉起
            ├─ 进程内写 collector.log（pythonw 下 cmd 重定向不可靠，勿依赖 >>）
            └─ collector.py  采集 → 快照 → 心跳 → 每 30 分钟 SFTP 推送
```

要点：

- `pythonw`（无窗口）：没有控制台就没有 ^C；之前 2026-11-09 22:13 的 `^C` 把
  watchdog 和 collector 一起杀掉，且任务只在下次登录触发，同一次登录内不会自拉。
- **服务端"一键重启"只在采集器进程存活时有效**：`POST /admin/api/collector/restart`
  只是写 `restart_requested_at` 标记，等下次心跳返回 `restart=true` 后进程退出、
  watchdog 拉起。进程死了服务器够不到本机，只能挂起等待；接口现在会返回 notice，
  前端在离线时提示"需在本机恢复采集器"。
- 注册/重注册任务（管理员权限）：`powershell -NoProfile -ExecutionPolicy Bypass
  -File register_task.ps1`（会弹 UAC；注册到根文件夹，当前用户 InteractiveToken）。

### 改动与回滚（2026-11-10）

| 文件 | 改动 | 回滚 |
|---|---|---|
| `run_forever.py` | +SIGINT 忽略、+防双开锁、+进程内日志 | `run_forever.py.bak-20261110` |
| `run_collector.bat` | python.exe→pythonw.exe，去掉 `>>` 重定向 | `run_collector.bat.bak-20261110` |
| `register_task.ps1` | 新增（COM 注册计划任务） | 删除任务：`schtasks /delete /tn JieqiuSPCollector /f` |

回滚后需重启进程（`taskkill /F /IM pythonw.exe` 再手动跑 bat）。
