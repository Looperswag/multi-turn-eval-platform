"""Dashboard 聚合业务逻辑：成本汇总、维度切片预聚合。

M3.5 从 api/eval_runs.py 抽出 — 让 router 不直接拼 query + 聚合。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import EvalCallCost, EvalCaseResult


def compute_cost_summary(db: Session, run_id: int, session_count: int) -> dict:
    """聚合本 run 的 eval_call_cost：总成本 + per-dim breakdown。
    无数据时返回 zeros（兼容历史 run，前端可据 total_calls=0 显示"未埋点"）。
    """
    rows = (
        db.query(EvalCallCost)
        .join(EvalCaseResult, EvalCaseResult.id == EvalCallCost.eval_case_result_id)
        .filter(EvalCaseResult.eval_run_id == run_id)
        .all()
    )
    if not rows:
        return {
            "total_calls": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cost_usd": 0.0,
            "total_cost_cny": 0.0,
            "cost_per_session_cny": 0.0,
            "breakdown_by_dim": [],
        }
    total_usd = sum(r.cost_usd for r in rows)
    total_cny = sum(r.cost_cny for r in rows)
    by_dim: dict[str, dict] = {}
    for r in rows:
        d = by_dim.setdefault(
            r.dimension_code,
            {"dim_code": r.dimension_code, "calls": 0, "cost_cny": 0.0, "cost_usd": 0.0},
        )
        d["calls"] += 1
        d["cost_cny"] += r.cost_cny
        d["cost_usd"] += r.cost_usd
    return {
        "total_calls": len(rows),
        "total_prompt_tokens": sum(r.prompt_tokens for r in rows),
        "total_completion_tokens": sum(r.completion_tokens for r in rows),
        "total_cost_usd": round(total_usd, 4),
        "total_cost_cny": round(total_cny, 4),
        "cost_per_session_cny": round(total_cny / session_count, 4) if session_count else 0.0,
        "breakdown_by_dim": [
            {
                "dim_code": d["dim_code"],
                "calls": d["calls"],
                "cost_cny": round(d["cost_cny"], 4),
                "cost_usd": round(d["cost_usd"], 4),
            }
            for d in sorted(by_dim.values(), key=lambda x: x["dim_code"])
        ],
    }
