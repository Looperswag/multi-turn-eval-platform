"""M1.3: Dim1SessionEvaluator 根据 boundary_type 设 applicable 的回归测试。

固化行为：当 judge 返回 boundary_type ∈ {non_shopping, correction,
emotion_negative, meaningless} 时，turn 的 applicable=false，分数不计入 dim1
case-level 均值（消除 dim1/dim3/dim6 双重惩罚）。
"""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.eval_engine.evaluators import (
    Dim1SessionEvaluator,
    _DIM1_NOT_APPLICABLE_BOUNDARIES,
)


def _make_evaluator(judge_response: dict) -> Dim1SessionEvaluator:
    judge = MagicMock()
    judge.call.return_value = judge_response
    renderer = MagicMock()
    renderer.render.return_value = [{"role": "user", "content": "..."}]
    renderer.strategy.return_value = "session_returns_per_turn"
    ev = Dim1SessionEvaluator(judge, renderer, request_interval_sec=0)
    return ev


def _conv(n_turns: int = 3) -> dict:
    return {
        "conversation_id": "test",
        "total_turns": n_turns,
        "turns": [
            {
                "turn_index": i + 1,
                "user_query": f"q{i+1}",
                "rewritten_query": f"r{i+1}",
            }
            for i in range(n_turns)
        ],
    }


def test_normal_shopping_turns_all_applicable_and_count():
    evaluator = _make_evaluator(
        {
            "evaluations": [
                {"turn_index": 1, "boundary_type": "normal_shopping", "overall_score": 1},
                {"turn_index": 2, "boundary_type": "normal_shopping", "overall_score": 0},
                {"turn_index": 3, "boundary_type": "normal_shopping", "overall_score": 1},
            ]
        }
    )
    result = evaluator.evaluate(_conv(3))
    assert result["score"] == 0.6667  # (1+0+1)/3
    assert [t["applicable"] for t in result["turn_scores"]] == [True, True, True]


def test_meaningless_turn_excluded_from_score():
    evaluator = _make_evaluator(
        {
            "evaluations": [
                {"turn_index": 1, "boundary_type": "normal_shopping", "overall_score": 1},
                {"turn_index": 2, "boundary_type": "meaningless", "overall_score": 0},
                {"turn_index": 3, "boundary_type": "normal_shopping", "overall_score": 1},
            ]
        }
    )
    result = evaluator.evaluate(_conv(3))
    # 修复前：(1+0+1)/3=0.6667（meaningless turn 也算）
    # 修复后：(1+1)/2=1.0（meaningless turn applicable=false 不计）
    assert result["score"] == 1.0
    assert [t["applicable"] for t in result["turn_scores"]] == [True, False, True]


def test_all_excluded_boundaries_are_not_applicable():
    """覆盖完整的 _DIM1_NOT_APPLICABLE_BOUNDARIES 集合。"""
    evals = [
        {"turn_index": i + 1, "boundary_type": bt, "overall_score": 0}
        for i, bt in enumerate(sorted(_DIM1_NOT_APPLICABLE_BOUNDARIES))
    ]
    evaluator = _make_evaluator({"evaluations": evals})
    result = evaluator.evaluate(_conv(len(evals)))
    # 全部 not-applicable → 没有有效分 → score=None
    assert result["score"] is None
    assert all(t["applicable"] is False for t in result["turn_scores"])
