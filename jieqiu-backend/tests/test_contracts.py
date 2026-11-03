"""契约测试：坏数据必须 fail loud。"""
import pandas as pd
import pandera.errors as perr

from app.contracts import validate_matches, validate_snapshots


def _good_matches():
    return pd.DataFrame([
        {"match_no": "周三012", "match_id": "2042501", "league": "英超",
         "home": "曼城", "away": "布莱顿", "kickoff": "2026-11-04 21:55:00", "single_flag": 1}
    ])


def _good_snaps():
    return pd.DataFrame([
        {"match_id": "2042501", "pool": "had", "goal_line": "",
         "sp_h": 1.53, "sp_d": 4.40, "sp_a": 5.60, "captured_at": "2026-11-03T19:00:00+08:00"}
    ])


def test_valid_frames_pass():
    validate_matches(_good_matches())
    validate_snapshots(_good_snaps())


def test_bad_sp_fails():
    bad = _good_snaps()
    bad.loc[0, "sp_h"] = 0.5  # 赔率不可能 < 1
    try:
        validate_snapshots(bad)
        raise AssertionError("must fail")
    except perr.SchemaErrors:
        pass


def test_bad_pool_fails():
    bad = _good_snaps()
    bad.loc[0, "pool"] = "corner"
    try:
        validate_snapshots(bad)
        raise AssertionError("must fail")
    except perr.SchemaErrors:
        pass


def test_bad_kickoff_format_fails():
    bad = _good_matches()
    bad.loc[0, "kickoff"] = "2026/11/04 21:55"
    try:
        validate_matches(bad)
        raise AssertionError("must fail")
    except perr.SchemaErrors:
        pass
