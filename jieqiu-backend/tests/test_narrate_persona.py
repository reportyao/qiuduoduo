"""narrate 人设模板的最小回归：meng 不得再出现旧称呼/表情。"""
from types import SimpleNamespace

from app.models import PersonaCopySlot
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


def test_admin_slot_overrides_narration(db):
    db.merge(PersonaCopySlot(
        persona_id="laopao", slot_key="narration_promoted",
        template="自定义 {home} vs {away}，{pick}", version=1, enabled=True))
    db.commit()
    text, _ = build_narration(_verdict(), "laopao", db=db)
    assert text.startswith("自定义 曼城 vs 布莱顿")


def test_bad_slot_template_falls_back_instead_of_raising(db):
    db.merge(PersonaCopySlot(
        persona_id="laopao", slot_key="narration_promoted",
        template="{unknown_placeholder}", version=1, enabled=True))
    db.commit()
    text, _ = build_narration(_verdict(), "laopao", db=db)
    assert "曼城" in text and "布莱顿" in text


def test_slot_supports_address_placeholder(db):
    db.merge(PersonaCopySlot(
        persona_id="laopao", slot_key="narration_promoted",
        template="{address}，{home} vs {away}，{pick}", version=1, enabled=True))
    db.commit()
    text, _ = build_narration(_verdict(), "laopao", db=db)
    assert text.startswith("兄弟，曼城 vs 布莱顿")
