"""修订史回归：同一 verdict 随数据更新重建时，历史封存哈希必须全部可回溯。"""
from app.models import SPMatch, SPSnapshot, VerdictRevision
from app.modules.verdict import build_verdicts
from tests.conftest import future_kickoff, today_cn

NOW = "2026-11-03 19:02:00"


def _seed(db, cutoff: str):
    db.merge(SPMatch(match_id="2042701", match_no="周三099", league="英超",
                     home_raw="曼城", away_raw="布莱顿", home="曼城", away="布莱顿",
                     kickoff=future_kickoff(today_cn()), single_flag=True))
    db.merge(SPSnapshot(match_id="2042701", pool="had", goal_line="",
                        sp_h=1.53, sp_d=4.40, sp_a=5.60, captured_at=cutoff))
    db.commit()


def test_revisions_append_and_dedup(db):
    _seed(db, today_cn() + "T10:00:00+08:00")
    build_verdicts(db, today_cn(), NOW)
    assert db.query(VerdictRevision).count() == 1

    # SP 更新（新 cutoff，赔率变化）→ 重建 → 新修订落档
    db.merge(SPSnapshot(match_id="2042701", pool="had", goal_line="",
                        sp_h=1.60, sp_d=4.10, sp_a=5.90,
                        captured_at=today_cn() + "T12:00:00+08:00"))
    db.commit()
    vs = build_verdicts(db, today_cn(), NOW)
    assert len(vs) == 1
    assert db.query(VerdictRevision).count() == 2

    # 再次重建（无新数据）→ 幂等，不重复落档
    build_verdicts(db, today_cn(), NOW)
    assert db.query(VerdictRevision).count() == 2

    # 两个修订哈希必不相同，且第一版原文仍可独立复算
    revs = db.query(VerdictRevision).order_by(VerdictRevision.id).all()
    assert revs[0].payload_hash != revs[1].payload_hash
    import hashlib
    import json
    for r in revs:
        h = hashlib.sha256(json.dumps(r.payload, ensure_ascii=False,
                                      sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        assert h == r.payload_hash


def test_first_revision_hash_preserved_after_updates(db):
    _seed(db, today_cn() + "T10:00:00+08:00")
    build_verdicts(db, today_cn(), NOW)
    first_hash = db.query(VerdictRevision).first().payload_hash

    for i, sp in enumerate((1.55, 1.58, 1.62), start=1):
        db.merge(SPSnapshot(match_id="2042701", pool="had", goal_line="",
                            sp_h=sp, sp_d=4.40, sp_a=5.60,
                            captured_at=f"{today_cn()}T1{i}:00:00+08:00"))
        db.commit()
        build_verdicts(db, today_cn(), NOW)

    # 当前 verdict = 最新版，但第一版哈希在修订史里完好
    assert db.query(VerdictRevision).count() == 4
    assert db.query(VerdictRevision).order_by(VerdictRevision.id).first().payload_hash == first_hash
