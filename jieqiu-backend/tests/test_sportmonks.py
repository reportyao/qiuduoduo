"""Sportmonks 同步纯函数测试：映射与去水。"""
from types import SimpleNamespace

from app.modules.sportmonks import _devig, match_fixture


def _match(home: str, away: str, kickoff: str = "2026-11-11 20:00:00"):
    return SimpleNamespace(home=home, away=away, kickoff=kickoff, league="英超")


def _fixture(fid: int, home: str, away: str, starting_at: str):
    return {
        "id": fid,
        "starting_at": starting_at,
        "participants": [
            {"name": home, "meta": {"location": "home"}},
            {"name": away, "meta": {"location": "away"}},
        ],
    }


def test_match_fixture_exact_names_and_kickoff():
    fixture = _fixture(1, "曼城", "布莱顿", "2026-11-11 12:00:00")
    assert match_fixture(_match("曼城", "布莱顿"), [fixture]) is fixture


def test_match_fixture_rejects_far_kickoff():
    fixture = _fixture(1, "曼城", "布莱顿", "2026-11-11 18:00:00")
    assert match_fixture(_match("曼城", "布莱顿"), [fixture]) is None


def test_match_fixture_requires_close_enough_names():
    fixture = _fixture(1, "曼城", "布莱顿", "2026-11-11 12:00:00")
    assert match_fixture(_match("利物浦", "埃弗顿"), [fixture]) is None


def test_devig_sums_to_one():
    probs = _devig([2.0, 3.5, 4.0])
    assert probs is not None
    assert abs(sum(probs.values()) - 1.0) < 1e-9
    assert probs["home"] > probs["away"]


def test_devig_bad_values():
    assert _devig([0, 3, 4]) is None


def test_match_fixture_chinese_abbreviations():
    fixture = _fixture(2, "谢菲尔德星期三", "阿克灵顿斯坦利", "2026-11-11 19:00:00")
    assert match_fixture(_match("谢周三", "阿克宁顿", "2026-11-12 03:00:00"), [fixture]) is fixture


def test_match_fixture_never_guesses_weak_second_team():
    fixture = _fixture(3, "曼城", "布伦特福德", "2026-11-11 12:00:00")
    assert match_fixture(_match("曼城", "布莱顿"), [fixture]) is None
