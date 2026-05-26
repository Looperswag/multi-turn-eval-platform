"""对比服务：编排 4 类对比的校验、计算、缓存键生成。

实现自 plan §8.A.5.1 的 10 条修订规范（Spec-1..10）：
- Spec-1：validate_run_compat — 创建时硬校验 comparison.type 与 run 配置的 diff
- Spec-2：dataset_id 必须一致；case 对齐用 conversation_id（FK）
- Spec-3：cache_key 由两 run.finished_at 组成
- Spec-4：Movement 双视图（session-level + dimension-level，PASS_THRESHOLD=0.6）
- Spec-5：Cohen's weighted κ（quadratic weights，0/0.5/1 ordinal，手写，不依赖 sklearn）
- Spec-6：Chi-square p-value 在 sample < 30 时返回 None
- Spec-7：diff_runs 自动推断 suggested_type
- Spec-8：同步即时计算（< 1s for 100 case）
- Spec-10：empty case 容错（不报错，返回 200，movements 为空）
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Iterable

from sqlalchemy.orm import Session

from app.core.config import DEFAULT_DIMENSION_WEIGHTS, DIMENSION_NAMES
from app.models import EvalCaseResult, EvalRun, Conversation
from app.services.scoring import PASS_THRESHOLD

# ====================================================================
# 通用工具
# ====================================================================


def build_cache_key(run_a: EvalRun, run_b: EvalRun) -> str:
    """Spec-3：缓存键由两 run 的 finished_at 组成。

    如果 run 还未跑完（finished_at=None），用 'none' 占位。
    重跑过的 run 会有新的 finished_at，从而失效缓存。
    """
    fa = run_a.finished_at.isoformat() if run_a.finished_at else "none"
    fb = run_b.finished_at.isoformat() if run_b.finished_at else "none"
    return f"{fa}|{fb}"


# ====================================================================
# Spec-1 / Spec-7：配置 diff & 类型推断
# ====================================================================

# 各对比类型「期望差异字段」与「期望相同字段」
_TYPE_SPEC: dict[str, dict[str, list[str]]] = {
    "prompt": {
        "must_differ": ["judge_prompt_version_ids"],
        "must_match": ["dataset_id", "bot_version_id", "judge_model_id"],
    },
    "bot": {
        "must_differ": ["bot_version_id"],
        "must_match": ["dataset_id", "judge_model_id", "judge_prompt_version_ids"],
    },
    "judge": {
        "must_differ": ["judge_model_id"],
        "must_match": ["dataset_id", "bot_version_id", "judge_prompt_version_ids"],
    },
}


def _run_field(run: EvalRun, field: str):
    return getattr(run, field)


def _values_differ(a, b) -> bool:
    """对 dict / list / scalar 做语义比较。"""
    return a != b


def compute_all_diff_points(run_a: EvalRun, run_b: EvalRun) -> list[dict]:
    """枚举两 run 的所有配置差异字段。"""
    fields = ["dataset_id", "bot_version_id", "judge_model_id", "judge_prompt_version_ids"]
    diffs = []
    for f in fields:
        va = _run_field(run_a, f)
        vb = _run_field(run_b, f)
        if _values_differ(va, vb):
            diffs.append({"field": f, "value_a": va, "value_b": vb})
    return diffs


def suggest_type(diff_points: list[dict]) -> str | None:
    """Spec-7：从 diff 字段推断推荐 type。"""
    diff_fields = {d["field"] for d in diff_points}
    # 必须 dataset_id 一致才有意义
    if "dataset_id" in diff_fields:
        return None
    # 仅一个字段不同 → 唯一推断
    if diff_fields == {"judge_prompt_version_ids"}:
        return "prompt"
    if diff_fields == {"bot_version_id"}:
        return "bot"
    if diff_fields == {"judge_model_id"}:
        return "judge"
    return None


def diff_runs(run_a: EvalRun, run_b: EvalRun) -> dict:
    """Spec-7：返回 {diff_points, suggested_type}。"""
    points = compute_all_diff_points(run_a, run_b)
    return {"diff_points": points, "suggested_type": suggest_type(points)}


def validate_run_compat(run_a: EvalRun, run_b: EvalRun, ctype: str) -> list[dict]:
    """Spec-1：返回违规 diff_points 列表。空列表 = 合规。

    Spec-2：硬性要求 dataset_id 相同。
    """
    if ctype not in _TYPE_SPEC:
        # human 类型在 W1.5 不通过此校验链路（A.5.2 走独立端点）
        return [{"field": "type", "value_a": ctype, "value_b": "prompt|bot|judge"}]

    spec = _TYPE_SPEC[ctype]
    issues: list[dict] = []

    # Spec-2：dataset_id 强制一致
    if _values_differ(run_a.dataset_id, run_b.dataset_id):
        issues.append(
            {
                "field": "dataset_id",
                "value_a": run_a.dataset_id,
                "value_b": run_b.dataset_id,
                "reason": "两 run 必须使用同一 dataset",
            }
        )

    # must_differ：必须有差异
    for f in spec["must_differ"]:
        if not _values_differ(_run_field(run_a, f), _run_field(run_b, f)):
            issues.append(
                {
                    "field": f,
                    "value_a": _run_field(run_a, f),
                    "value_b": _run_field(run_b, f),
                    "reason": f"type={ctype} 要求 {f} 不同",
                }
            )

    # must_match：必须相同（dataset_id 已上面查过，这里跳过）
    for f in spec["must_match"]:
        if f == "dataset_id":
            continue
        if _values_differ(_run_field(run_a, f), _run_field(run_b, f)):
            issues.append(
                {
                    "field": f,
                    "value_a": _run_field(run_a, f),
                    "value_b": _run_field(run_b, f),
                    "reason": f"type={ctype} 要求 {f} 相同",
                }
            )

    return issues


# ====================================================================
# Spec-4：Movement 双视图
# ====================================================================


def _is_pass(score: float | None, threshold: float = PASS_THRESHOLD) -> bool:
    return score is not None and score >= threshold


def compute_movements(
    aligned_pairs: list[tuple[EvalCaseResult, EvalCaseResult, str]],
    dim_codes: list[str],
) -> dict:
    """计算 session-level 与 dimension-level 双视图 movement。

    aligned_pairs: list of (case_a, case_b, conversation_id_src)
    """
    session_improved = []
    session_regressed = []
    dimension_movements: dict[str, dict[str, list]] = {
        d: {"improved": [], "regressed": []} for d in dim_codes
    }

    for case_a, case_b, conv_src in aligned_pairs:
        # session-level
        a_pass = _is_pass(case_a.weighted_score)
        b_pass = _is_pass(case_b.weighted_score)
        if not a_pass and b_pass:
            session_improved.append(
                {
                    "conversation_id_src": conv_src,
                    "conversation_id": case_a.conversation_id,
                    "score_a": case_a.weighted_score,
                    "score_b": case_b.weighted_score,
                }
            )
        elif a_pass and not b_pass:
            session_regressed.append(
                {
                    "conversation_id_src": conv_src,
                    "conversation_id": case_a.conversation_id,
                    "score_a": case_a.weighted_score,
                    "score_b": case_b.weighted_score,
                }
            )

        # dimension-level
        for dim in dim_codes:
            sa = getattr(case_a, f"{dim}_score", None)
            sb = getattr(case_b, f"{dim}_score", None)
            a_ok = _is_pass(sa)
            b_ok = _is_pass(sb)
            if not a_ok and b_ok:
                dimension_movements[dim]["improved"].append(
                    {
                        "conversation_id_src": conv_src,
                        "conversation_id": case_a.conversation_id,
                        "score_a": sa,
                        "score_b": sb,
                    }
                )
            elif a_ok and not b_ok:
                dimension_movements[dim]["regressed"].append(
                    {
                        "conversation_id_src": conv_src,
                        "conversation_id": case_a.conversation_id,
                        "score_a": sa,
                        "score_b": sb,
                    }
                )

    return {
        "session_movement": {
            "improved": session_improved,
            "regressed": session_regressed,
        },
        "dimension_movements": dimension_movements,
    }


# ====================================================================
# M1.1：bootstrap CI for two-sample mean difference + Cohen's d 效应量
# ====================================================================


def _bootstrap_delta_ci(
    a_values: list[float],
    b_values: list[float],
    n_iters: int = 1000,
    ci: float = 0.95,
    seed: int = 0,
) -> tuple[float | None, float | None]:
    """对两组样本的均值差做 bootstrap 重采样，返回 (delta_low, delta_high) 95% CI。

    各自任一组 n<30 时返回 (None, None)。配合 scoring.bootstrap_ci 的阈值。
    """
    if len(a_values) < 30 or len(b_values) < 30:
        return None, None
    import random as _r
    rng = _r.Random(seed)
    na, nb = len(a_values), len(b_values)
    deltas: list[float] = []
    for _ in range(n_iters):
        sa = sum(a_values[rng.randrange(na)] for _ in range(na)) / na
        sb = sum(b_values[rng.randrange(nb)] for _ in range(nb)) / nb
        deltas.append(sb - sa)
    deltas.sort()
    alpha = (1 - ci) / 2
    low_idx = max(0, int(alpha * n_iters))
    high_idx = min(n_iters - 1, int((1 - alpha) * n_iters))
    return round(deltas[low_idx], 4), round(deltas[high_idx], 4)


def cohens_d_effect_size(
    a_values: list[float], b_values: list[float]
) -> float | None:
    """Cohen's d = (mean_b - mean_a) / pooled_std。
    用于替代 run-vs-run 错位的 kappa（kappa 语义是 rater 一致性，
    run_a / run_b 用不同 judge 时不该用 kappa）。

    返回 None 表示样本不足或方差为 0（无判别意义）。
    """
    if len(a_values) < 2 or len(b_values) < 2:
        return None
    mean_a = sum(a_values) / len(a_values)
    mean_b = sum(b_values) / len(b_values)
    var_a = sum((v - mean_a) ** 2 for v in a_values) / (len(a_values) - 1)
    var_b = sum((v - mean_b) ** 2 for v in b_values) / (len(b_values) - 1)
    pooled = ((var_a + var_b) / 2) ** 0.5
    if pooled == 0:
        return None
    return round((mean_b - mean_a) / pooled, 4)


# ====================================================================
# Spec-5：Cohen's weighted kappa（quadratic）— 手写实现，不依赖 sklearn
# 仅用于 human-vs-judge 一致性场景（agreement.py），不再用于 run-vs-run
# ====================================================================


def cohens_weighted_kappa(
    scores_a: list[float | None],
    scores_b: list[float | None],
    levels: list[float] | None = None,
) -> tuple[float | None, list[list[int]] | None]:
    """Cohen's weighted κ（quadratic weights）针对 ordinal levels [0, 0.5, 1]。

    返回 (kappa, confusion_matrix)。kappa 为 None 表示样本不足或所有 rater 完全一致
    导致期望矩阵为 0（无法计算）。
    """
    levels = levels or [0.0, 0.5, 1.0]
    K = len(levels)
    if K < 2:
        return None, None

    # 对齐过滤：两边都不能是 None，且必须在 levels 中
    pairs: list[tuple[int, int]] = []
    level_index = {v: i for i, v in enumerate(levels)}
    for a, b in zip(scores_a, scores_b):
        if a is None or b is None:
            continue
        if a not in level_index or b not in level_index:
            continue
        pairs.append((level_index[a], level_index[b]))

    n = len(pairs)
    if n < 2:
        return None, None

    # 观察矩阵 O[i][j]
    O = [[0 for _ in range(K)] for _ in range(K)]
    for i, j in pairs:
        O[i][j] += 1

    # 行/列边际
    row_sum = [sum(O[i]) for i in range(K)]
    col_sum = [sum(O[i][j] for i in range(K)) for j in range(K)]

    # 期望矩阵 E[i][j] = row_sum[i] * col_sum[j] / n
    E = [[row_sum[i] * col_sum[j] / n for j in range(K)] for i in range(K)]

    # 权重矩阵 W[i][j] = ((i - j) / (K - 1)) ** 2
    W = [[((i - j) / (K - 1)) ** 2 for j in range(K)] for i in range(K)]

    num = sum(W[i][j] * O[i][j] for i in range(K) for j in range(K))
    den = sum(W[i][j] * E[i][j] for i in range(K) for j in range(K))
    if den == 0:
        # 期望矩阵权重和为 0：边际频率集中在单 level。
        # 分两种情况：
        #   (a) 观察矩阵 O 全在对角线 → 完美一致 → 数学退化但语义上 kappa=1.0
        #   (b) 观察矩阵 O 有非对角项但 E 仍为 0 → 不可能（数学上 E=0 ⇒ row/col 边际之一为 0）
        off_diag = sum(O[i][j] for i in range(K) for j in range(K) if i != j)
        if off_diag == 0 and n > 0:
            return 1.0, O
        return None, O
    kappa = 1.0 - num / den
    return round(kappa, 4), O


# ====================================================================
# Spec-6：Chi-square p-value（小样本警告）
# ====================================================================


def _chi2_sf(x: float, k: int) -> float:
    """Chi-square 生存函数 P(X >= x) for df=k。

    使用正则化不完全 gamma 函数 Q(k/2, x/2)。这里手写一个简单 series + Lentz 连分式
    近似，避免引入 scipy。仅用于展示量级，不追求高精度。
    """
    if x <= 0:
        return 1.0
    a = k / 2.0
    z = x / 2.0
    # 使用 Numerical Recipes 风格：x < a+1 用 series；否则 continued fraction
    if z < a + 1.0:
        # Series for P(a, z) = 1 - Q
        term = 1.0 / a
        total = term
        n = 1
        ap = a
        while n < 200:
            ap += 1.0
            term *= z / ap
            total += term
            if abs(term) < abs(total) * 1e-10:
                break
            n += 1
        P = total * math.exp(-z + a * math.log(z) - math.lgamma(a))
        return max(0.0, min(1.0, 1.0 - P))
    else:
        # Continued fraction for Q(a, z)
        eps = 1e-14
        FPMIN = 1e-300
        b = z + 1.0 - a
        c = 1.0 / FPMIN
        d = 1.0 / b
        h = d
        for i in range(1, 200):
            an = -i * (i - a)
            b += 2.0
            d = an * d + b
            if abs(d) < FPMIN:
                d = FPMIN
            c = b + an / c
            if abs(c) < FPMIN:
                c = FPMIN
            d = 1.0 / d
            delta = d * c
            h *= delta
            if abs(delta - 1.0) < eps:
                break
        Q = math.exp(-z + a * math.log(z) - math.lgamma(a)) * h
        return max(0.0, min(1.0, Q))


def chi_square_dim(
    scores_a: list[float | None],
    scores_b: list[float | None],
    threshold: float = PASS_THRESHOLD,
) -> float | None:
    """计算 2×2 卡方检验 p-value：pass/fail × A/B。

    Spec-6：n < 30 返回 None。
    返回 p-value（float）或 None（样本不足 / 期望频数为 0 / 退化）。
    """
    # 收集所有非 None 的 (run, pass_flag) 配对
    a_vals = [s for s in scores_a if s is not None]
    b_vals = [s for s in scores_b if s is not None]
    total_n = len(a_vals) + len(b_vals)
    if total_n < 30:
        return None

    # 2×2 列联表：rows = [run_a, run_b]，cols = [pass, fail]
    a_pass = sum(1 for s in a_vals if s >= threshold)
    a_fail = len(a_vals) - a_pass
    b_pass = sum(1 for s in b_vals if s >= threshold)
    b_fail = len(b_vals) - b_pass

    O = [[a_pass, a_fail], [b_pass, b_fail]]
    row_sum = [a_pass + a_fail, b_pass + b_fail]
    col_sum = [a_pass + b_pass, a_fail + b_fail]
    n = total_n

    if 0 in row_sum or 0 in col_sum:
        return None

    chi2 = 0.0
    for i in range(2):
        for j in range(2):
            e = row_sum[i] * col_sum[j] / n
            if e == 0:
                continue
            chi2 += (O[i][j] - e) ** 2 / e

    # df = (rows-1) * (cols-1) = 1
    return round(_chi2_sf(chi2, 1), 4)


# ====================================================================
# 主编排函数
# ====================================================================


def _summarize_run(run: EvalRun) -> dict:
    return {
        "id": run.id,
        "name": run.name,
        "status": run.status,
        "weighted_score": run.weighted_score,
        "pass_rate": run.pass_rate,
        "dataset_id": run.dataset_id,
        "bot_version_id": run.bot_version_id,
        "judge_model_id": run.judge_model_id,
        "judge_prompt_version_ids": run.judge_prompt_version_ids,
        "dimensions_selected": run.dimensions_selected,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def compute_comparison_payload(
    db: Session, run_a: EvalRun, run_b: EvalRun, ctype: str
) -> dict:
    """Spec-8：同步即时计算 comparison payload。"""
    # 拉 case results
    cases_a = (
        db.query(EvalCaseResult).filter(EvalCaseResult.eval_run_id == run_a.id).all()
    )
    cases_b = (
        db.query(EvalCaseResult).filter(EvalCaseResult.eval_run_id == run_b.id).all()
    )

    # Spec-2：按 conversation_id（FK 到 conversation）对齐
    map_b = {c.conversation_id: c for c in cases_b}

    # 同时拉 conversation_id_src 给前端展示用
    conv_ids = {c.conversation_id for c in cases_a} | set(map_b.keys())
    conv_src_map: dict[int, str] = {}
    if conv_ids:
        for conv in (
            db.query(Conversation).filter(Conversation.id.in_(list(conv_ids))).all()
        ):
            conv_src_map[conv.id] = conv.conversation_id_src

    aligned_pairs: list[tuple[EvalCaseResult, EvalCaseResult, str]] = []
    for ca in cases_a:
        cb = map_b.get(ca.conversation_id)
        if cb is None:
            continue
        aligned_pairs.append(
            (ca, cb, conv_src_map.get(ca.conversation_id, str(ca.conversation_id)))
        )

    dim_codes = run_a.dimensions_selected or list(DEFAULT_DIMENSION_WEIGHTS.keys())

    # Spec-10：空集合容错 — 仍构造结构化空 payload
    if not aligned_pairs:
        movements = {
            "session_movement": {"improved": [], "regressed": []},
            "dimension_movements": {d: {"improved": [], "regressed": []} for d in dim_codes},
        }
        return {
            "type": ctype,
            "run_a_summary": _summarize_run(run_a),
            "run_b_summary": _summarize_run(run_b),
            "aligned_count": 0,
            "sample_size": 0,
            "session_movement": movements["session_movement"],
            "dimension_movements": movements["dimension_movements"],
            "dim_deltas": [
                {
                    "dim_code": d,
                    "dim_name": DIMENSION_NAMES.get(d, d),
                    "avg_a": None,
                    "avg_b": None,
                    "delta": None,
                    "chi_square_pvalue": None,
                    "delta_ci_low": None,
                    "delta_ci_high": None,
                    "sample_size": 0,
                }
                for d in dim_codes
            ],
            "score_distribution_overlap": None,
            "computed_at": datetime.utcnow().isoformat(),
        }

    # Spec-4：movements
    movements = compute_movements(aligned_pairs, dim_codes)

    # 维度 delta + chi-square
    dim_deltas = []
    for dim in dim_codes:
        col = f"{dim}_score"
        a_scores = [getattr(ca, col) for ca, _, _ in aligned_pairs]
        b_scores = [getattr(cb, col) for _, cb, _ in aligned_pairs]
        a_valid = [v for v in a_scores if v is not None]
        b_valid = [v for v in b_scores if v is not None]
        avg_a = round(sum(a_valid) / len(a_valid), 4) if a_valid else None
        avg_b = round(sum(b_valid) / len(b_valid), 4) if b_valid else None
        delta = (
            round(avg_b - avg_a, 4)
            if (avg_a is not None and avg_b is not None)
            else None
        )
        p_value = chi_square_dim(a_scores, b_scores)
        delta_ci_low, delta_ci_high = _bootstrap_delta_ci(a_valid, b_valid)
        dim_deltas.append(
            {
                "dim_code": dim,
                "dim_name": DIMENSION_NAMES.get(dim, dim),
                "avg_a": avg_a,
                "avg_b": avg_b,
                "delta": delta,
                "chi_square_pvalue": p_value,
                "delta_ci_low": delta_ci_low,
                "delta_ci_high": delta_ci_high,
                "sample_size": min(len(a_valid), len(b_valid)),
            }
        )

    # M1.1：run-vs-run 不再用 Cohen's κ（语义错位 — kappa 是 rater 一致性，
    # 而 run_a/run_b 用不同 judge 时 judge 输出差异不该被当作 rater 不一致）。
    # 改用 Cohen's d 效应量作为 score_distribution_overlap 量化指标。
    a_scores_full = [ca.weighted_score for ca, _, _ in aligned_pairs if ca.weighted_score is not None]
    b_scores_full = [cb.weighted_score for _, cb, _ in aligned_pairs if cb.weighted_score is not None]
    score_distribution_overlap = cohens_d_effect_size(a_scores_full, b_scores_full)

    return {
        "type": ctype,
        "run_a_summary": _summarize_run(run_a),
        "run_b_summary": _summarize_run(run_b),
        "aligned_count": len(aligned_pairs),
        "sample_size": len(aligned_pairs),
        "session_movement": movements["session_movement"],
        "dimension_movements": movements["dimension_movements"],
        "dim_deltas": dim_deltas,
        "score_distribution_overlap": score_distribution_overlap,
        "computed_at": datetime.utcnow().isoformat(),
    }
