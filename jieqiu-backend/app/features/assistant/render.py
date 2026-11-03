"""通知文案：站内信可以详细，系统推送保持中性（PRD F19）。"""
from __future__ import annotations

from ...models import Event

STATUS_LABEL = {"promoted": "三关全过", "killed": "未过闸", "screening": "复核中"}


def _deeplink(event: Event, payload: dict) -> str:
    if payload.get("verdict_id"):
        return f"jieqiu://verdict/{payload['verdict_id']}"
    if event.match_id:
        return f"jieqiu://match/{event.match_id}"
    return "jieqiu://today"


def render_notification(event: Event, channel: str = "inapp") -> dict:
    """返回 {title, body, deeplink}。推送不写队名/赔率/投注词。"""
    p = event.payload or {}
    home, away = p.get("home", ""), p.get("away", "")
    match = f"{home} vs {away}" if home and away else ""
    deeplink = _deeplink(event, p)
    t = event.type

    if t in ("verdict_promoted", "verdict_change", "verdict_killed"):
        status = STATUS_LABEL.get(p.get("status", ""), "有更新")
        if channel == "push":
            return {"title": "解球 · 比赛更新",
                    "body": "你关注的比赛结论有更新，点开看详情。",
                    "deeplink": deeplink}
        pick = p.get("pick") or {}
        extra = ""
        if pick.get("dir"):
            extra = f" 方向：{pick['dir']}"
            if pick.get("prob") is not None:
                extra += f"，置信 {round(float(pick['prob']) * 100, 1)}%"
        if status == "未过闸":
            body = f"{match} 没过三关，先别碰。"
        else:
            body = f"{match}：{status}。{extra}".strip()
        return {"title": "比赛结论更新", "body": body or f"{match} 有更新。", "deeplink": deeplink}

    if t == "close_soon":
        mins = p.get("minutes")
        if channel == "push":
            return {"title": "解球 · 停售提醒",
                    "body": "你关注的比赛即将停售，点开看最后结论。",
                    "deeplink": deeplink}
        return {"title": "停售提醒",
                "body": f"{match} 将在 {mins} 分钟后停售。" if mins is not None else f"{match} 即将停售。",
                "deeplink": deeplink}

    if t == "final":
        score = p.get("score", "")
        if channel == "push":
            return {"title": "解球 · 终场",
                    "body": "你关注的比赛已终场，点开看结果。",
                    "deeplink": deeplink}
        return {"title": "终场", "body": f"{match} 终场 {score}".strip(),
                "deeplink": deeplink}

    if t == "settled":
        result = p.get("result", "")
        if channel == "push":
            return {"title": "解球 · 结算",
                    "body": "你记录的比赛已结算，点开看归因。",
                    "deeplink": deeplink}
        return {"title": "结算与归因", "body": f"{match} 已结算：{result}".strip(),
                "deeplink": deeplink}

    if t == "daily_brief":
        total, promoted = p.get("total", 0), p.get("promoted", 0)
        if channel == "push":
            return {"title": "解球 · 今日简报",
                    "body": "今天的比赛结论已更新，点开看今日简报。",
                    "deeplink": "jieqiu://today"}
        return {"title": "今日简报",
                "body": f"今天 {total} 场，过三关 {promoted} 场。点开看今天值得看的场次。",
                "deeplink": "jieqiu://today"}

    return {"title": "解球", "body": "有一条新消息，点开看详情。", "deeplink": deeplink}
