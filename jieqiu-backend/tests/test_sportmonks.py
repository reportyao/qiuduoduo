"""Sportmonks 同步纯函数测试：映射与去水。"""
from types import SimpleNamespace

from app.modules.intel_research import _extract_json
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


def test_extract_json_tolerates_markdown_and_prefix():
    text = '说明' + chr(10) + '```json' + chr(10) + '{"headline":"x","points":["y"]}' + chr(10) + '```'
    assert _extract_json(text)["headline"] == "x"
    assert _extract_json('prefix {"a":1} suffix')["a"] == 1


def test_get_retries_429_then_succeeds(monkeypatch):
    import urllib.error
    from app.modules import sportmonks

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"data": [1]}'

    calls = {"n": 0}

    def fake_urlopen(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(
                "https://example.invalid", 429, "Too Many",
                {"Retry-After": "0"}, None)
        return _Response()

    sleeps = []
    monkeypatch.setattr(sportmonks.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(sportmonks.time, "sleep", lambda s: sleeps.append(s))
    assert sportmonks._get("https://example.invalid", "/fixtures", "api_token=x") == {"data": [1]}
    assert calls["n"] == 2
    assert sleeps == [1.0]


def test_get_does_not_retry_auth_error(monkeypatch):
    import urllib.error
    from app.modules import sportmonks

    calls = {"n": 0}

    def fake_urlopen(*args, **kwargs):
        calls["n"] += 1
        raise urllib.error.HTTPError(
            "https://example.invalid", 401, "Unauthorized", {}, None)

    monkeypatch.setattr(sportmonks.urllib.request, "urlopen", fake_urlopen)
    assert sportmonks._get("https://example.invalid", "/fixtures", "api_token=x") is None
    assert calls["n"] == 1
