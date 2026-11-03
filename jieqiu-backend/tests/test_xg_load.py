"""W3 补充：understat dump 加载 / 多文件合并 / 列名自适应。"""
import pandas as pd

from app.modules.dc_model import fit, load_xg, predict


def test_load_xg_merges_main_and_dump_with_col_mapping(tmp_path):
    # 主 csv：W1 schema
    main = tmp_path / "xg_matches.csv"
    pd.DataFrame([
        dict(understat_id=1, datetime="2026-09-01 20:00:00", team_home="A队",
             team_away="B队", xg_home=2.0, xg_away=1.0),
        dict(understat_id=2, datetime="2026-09-08 20:00:00", team_home="B队",
             team_away="A队", xg_home=1.1, xg_away=1.9),
    ]).to_csv(main, index=False)
    # dump：understat 原始风格列名（datetime + h_team/a_team/hxg/axg）+ 与主 csv 重叠行
    d = tmp_path / "dumps"
    d.mkdir()
    pd.DataFrame([
        dict(datetime="2026-09-15 20:00:00", h_team="A队", a_team="B队", hxg=2.2, axg=0.8),
        dict(datetime="2026-09-01 20:00:00", h_team="A队", a_team="B队", hxg=2.0, axg=1.0),  # 重叠 → 去重
    ]).to_csv(d / "understat_EPL_2026_2027.csv", index=False)

    df = load_xg(str(main), str(d))
    assert len(df) == 3  # 2 主 + 1 新 dump（重叠去重）
    m = fit(df, as_of=pd.Timestamp("2026-11-03 12:00:00").to_pydatetime())
    p = predict(m, "A队", "B队")
    assert p is not None and abs(p.p_home + p.p_draw + p.p_away - 1) < 1e-6


def test_load_xg_skips_unmappable_files(tmp_path):
    main = tmp_path / "xg.csv"
    pd.DataFrame([dict(datetime="2026-09-01", team_home="A", team_away="B",
                       xg_home=1.5, xg_away=1.2)]).to_csv(main, index=False)
    junk = tmp_path / "dumps"
    junk.mkdir()
    pd.DataFrame([dict(foo="bar")]).to_csv(junk / "junk.csv", index=False)
    df = load_xg(str(main), str(junk))
    assert len(df) == 1  # junk 被跳过，主文件可用


def test_load_xg_raises_when_nothing_usable(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        load_xg(str(tmp_path / "none.csv"), "")
