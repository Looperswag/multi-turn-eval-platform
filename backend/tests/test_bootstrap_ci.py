"""M1.1: bootstrap CI 单测。

验证：
- n < 30 时返回 (None, None)
- n ≥ 30 时返回 (low, high)，且区间包含真实均值
- 相同输入 + 固定 seed 产生相同 CI（前端 polling 无抖动）
"""
from __future__ import annotations

import random

from app.services.scoring import MIN_CI_SAMPLE, bootstrap_ci


def test_bootstrap_ci_returns_none_when_sample_too_small():
    low, high = bootstrap_ci([0.5, 0.7, 0.9])
    assert (low, high) == (None, None)


def test_bootstrap_ci_returns_none_at_threshold_minus_one():
    values = [0.6] * (MIN_CI_SAMPLE - 1)
    assert bootstrap_ci(values) == (None, None)


def test_bootstrap_ci_returns_values_at_threshold():
    rng = random.Random(42)
    values = [rng.gauss(0.8, 0.1) for _ in range(MIN_CI_SAMPLE)]
    low, high = bootstrap_ci(values)
    assert low is not None and high is not None
    # CI 必然在 min/max 之间
    assert min(values) <= low <= max(values)
    assert min(values) <= high <= max(values)
    # 区间需包含样本均值（bootstrap 经验性几乎一定满足）
    sample_mean = sum(values) / len(values)
    assert low <= sample_mean <= high


def test_bootstrap_ci_is_deterministic_for_same_input():
    values = [0.5, 0.6, 0.7, 0.8, 0.9] * 10  # 50 values
    a = bootstrap_ci(values, seed=7)
    b = bootstrap_ci(values, seed=7)
    assert a == b


def test_bootstrap_ci_changes_with_different_seed():
    values = [0.5, 0.6, 0.7, 0.8, 0.9] * 10
    a = bootstrap_ci(values, seed=7)
    b = bootstrap_ci(values, seed=8)
    # 不同 seed 至少有一端不同（极小概率撞车，固定 seed 就稳）
    assert a != b
