"""HeaderMetrics 数据源：用户陪伴时长 + 引擎版本 + 今日数据点 + 5/7 监控口径。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..models import EngineConfig, User, utcnow
from .timeutil import CN


def config(db: Session) -> EngineConfig:
    row = db.get(EngineConfig, 1)
    if row is None:
        row = EngineConfig(id=1, version="V3.21", markets_monitored=5,
                           models_reviewing=7, data_points_factor=5.0)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def status(db: Session, user: User | None = None,
           include_points: bool = True) -> dict:
    cfg = config(db)
    now = utcnow()
    uptime = None
    if user is not None and user.created_at is not None:
        seconds = max(0, int((now - user.created_at).total_seconds()))
        uptime = max(1, seconds // 3600)  # 不足 1 小时按 1 小时展示
    points = 0
    running = True
    sm_prediction_types = 0
    sm_lineups = 0
    sm_intel = 0
    if include_points:
        try:
            from ..features.intel import service as intel
            pulse = intel.build_pulse(db)
            raw = int(pulse.get("data_points") or 0)
            points = int(round(raw * float(cfg.data_points_factor or 1)))
            running = pulse.get("stale_seconds") is None or int(pulse.get("stale_seconds") or 0) < 3600
            counts = pulse.get("counts") or {}
            sm_prediction_types = int(counts.get("sportmonks_prediction_types") or 0)
            sm_lineups = int(counts.get("sportmonks_lineups") or 0)
            sm_intel = int(counts.get("sportmonks_intel") or 0)
        except Exception:
            running = False
    return {
        "version": cfg.version,
        "running": bool(running),
        "uptime_hours": uptime,
        "today_data_points": points,
        "markets_monitored": int(cfg.markets_monitored),
        "models_reviewing": int(cfg.models_reviewing),
        "sportmonks_prediction_types": sm_prediction_types,
        "sportmonks_lineups": sm_lineups,
        "sportmonks_intel": sm_intel,
        "as_of": datetime.now(CN).isoformat(timespec="seconds"),
    }
