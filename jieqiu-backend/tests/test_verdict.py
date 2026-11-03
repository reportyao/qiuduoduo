"""判决模块测试：去水数学、价闸、封存确定性。"""
import hashlib
import json

import pytest

from app.modules.verdict import (
    breakeven_prob,
    canonical_payload,
    implied_probs,
    price_gate,
    seal_payload,
)


def test_implied_probs_known_numbers():
    # 1.53 / 4.40 / 5.60 → 隐含和 = 0.6536+0.2273+0.1786 = 1.0595
    p_h, p_d, p_a, rake = implied_probs(1.53, 4.40, 5.60)
    assert abs(p_h - 0.6167) < 0.001
    assert abs(p_d - 0.2145) < 0.001
    assert abs(p_a - 0.1686) < 0.001
    assert abs(p_h + p_d + p_a - 1.0) < 1e-9
    assert abs(rake - (1 - 1 / (1 / 1.53 + 1 / 4.4 + 1 / 5.6))) < 1e-12


def test_implied_probs_fair_book_zero_rake():
    _, _, _, rake = implied_probs(2.0, 3.0, 6.0)  # 隐含和 = 0.5+0.3333+0.1667 = 1.0
    assert abs(rake) < 1e-9


def test_implied_probs_rejects_bad_input():
    with pytest.raises(ValueError):
        implied_probs(1.0, 3.0, 4.0)
    with pytest.raises(ValueError):
        implied_probs(1.5, 0.9, 4.0)


def test_breakeven():
    assert abs(breakeven_prob(2.05) - (1 / 2.05)) < 1e-12
    with pytest.raises(ValueError):
        breakeven_prob(0.9)


def test_price_gate_threshold():
    assert price_gate(0.092, 0.126).result == "pass"
    assert price_gate(0.134, 0.126).result == "fail"


def test_canonical_payload_is_sorted_and_compact():
    p = {"b": 1, "a": "中文"}
    assert canonical_payload(p) == '{"a":"中文","b":1}'


def test_seal_deterministic_and_verifiable():
    p = {"id": "v2026-11-03-周三012", "rake": 0.092, "home": "曼城"}
    _, h1 = seal_payload(p)
    _, h2 = seal_payload(p)
    assert h1 == h2
    # 独立复算：不依赖 seal_payload 本身
    manual = hashlib.sha256(
        json.dumps(p, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert h1 == manual
    # 改一个字哈希必变
    q = dict(p, rake=0.093)
    _, h3 = seal_payload(q)
    assert h3 != h1
