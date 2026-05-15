"""一致率计算服务（A.5.2）。

实现自 plan §8.A.5.2 的 Spec-9..14：
- Spec-11：applicable=false case 的标注语义 — 4 档归类（ZERO/HALF/ONE/NA）
- Spec-12：sample_size < 20 时 kappa 仍计算，前端决定是否展示
- Spec-13：多 annotator 协作 — 默认按 annotator 分别返回；merge=true 时按众数合并

核心算法：
- accuracy = (judge==human 的样本数) / 总样本
- Cohen's weighted kappa（quadratic weights）— 4 档 ordinal，复用 services/comparison.py 风格
- confusion_matrix = 4×4（行 judge，列 human）
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable

# 4 档枚举：与 Spec-11 一一对应
LEVELS = ["ZERO", "HALF", "ONE", "NA"]
LEVEL_INDEX = {v: i for i, v in enumerate(LEVELS)}


def categorize(score: float | None, is_applicable: bool | None) -> str | None:
    """把 (score, applicable) 二维归类到 4 档 enum。

    规则（Spec-11）：
    - applicable=False 且 score=None → NA
    - applicable=True/None 且 score 在 {0, 0.5, 1} → ZERO/HALF/ONE
    - 其他（缺失数据）→ None
    """
    if is_applicable is False:
        return "NA"
    if score is None:
        return None
    if score == 0.0:
        return "ZERO"
    if score == 0.5:
        return "HALF"
    if score == 1.0:
        return "ONE"
    # 兜底：连续分数粗量化（理论上 dim_score 只会是 0/0.5/1）
    if score >= 0.75:
        return "ONE"
    if score >= 0.25:
        return "HALF"
    return "ZERO"


def cohens_weighted_kappa_4level(
    cats_a: list[str | None],
    cats_b: list[str | None],
) -> tuple[float | None, list[list[int]] | None, int]:
    """4 档 ordinal weighted κ（quadratic weights）。

    levels 顺序：ZERO(0) → HALF(1) → ONE(2) → NA(3)
    注意：NA 与 0/0.5/1 之间的距离 = 3（满档），是最严的惩罚。
    这符合直觉：机评说"不适用"但人评打 0/0.5/1（或反之）是最大的分歧。

    返回 (kappa, confusion_matrix 4x4, sample_size)。
    """
    K = len(LEVELS)

    pairs: list[tuple[int, int]] = []
    for a, b in zip(cats_a, cats_b):
        if a is None or b is None:
            continue
        pairs.append((LEVEL_INDEX[a], LEVEL_INDEX[b]))

    n = len(pairs)
    if n < 2:
        return None, None, n

    O = [[0 for _ in range(K)] for _ in range(K)]
    for i, j in pairs:
        O[i][j] += 1

    row_sum = [sum(O[i]) for i in range(K)]
    col_sum = [sum(O[i][j] for i in range(K)) for j in range(K)]

    E = [[row_sum[i] * col_sum[j] / n for j in range(K)] for i in range(K)]
    W = [[((i - j) / (K - 1)) ** 2 for j in range(K)] for i in range(K)]

    num = sum(W[i][j] * O[i][j] for i in range(K) for j in range(K))
    den = sum(W[i][j] * E[i][j] for i in range(K) for j in range(K))
    if den == 0:
        # 期望权重和为 0：所有数据集中在一档，无法定义 kappa
        return None, O, n
    kappa = 1.0 - num / den
    return round(kappa, 4), O, n


def compute_agreement(
    judge_scores: list[float | None],
    human_scores: list[float | None],
    judge_applicable: list[bool | None],
    human_applicable: list[bool | None],
) -> dict:
    """计算 accuracy/kappa/confusion_matrix/sample_size。

    Spec-11：先把 (score, applicable) → 4 档 enum，然后:
    - accuracy：两侧 enum 相等的比例
    - kappa：4 档 weighted κ
    - confusion_matrix：4×4，行 judge，列 human
    """
    cats_judge: list[str | None] = [
        categorize(s, a) for s, a in zip(judge_scores, judge_applicable)
    ]
    cats_human: list[str | None] = [
        categorize(s, a) for s, a in zip(human_scores, human_applicable)
    ]

    # 同时过滤两侧均有效的样本
    valid_pairs: list[tuple[str, str]] = [
        (j, h) for j, h in zip(cats_judge, cats_human) if j is not None and h is not None
    ]
    sample_size = len(valid_pairs)

    if sample_size == 0:
        return {
            "accuracy": None,
            "kappa": None,
            "confusion_matrix": [[0] * 4 for _ in range(4)],
            "sample_size": 0,
        }

    agree = sum(1 for j, h in valid_pairs if j == h)
    accuracy = round(agree / sample_size, 4)

    # 总是构造 confusion_matrix（包含 n=1 情况）
    K = len(LEVELS)
    conf_matrix = [[0] * K for _ in range(K)]
    for j, h in valid_pairs:
        conf_matrix[LEVEL_INDEX[j]][LEVEL_INDEX[h]] += 1

    kappa, _, _ = cohens_weighted_kappa_4level(cats_judge, cats_human)

    return {
        "accuracy": accuracy,
        "kappa": kappa,
        "confusion_matrix": conf_matrix,
        "sample_size": sample_size,
    }


def majority_vote(
    annotations_per_case: dict[int, list[tuple[float | None, bool | None]]],
) -> dict[int, tuple[float | None, bool | None]]:
    """Spec-13：把同 case 多 annotator 的标注合并为单一"众数"标注。

    输入：{conversation_id: [(score, is_applicable), ...]}
    输出：{conversation_id: (merged_score, merged_applicable)}

    规则：
    - 把每条标注先归类到 4 档 enum
    - 取 Counter.most_common(1)；票数相等（abstain）则返回 (None, None)
    - 把众数 enum 还原为 (score, is_applicable)
    """
    out: dict[int, tuple[float | None, bool | None]] = {}
    enum_to_pair = {
        "ZERO": (0.0, True),
        "HALF": (0.5, True),
        "ONE": (1.0, True),
        "NA": (None, False),
    }
    for cid, items in annotations_per_case.items():
        cats = [categorize(s, a) for s, a in items]
        cats = [c for c in cats if c is not None]
        if not cats:
            out[cid] = (None, None)
            continue
        counter = Counter(cats)
        top = counter.most_common()
        # 检查是否票数并列（abstain）
        if len(top) > 1 and top[0][1] == top[1][1]:
            out[cid] = (None, None)
            continue
        out[cid] = enum_to_pair[top[0][0]]
    return out
