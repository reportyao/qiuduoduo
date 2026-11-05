"""概率区间：残差分位 + 样本不足时不伪造。"""
from app.modules.calibration import MIN_SAMPLES, _interval_from_values


def test_interval_accumulating_below_min_samples():
    low, high = _interval_from_values(0.55, [0.01] * (MIN_SAMPLES - 1))
    assert low is None and high is None


def test_interval_from_residual_quantiles():
    # 20 个残差：大部分在 -0.1..+0.1，少数极端值
    values = [-0.2, -0.15] + [-0.05] * 8 + [0.05] * 7 + [0.1, 0.2, 0.3]
    low, high = _interval_from_values(0.55, values)
    assert low is not None and high is not None
    assert 0.0 <= low < 0.55 < high <= 1.0
    assert low == 0.40  # 0.55 + q10(-0.15)
    assert high == 0.65  # 0.55 + q90(0.10)
