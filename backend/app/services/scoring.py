"""评分聚合：从单 conversation 的 6 维结果计算 weighted_score；从 run 全量结果汇总。"""
from __future__ import annotations

import random
from typing import Iterable

from app.core.config import DEFAULT_DIMENSION_WEIGHTS

PASS_THRESHOLD = 0.6  # 见准出标准：会话级 ≥0.6 为 GOOD
MIN_CI_SAMPLE = 30  # n<30 时 bootstrap 不返回 CI（统计效力不足）


def bootstrap_ci(
    values: list[float], n_iters: int = 1000, ci: float = 0.95, seed: int = 0
) -> tuple[float | None, float | None]:
    """对样本均值做 bootstrap 重采样，返回 (low, high) 95% CI。

    n<MIN_CI_SAMPLE 时返回 (None, None)——告诉调用方"样本不足，不可信"。
    seed 固定让相同输入产生相同 CI（避免前端 polling 时数值抖动）。
    """
    if len(values) < MIN_CI_SAMPLE:
        return None, None
    rng = random.Random(seed)
    means: list[float] = []
    n = len(values)
    for _ in range(n_iters):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    alpha = (1 - ci) / 2
    low_idx = max(0, int(alpha * n_iters))
    high_idx = min(n_iters - 1, int((1 - alpha) * n_iters))
    return round(means[low_idx], 4), round(means[high_idx], 4)


def conversation_weighted_score(
    dim_scores: dict[str, float | None],
    weights: dict[str, float] | None = None,
) -> tuple[float | None, str | None]:
    """按权重聚合 6 维分数。返回 (weighted_score, lowest_dim_code)。

    None 分数（不适用 / 跳过）参与归一化分母剔除，避免 applicable=false 拉低总分。
    """
    weights = weights or DEFAULT_DIMENSION_WEIGHTS
    total_weight = 0.0
    total_score = 0.0
    lowest_score = None
    lowest_dim = None
    for code, score in dim_scores.items():
        if score is None:
            continue
        w = weights.get(code, 0.0)
        total_weight += w
        total_score += w * score
        if lowest_score is None or score < lowest_score:
            lowest_score = score
            lowest_dim = code
    if total_weight == 0:
        return None, None
    return round(total_score / total_weight, 4), lowest_dim


def aggregate_dimension_summary(
    case_results: Iterable[dict],
    dimensions: list[str],
) -> list[dict]:
    """从 case_results 列表聚合每个维度的均值/通过率/min/max。

    case_results 是 list[{"dim1_score": .., "dim2_score": ..}, ...]
    """
    out = []
    for code in dimensions:
        col = f"{code}_score"
        values = [r[col] for r in case_results if r.get(col) is not None]
        if not values:
            out.append(
                {
                    "dimension_code": code,
                    "avg_score": None,
                    "sample_count": 0,
                    "pass_count": 0,
                    "pass_rate": None,
                    "min_score": None,
                    "max_score": None,
                }
            )
            continue
        passed = [v for v in values if v >= PASS_THRESHOLD]
        ci_low, ci_high = bootstrap_ci(values)
        out.append(
            {
                "dimension_code": code,
                "avg_score": round(sum(values) / len(values), 4),
                "sample_count": len(values),
                "pass_count": len(passed),
                "pass_rate": round(len(passed) / len(values), 4),
                "min_score": min(values),
                "max_score": max(values),
                "mean_ci_low": ci_low,
                "mean_ci_high": ci_high,
            }
        )
    return out


def run_pass_rate(case_weighted_scores: list[float | None]) -> float | None:
    valid = [s for s in case_weighted_scores if s is not None]
    if not valid:
        return None
    return round(sum(1 for s in valid if s >= PASS_THRESHOLD) / len(valid), 4)


def run_overall_score(case_weighted_scores: list[float | None]) -> float | None:
    valid = [s for s in case_weighted_scores if s is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 4)
