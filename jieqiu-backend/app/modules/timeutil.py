"""竞彩销售日时间口径：00:00–04:59 属于前一日，窗口为 [D 05:00, D+1 04:59]。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..config import get_settings

CN = timezone(timedelta(hours=get_settings().tz_offset_hours))


def trade_date_from_kickoff(value: str | datetime) -> str:
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            return ""
    if dt.hour < 5:
        dt -= timedelta(days=1)
    return dt.strftime("%Y-%m-%d")


def trade_date_now(now: datetime | None = None) -> str:
    return trade_date_from_kickoff(now or datetime.now(CN))


def trade_window(date: str) -> tuple[str, str]:
    """返回 (当日 05:00:00, 次日 04:59:59) 的 CN naive 字符串。"""
    d = datetime.strptime(date, "%Y-%m-%d")
    return (f"{date} 05:00:00",
            f"{(d + timedelta(days=1)).strftime('%Y-%m-%d')} 04:59:59")
