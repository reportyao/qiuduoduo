# Assistant feature slice

AI 助理运行时：事件监控 → 扇出 → 站内信/推送 → 用户行为。

## 文件

- `events.py`：事件写入，`dedupe_key` 幂等。
- `monitors.py`：结论变化、停售、终场、结算、每日简报。
- `fanout.py`：关注/下注关系扇出，静默时段、每日上限。
- `providers.py`：`PushProvider` 协议与 JPush 实现。
- `render.py`：站内信/推送文案（推送保持中性）。
- `router.py`：`/me/inbox`、`/me/watch`、`/me/notify-settings`、`/push/*`。
- `worker.py`：`python -m app.features.assistant.worker --once`。

## 不变量

1. 同一事件对同一用户/渠道只产生一条通知。
2. 推送失败不会阻塞判决发布。
3. 静默时段不发送 close/daily 类推送；站内信仍可见。
4. 推送文案中性，不出现赔率/投注/赛事结果字样。
5. 用户删除账号时，助理数据必须被清除。

## 已知待办

- 未决 T-30m、T-3h 动态触发。
- 盘口异动、阵容/伤停监控。
- `user_events` 记忆推导。
- `/admin` AI / memory 页（旧 /console 已下线）。
