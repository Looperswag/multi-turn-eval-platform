"""v5 prompt 渲染回归 + 行为单测。

- 模板与 alembic 0013/0014 内联值同步（snapshot 校验）
- evaluator 用 v5 模板 + 注入合成会话时，确认渲染产物含 bot_response、intent_type 等元字段
- 用 FakeJudgeClient 跑通完整六维评估闭环（无真实 API）
"""
from __future__ import annotations

import json

import pytest

from app.services.eval_engine.evaluators import (
    Dim1Evaluator, Dim2Evaluator, Dim3Evaluator, Dim4Evaluator,
    Dim5Evaluator, Dim6Evaluator,
)
from app.services.eval_engine.judge_client import BaseJudgeClient
from app.services.eval_engine.prompt_renderer import PromptRenderer
from app.services.eval_engine.prompts_v5_templates import ALL_V5_TEMPLATES


@pytest.fixture(scope="module")
def renderer():
    return PromptRenderer(ALL_V5_TEMPLATES)


@pytest.fixture(scope="module")
def online_conv():
    """模拟 60-conv 线上数据中的一条：3 轮，含 phantom turn 1 + bot 元信息齐全。"""
    return {
        "conversation_id": "test_conv_online",
        "total_turns": 3,
        "turns": [
            {
                "turn_index": 1,
                "user_query": "帮我找优惠",
                "rewritten_query": None,
                "timestamp": "2026-05-18 23:50:00",
                "bot_response": "好的，你想找什么品类的优惠？",
                "intent_type": None,
                "inherited_constraints": None,
                "dropped_constraints": None,
                "needs_rewrite": None,
            },
            {
                "turn_index": 2,
                "user_query": "本人身形偏瘦，身高1.71米，帮我搭配夏天短袖",
                "rewritten_query": "帮我推荐适合夏天穿的短袖上衣，用户身形偏瘦，身高1.71米",
                "timestamp": "2026-05-18 23:55:57",
                "bot_response": "你对哪款比较感兴趣？我可以详细展开。",
                "intent_type": "商品检索",
                "inherited_constraints": ["身形偏瘦", "身高1.71米", "夏季短袖上衣"],
                "dropped_constraints": [],
                "needs_rewrite": True,
            },
            {
                "turn_index": 3,
                "user_query": "多推几款我选择",
                "rewritten_query": "请推荐几款适合夏天穿的短袖上衣，身形偏瘦，身高1.71米",
                "timestamp": "2026-05-18 23:58:02",
                "bot_response": None,
                "intent_type": "商品检索",
                "inherited_constraints": ["夏季短袖上衣", "身形偏瘦", "身高1.71米"],
                "dropped_constraints": [],
                "needs_rewrite": True,
            },
        ],
    }


# ---------------------------------------------------------------------------
# Fake judge：返回固定 JSON，按 dim 出不同 schema
# ---------------------------------------------------------------------------


class FakeJudgeClient(BaseJudgeClient):
    provider = "fake-v5"

    def __init__(self, response: dict):
        self.model_id = "fake-v5"
        self.temperature = 0.0
        self.max_retries = 1
        self.timeout = 1
        self.response = response
        self.calls: list[list[dict]] = []

    def _create_completion(self, messages):  # pragma: no cover
        raise NotImplementedError

    def call(self, messages):
        self.calls.append(messages)
        return self.response


# ---------------------------------------------------------------------------
# 渲染 snapshot：确认 v5 prompt 把元字段拼进了 messages content
# ---------------------------------------------------------------------------


def test_dim1_v5_render_contains_bot_metadata(renderer, online_conv):
    """dim1 v5 prompt 应当含 intent_type / bot 回复 / 历史含 bot 元信息。"""
    fake = FakeJudgeClient({"overall_score": 1.0, "explanation": "ok"})
    ev = Dim1Evaluator(fake, renderer, request_interval_sec=0)
    ev.evaluate(online_conv)
    # 2 个 rewritten turn → 2 次 call
    assert len(fake.calls) == 2
    content = fake.calls[0][0]["content"]
    assert "bot 自报本轮意图" in content
    assert "商品检索" in content
    assert "你对哪款比较感兴趣" in content  # 来自 history_text_with_bot
    assert "领域语言校准" in content
    # 第二轮（turn 3）的 prompt 中也应当包含 turn 2 的 bot 回复作为历史
    content2 = fake.calls[1][0]["content"]
    assert "你对哪款比较感兴趣" in content2


def test_dim3_v5_render_contains_intent_and_bot_reply(renderer, online_conv):
    fake = FakeJudgeClient({
        "applicable": False,
        "boundary_type": "normal_shopping",
        "score": 0,
    })
    ev = Dim3Evaluator(fake, renderer, request_interval_sec=0)
    ev.evaluate(online_conv)
    content = fake.calls[0][0]["content"]
    assert "bot_intent_type_for_reference" in content
    assert "选项点选" in content  # 提到 boundary type 之一


def test_dim4_v5_render_includes_bot_history(renderer, online_conv):
    fake = FakeJudgeClient({
        "applicable": False, "anaphora_type": "none", "score": 0,
    })
    ev = Dim4Evaluator(fake, renderer, request_interval_sec=0)
    ev.evaluate(online_conv)
    content = fake.calls[0][0]["content"]
    assert "option_selection" in content
    # bot 历史回复应当出现
    assert "你对哪款比较感兴趣" in fake.calls[1][0]["content"]


def test_dim5_v5_render_includes_bot_history(renderer, online_conv):
    fake = FakeJudgeClient({
        "applicable": False, "score": 0, "expected_theme_source": "bot_reply",
    })
    ev = Dim5Evaluator(fake, renderer, request_interval_sec=0)
    ev.evaluate(online_conv)
    content = fake.calls[1][0]["content"]  # turn 3：包含 turn 2 的 bot 回复历史
    assert "你对哪款比较感兴趣" in content


def test_dim2_v5_render_uses_turns_with_meta(renderer, online_conv):
    fake = FakeJudgeClient({
        "false_inherited": [],
        "missed_constraints": [],
        "correctly_inherited_count": 3,
        "precision": 1.0,
        "recall": 1.0,
        "overall_score": 1.0,
        "explanation": "ok",
    })
    ev = Dim2Evaluator(fake, renderer, request_interval_sec=0)
    result = ev.evaluate(online_conv)
    assert len(fake.calls) == 1
    content = fake.calls[0][0]["content"]
    # turns_text_with_meta 包含 inherited / bot_response
    assert "bot自报继承约束" in content
    assert "身形偏瘦" in content
    assert "夏季短袖上衣" in content
    # judge 返回的字段进到 detail
    assert result["score"] == 1.0
    assert result["detail"]["precision"] == 1.0
    assert "missed_constraints" in result["detail"]


def test_dim6_v5_render_uses_turns_with_meta(renderer, online_conv):
    fake = FakeJudgeClient({
        "applicable": False,
        "correction_signals": [],
        "subsequent_rewrites_check": [],
        "score": 0,
        "explanation": "no correction",
    })
    ev = Dim6Evaluator(fake, renderer, request_interval_sec=0)
    result = ev.evaluate(online_conv)
    assert len(fake.calls) == 1
    content = fake.calls[0][0]["content"]
    assert "bot自报丢弃约束" in content or "bot自报继承约束" in content
    # applicable=false → score=None
    assert result["score"] is None


# ---------------------------------------------------------------------------
# v4 兼容：v4 模板不引用 v5 新增的 jinja 变量 → 渲染不会因 StrictUndefined 报错
# ---------------------------------------------------------------------------


def test_v4_templates_still_render_with_v5_context():
    """关键回归：v4 模板应当与 v5 evaluator 共存（v5 ctx 多传变量，v4 模板忽略即可）。"""
    from app.services.eval_engine.prompts_v4_templates import ALL_V4_TEMPLATES
    v4_renderer = PromptRenderer(ALL_V4_TEMPLATES)
    fake = FakeJudgeClient({"overall_score": 0.8, "explanation": "v4 ok"})
    ev = Dim1Evaluator(fake, v4_renderer, request_interval_sec=0)
    conv = {
        "conversation_id": "x",
        "total_turns": 2,
        "turns": [
            {"turn_index": 1, "user_query": "找跑鞋", "rewritten_query": None,
             "intent_type": None, "inherited_constraints": None, "dropped_constraints": None,
             "bot_response": None, "needs_rewrite": None, "timestamp": None},
            {"turn_index": 2, "user_query": "500 元以内", "rewritten_query": "500 元以内的跑鞋",
             "intent_type": "商品检索", "inherited_constraints": ["跑鞋"], "dropped_constraints": [],
             "bot_response": "好的", "needs_rewrite": True, "timestamp": None},
        ],
    }
    result = ev.evaluate(conv)
    # v4 模板能渲染（评测正常完成）
    assert result["score"] == 0.8
    content = fake.calls[0][0]["content"]
    # v4 模板不引用 history_text_with_bot 等 v5 变量
    assert "bot 自报本轮意图" not in content
    assert "领域语言校准" not in content
