"""对齐模块测试。"""
from app.modules.align import Aligner, normalize, seed_aliases, upsert_aliases


def test_normalize_folds_fullwidth_and_case():
    assert normalize("Ｍａｎ　City！") == "mancity"
    assert normalize("  Bayern  Munich ") == "bayernmunich"


def test_normalize_strips_org_suffixes():
    assert normalize("Manchester City FC") == "manchestercity"
    assert normalize("利物浦FC") == "利物浦"


def test_seed_and_resolve(db):
    assert seed_aliases(db) > 0
    assert seed_aliases(db) == 0  # 幂等
    a = Aligner(db)
    assert a.resolve("曼彻斯特城") == "曼城"
    assert a.resolve("Man City") == "曼城"
    assert a.resolve("BAYERN MUNICH") == "拜仁"
    assert a.resolve("皇家贝蒂斯") == "皇家贝蒂斯"  # 未知 → 归一化原名，不丢


def test_upsert_new_alias(db):
    seed_aliases(db)
    upsert_aliases(db, "皇家贝蒂斯", ["Real Betis", "betis"])
    a = Aligner(db)
    assert a.resolve("Real Betis") == "皇家贝蒂斯"
    assert a.resolve("betis") == "皇家贝蒂斯"
