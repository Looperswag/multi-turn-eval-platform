"""Badcase 筛选 / 排序 / facet 计算。

M3.5 从 api/eval_runs.py:list_badcases 抽出。Router 只剩参数校验 + schema 构造。
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.models import BadcaseTag, EvalCaseResult


def case_dim_score(case: EvalCaseResult, dim: str) -> float | None:
    return getattr(case, f"{dim}_score", None)


@dataclass
class BadcaseSelection:
    """list_badcases 业务层产物。Router 把它转 BadcaseListResponse。"""
    total_cases: int
    below_threshold: int
    tagged_count: int
    confirmed_count: int
    tag_counts: list[tuple[str, int]]  # 按 count desc 排序
    page: list[EvalCaseResult]
    total_filtered: int
    tags_by_case: dict[int, list[BadcaseTag]]


def select_badcases(
    *,
    all_cases: list[EvalCaseResult],
    tags_by_case: dict[int, list[BadcaseTag]],
    dim_filter: str | None,
    score_max: float,
    tag_filter: str | None,
    confirmed: bool | None,
    limit: int,
    offset: int,
) -> BadcaseSelection:
    """对已加载的 case + tag 做过滤、排序、分页，附带 stats + facet。

    输入故意是已加载的 list 而非 db session：router 负责 query，
    本函数只做内存计算，便于单测。
    """
    # ---------- stats ----------
    total_cases = len(all_cases)
    below_threshold = sum(
        1 for c in all_cases if (c.weighted_score is not None and c.weighted_score < score_max)
    )
    tagged_ids = {cid for cid, ts in tags_by_case.items() if ts}
    confirmed_ids = {
        cid for cid, ts in tags_by_case.items() if any(t.is_confirmed for t in ts)
    }

    # ---------- tag facet ----------
    tag_counter: dict[str, int] = defaultdict(int)
    for ts in tags_by_case.values():
        seen_per_case: set[str] = set()
        for t in ts:
            if t.tag in seen_per_case:
                continue
            seen_per_case.add(t.tag)
            tag_counter[t.tag] += 1
    tag_counts = sorted(tag_counter.items(), key=lambda kv: (-kv[1], kv[0]))

    # ---------- 过滤 ----------
    # C.1: 与 below_threshold 边界对齐 —— 都用严格小于 score_max
    def _passes(case: EvalCaseResult) -> bool:
        score = case_dim_score(case, dim_filter) if dim_filter else case.weighted_score
        if score is None:
            return False
        return score < score_max

    candidates = [c for c in all_cases if _passes(c)]

    if tag_filter:
        candidates = [
            c for c in candidates
            if any(t.tag == tag_filter for t in tags_by_case.get(c.id, []))
        ]

    if confirmed is not None:
        candidates = [
            c for c in candidates
            if confirmed == any(t.is_confirmed for t in tags_by_case.get(c.id, []))
        ]

    # 按 dim/weighted 分数升序（最差先）；None 沉底
    def _sort_key(c: EvalCaseResult) -> tuple:
        score = case_dim_score(c, dim_filter) if dim_filter else c.weighted_score
        return (1 if score is None else 0, score if score is not None else 0.0, c.id)

    candidates.sort(key=_sort_key)
    total = len(candidates)
    page = candidates[offset : offset + limit]

    return BadcaseSelection(
        total_cases=total_cases,
        below_threshold=below_threshold,
        tagged_count=len(tagged_ids),
        confirmed_count=len(confirmed_ids),
        tag_counts=tag_counts,
        page=page,
        total_filtered=total,
        tags_by_case=tags_by_case,
    )
