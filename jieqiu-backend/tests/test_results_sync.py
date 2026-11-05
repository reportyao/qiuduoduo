"""赛果兜底：football-data 进球代理写入 dc_model 可读 CSV。"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd

from app.modules import results_sync as rs


def test_results_proxy_written_and_loadable(tmp_path, monkeypatch):
    extra = tmp_path / "xg_dumps"
    monkeypatch.setattr(rs, "get_settings", lambda: SimpleNamespace(
        xg_data_path=str(tmp_path / "main.csv"), xg_extra_dir=str(extra)))
    monkeypatch.setattr(rs, "_THROTTLE_FILE", str(tmp_path / "throttle"))

    csv = (b"Date,HomeTeam,AwayTeam,FTHG,FTAG\n"
           b"01/11/2026,Man City,Crystal Palace,2,1\n"
           b"02/11/2026,Arsenal,Man United,1,1\n")
    n, note = rs.sync_results_xg(datetime.now(timezone.utc),
                                 fetcher=lambda code, season: csv)
    assert n == 10
    assert "新落档" in note
    assert rs.has_results_proxy(str(extra))

    files = sorted(extra.glob("footballdata_*.csv"))
    assert len(files) == 10
    df = pd.read_csv(files[0])
    assert {"datetime", "team_home", "team_away", "xg_home", "xg_away"} <= set(df.columns)
    assert df.iloc[0]["xg_home"] == 2 and df.iloc[0]["xg_away"] == 1
