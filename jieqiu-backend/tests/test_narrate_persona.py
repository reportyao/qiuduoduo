"""narrate 人设模板的最小回归：meng 不得再出现旧称呼/表情。"""
from types import SimpleNamespace

from app.modules.narrate import build_narration


def _verdict(status: str = "promoted") -> SimpleNamespace:
    return SimpleNamespace(
        id="v1",
        home="曼城",
        away="布莱顿",
        status=status,
        rake=0.03,
        rake_threshold=0.05,
        pick={"dir": "主胜"},
        payload={"model": {"shrunk": [0.54, 0.24, 0.22]}},
        gates={"market": {"detail": {"divergence": 0.02}}},
    )


def test_meng_template_has_no_old_address_or_heart():
    for status in ("promoted", "screening", "killed"):
        text, template_id = build_narration(_verdict(status), "meng")
        assert template_id.startswith("meng.")
        assert "主人" not in text
        assert "♡" not in text
        assert "～" in text or "…" in text
