"""集成测试：judge 返回「缺字段 / 字段为 null / 非数值」时，evaluator 与 scoring
走完整路径仍能正确得到 score=None，并最终被 weighted_score 跳过而不是按 0 拉低均值。

测试不依赖真实 LLM / DB / Celery，只构造 FakeJudgeClient，但用真实的
PromptRenderer + ALL_V4_TEMPLATES + evaluators + scoring，覆盖所有六维。

跑：
  docker compose exec api pytest tests/test_missing_field_full_path.py -v
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import DEFAULT_DIMENSION_WEIGHTS
from app.services.eval_engine.evaluators import (
    Dim1Evaluator,
    Dim2Evaluator,
    Dim3Evaluator,
    Dim4Evaluator,
    Dim5Evaluator,
    Dim6Evaluator,
)
from app.services.eval_engine.judge_client import BaseJudgeClient
from app.services.eval_engine.prompt_renderer import PromptRenderer
from app.services.eval_engine.prompts_v4_templates import ALL_V4_TEMPLATES
from app.services.scoring import conversation_weighted_score


# ---------------------------------------------------------------------------
# Fake judge：按 queue 顺序返回预设响应，每次 call 消费一项
# ---------------------------------------------------------------------------

class FakeJudgeClient(BaseJudgeClient):
    provider = "fake"

    def __init__(self, responses: list[dict | None]):
        # 不调 super().__init__ 避免连真 API；只塞必要属性
        self.model_id = "fake-model"
        self.temperature = 0.0
        self.max_retries = 1
        self.timeout = 1
        self._queue = list(responses)
        self.calls: list[list[dict]] = []  # 记录每次接收到的 messages

    def _create_completion(self, messages):  # pragma: no cover — 不会被走
        raise NotImplementedError

    def call(self, messages):
        self.calls.append(messages)
        if not self._queue:
            return None
        return self._queue.pop(0)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def renderer() -> PromptRenderer:
    return PromptRenderer(ALL_V4_TEMPLATES)


@pytest.fixture(scope="module")
def sample_conv() -> dict:
    """从 mock 数据找一个 >= 3 轮且有 rewritten_query 的 conversation。
    若数据文件不存在，构造一条最小可用样例。
    """
    here = Path(__file__).resolve()
    candidates = [Path("/seeds/mock_multi_turn_queries_100.json")]
    for parent in here.parents:
        candidates.append(parent / "mock_multi_turn_queries_100.json")
    for p in candidates:
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            for conv in data:
                turns = conv.get("turns", [])
                if (
                    len(turns) >= 3
                    and all(t.get("rewritten_query") for t in turns)
                ):
                    return {
                        "conversation_id": conv["conversation_id"],
                        "total_turns": len(turns),
                        "turns": [
                            {
                                "turn_index": t["turn_index"],
                                "user_query": t["user_query"],
                                "rewritten_query": t.get("rewritten_query"),
                                "timestamp": t.get("timestamp"),
                            }
                            for t in turns
                        ],
                    }
    # fallback：手工构造，避免本地无 mock 文件时 fixture 失败
    return {
        "conversation_id": "synthetic_conv_1",
        "total_turns": 3,
        "turns": [
            {"turn_index": 1, "user_query": "推荐一双跑鞋", "rewritten_query": "推荐一双跑鞋",
             "timestamp": None},
            {"turn_index": 2, "user_query": "500 元以内", "rewritten_query": "500 元以内的跑鞋",
             "timestamp": None},
            {"turn_index": 3, "user_query": "再来点别的", "rewritten_query": "再推荐 500 元以内的跑鞋",
             "timestamp": None},
        ],
    }


# ---------------------------------------------------------------------------
# 单维度：dim1 / dim2 / dim6 → 缺 overall_score / score → 单维度 score=None
# ---------------------------------------------------------------------------

def test_dim1_missing_overall_score_returns_none(renderer, sample_conv, caplog):
    """judge 返回 JSON 但没有 overall_score 字段 → 每轮 score=None，dim1 总分=None。"""
    rewritten_turns = sum(1 for t in sample_conv["turns"] if t["rewritten_query"])
    fake = FakeJudgeClient(
        responses=[
            # 故意把 score key 写错（final_score 而非 overall_score）
            {"final_score": 1, "explanation": "all good"}
            for _ in range(rewritten_turns)
        ]
    )
    ev = Dim1Evaluator(fake, renderer, request_interval_sec=0)
    with caplog.at_level("WARNING"):
        result = ev.evaluate(sample_conv)

    assert result["score"] is None, "缺字段时 dim1 不应回退到 0"
    assert len(result["turn_scores"]) == rewritten_turns
    for ts in result["turn_scores"]:
        assert ts["score"] is None
        # detail 仍然保留原始 judge 响应，便于人工排查
        assert ts["detail"]["final_score"] == 1
    # 至少打一条 warning，提示「字段缺失 + 实际 key 名」
    assert any(
        "missing field" in rec.message and "final_score" in rec.message
        for rec in caplog.records
    ), "应当 warning 列出真实 key 帮助定位"


def test_dim2_overall_score_is_null_returns_none(renderer, sample_conv, caplog):
    """judge 返回 overall_score=null 也算缺，session 级 dim2=None。"""
    fake = FakeJudgeClient(
        responses=[{"extracted_constraints": [], "overall_score": None, "explanation": "n/a"}]
    )
    ev = Dim2Evaluator(fake, renderer, request_interval_sec=0)
    with caplog.at_level("WARNING"):
        result = ev.evaluate(sample_conv)

    assert result["score"] is None
    assert any("is null" in rec.message for rec in caplog.records)


def test_dim6_score_non_numeric_returns_none(renderer, sample_conv, caplog):
    """score 是字符串而非数值 → 也判为 None，不静默 cast。"""
    fake = FakeJudgeClient(
        responses=[
            {
                "applicable": True,
                "correction_signals": [],
                "subsequent_rewrites_check": [],
                "score": "0.8",  # 字符串，不是数字
                "explanation": "x",
            }
        ]
    )
    ev = Dim6Evaluator(fake, renderer, request_interval_sec=0)
    with caplog.at_level("WARNING"):
        result = ev.evaluate(sample_conv)

    assert result["score"] is None
    assert any("non-numeric" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# Dim3/4/5：applicable=True 但 score 缺 → 该轮不计入均值
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "evaluator_cls, dim_code",
    [(Dim3Evaluator, "dim3"), (Dim4Evaluator, "dim4"), (Dim5Evaluator, "dim5")],
)
def test_dim3_4_5_applicable_but_missing_score(
    renderer, sample_conv, caplog, evaluator_cls, dim_code
):
    """applicable=True 但 JSON 没 score key，applicable_turns 会自增（用于审计），
    但 scores 列表里不放该轮，最终 dim 均值=None（applicable_turns==1 但 scores 空）。
    """
    rewritten_turns = sum(1 for t in sample_conv["turns"] if t["rewritten_query"])
    fake = FakeJudgeClient(
        responses=[
            {"applicable": True, "explanation": f"{dim_code} missing score"}
            for _ in range(rewritten_turns)
        ]
    )
    ev = evaluator_cls(fake, renderer, request_interval_sec=0)
    with caplog.at_level("WARNING"):
        result = ev.evaluate(sample_conv)

    assert result["score"] is None, f"{dim_code} 缺 score 不应回退到 0"
    assert result["applicable_turns"] == rewritten_turns
    # 每一轮 turn_score 都应是 None
    for ts in result["turn_scores"]:
        assert ts["applicable"] is True
        assert ts["score"] is None


@pytest.mark.parametrize(
    "evaluator_cls, dim_code",
    [(Dim3Evaluator, "dim3"), (Dim4Evaluator, "dim4"), (Dim5Evaluator, "dim5")],
)
def test_dim3_4_5_applicable_false_all_turns(
    renderer, sample_conv, caplog, evaluator_cls, dim_code
):
    """applicable=False（合法的「跳过」语义）→ dim 均值=None，不应打 warning。"""
    rewritten_turns = sum(1 for t in sample_conv["turns"] if t["rewritten_query"])
    fake = FakeJudgeClient(
        responses=[
            {"applicable": False, "explanation": "not applicable"}
            for _ in range(rewritten_turns)
        ]
    )
    ev = evaluator_cls(fake, renderer, request_interval_sec=0)
    with caplog.at_level("WARNING"):
        result = ev.evaluate(sample_conv)

    assert result["score"] is None
    assert result["applicable_turns"] == 0
    # applicable=False 是正常分支，不该 warning
    assert not any(
        dim_code in rec.message and ("missing field" in rec.message or "is null" in rec.message)
        for rec in caplog.records
    ), "applicable=False 路径不应触发字段缺失 warning"


# ---------------------------------------------------------------------------
# Judge API 失败：BaseJudgeClient.call 返回 None
# ---------------------------------------------------------------------------

def test_dim1_judge_call_failed_score_is_none_not_zero(renderer, sample_conv):
    """API 整体失败（None 响应）→ 维度 score=None，避免被当作 0 拉低 weighted_score。"""
    rewritten_turns = sum(1 for t in sample_conv["turns"] if t["rewritten_query"])
    fake = FakeJudgeClient(responses=[None] * rewritten_turns)
    ev = Dim1Evaluator(fake, renderer, request_interval_sec=0)
    result = ev.evaluate(sample_conv)
    assert result["score"] is None
    for ts in result["turn_scores"]:
        assert ts["score"] is None
        assert ts["detail"] == {"error": "judge call failed"}


def test_dim2_judge_call_failed_session_level(renderer, sample_conv):
    fake = FakeJudgeClient(responses=[None])
    ev = Dim2Evaluator(fake, renderer, request_interval_sec=0)
    result = ev.evaluate(sample_conv)
    assert result["score"] is None
    assert result["detail"]["error"] == "judge call failed"


# ---------------------------------------------------------------------------
# End-to-end：weighted_score 在多维度部分 None 时正确再加权
# ---------------------------------------------------------------------------

def test_weighted_score_skips_none_dims_after_field_missing(renderer, sample_conv):
    """模拟 dim1/dim2 因字段缺失变 None，dim3..6 给真实分；
    weighted_score 应跳过 None 维度并在剩余维度上正确归一化。
    """
    rewritten_turns = sum(1 for t in sample_conv["turns"] if t["rewritten_query"])

    dim1 = Dim1Evaluator(
        FakeJudgeClient(
            responses=[{"final_score": 1} for _ in range(rewritten_turns)]
        ),
        renderer,
        request_interval_sec=0,
    )
    dim2 = Dim2Evaluator(
        FakeJudgeClient(responses=[{"explanation": "missing overall_score"}]),
        renderer,
        request_interval_sec=0,
    )
    dim3 = Dim3Evaluator(
        FakeJudgeClient(
            responses=[
                {"applicable": True, "score": 1, "boundary_type": "non_shopping"}
                for _ in range(rewritten_turns)
            ]
        ),
        renderer,
        request_interval_sec=0,
    )
    dim4 = Dim4Evaluator(
        FakeJudgeClient(
            responses=[
                {"applicable": False, "anaphora_type": "none"}
                for _ in range(rewritten_turns)
            ]
        ),
        renderer,
        request_interval_sec=0,
    )
    dim5 = Dim5Evaluator(
        FakeJudgeClient(
            responses=[
                {"applicable": True, "score": 0.5}
                for _ in range(rewritten_turns)
            ]
        ),
        renderer,
        request_interval_sec=0,
    )
    dim6 = Dim6Evaluator(
        FakeJudgeClient(responses=[{"applicable": True, "score": 1}]),
        renderer,
        request_interval_sec=0,
    )

    dim_scores = {
        "dim1": dim1.evaluate(sample_conv)["score"],
        "dim2": dim2.evaluate(sample_conv)["score"],
        "dim3": dim3.evaluate(sample_conv)["score"],
        "dim4": dim4.evaluate(sample_conv)["score"],
        "dim5": dim5.evaluate(sample_conv)["score"],
        "dim6": dim6.evaluate(sample_conv)["score"],
    }
    # 校验单维度结果符合预期
    assert dim_scores["dim1"] is None
    assert dim_scores["dim2"] is None
    assert dim_scores["dim3"] == 1.0
    assert dim_scores["dim4"] is None  # 全 applicable=false
    assert dim_scores["dim5"] == 0.5
    assert dim_scores["dim6"] == 1.0

    weighted, lowest = conversation_weighted_score(
        dim_scores, weights=DEFAULT_DIMENSION_WEIGHTS
    )
    # 剩余 dim3(0.10) + dim5(0.10) + dim6(0.10) 参与归一化
    # = (0.10*1 + 0.10*0.5 + 0.10*1) / (0.10+0.10+0.10)
    # = 0.25 / 0.30 = 0.8333
    assert weighted == pytest.approx(0.8333, abs=1e-3)
    assert lowest == "dim5", "最低分维度应当是 dim5"


def test_weighted_score_all_dims_none_returns_none():
    """全部维度都 None（极端故障场景）→ weighted_score=None，不该返回 0。"""
    weighted, lowest = conversation_weighted_score(
        {f"dim{i}": None for i in range(1, 7)},
        weights=DEFAULT_DIMENSION_WEIGHTS,
    )
    assert weighted is None
    assert lowest is None
