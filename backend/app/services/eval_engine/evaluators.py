"""六大维度评估器。

每个 Evaluator 收到 (conversation, judge_client, prompt_renderer) 后：
1. 在 Python 端预拼接 history_text / turns_text（避免 jinja2 模板嵌套循环）
2. 通过 PromptRenderer 把 jinja2 模板渲染为 messages
3. 调用 judge
4. 解析为统一 schema
5. 返回 {"dimension", "score", "turn_scores"/"detail"}

W2/A.3：prompt 模板由 DB 中 JudgePromptVersion.prompt_template 注入；
evaluate() 协议保持稳定。
"""
from __future__ import annotations

import time
from typing import Any

from app.core.config import settings
from .judge_client import BaseJudgeClient
from .prompt_renderer import PromptRenderer


# ---------------------------------------------------------------------------
# history/turns 字符串预拼接（与原 prompts.py 内字符串生成逻辑严格一致）
# ---------------------------------------------------------------------------

def build_history_text_with_rewrite(history_turns: list[dict]) -> str:
    """dim1/3/4 风格：每轮先出 user_query，若有 rewritten 再出 rewritten。"""
    text = ""
    for t in history_turns:
        text += f"  第{t['turn_index']}轮 用户query: {t['user_query']}\n"
        if t["rewritten_query"]:
            text += f"  第{t['turn_index']}轮 改写query: {t['rewritten_query']}\n"
    return text


def build_history_text_user_only(history_turns: list[dict]) -> str:
    """dim5 风格：只列 user_query。"""
    text = ""
    for t in history_turns:
        text += f"  第{t['turn_index']}轮 用户query: {t['user_query']}\n"
    return text


def build_turns_text_full(all_turns: list[dict]) -> str:
    """dim2/6 风格：每轮 user_query + rewritten_query（无改写时输出 (首轮无改写)），段间空行。"""
    text = ""
    for t in all_turns:
        text += f"  第{t['turn_index']}轮 用户query: {t['user_query']}\n"
        rq = t["rewritten_query"] if t["rewritten_query"] else "(首轮无改写)"
        text += f"  第{t['turn_index']}轮 改写query: {rq}\n\n"
    return text


# ---------------------------------------------------------------------------
# 基类
# ---------------------------------------------------------------------------

class BaseEvaluator:
    dimension_name: str = ""
    dimension_code: str = ""

    def __init__(
        self,
        judge_client: BaseJudgeClient,
        prompt_renderer: PromptRenderer,
        request_interval_sec: float | None = None,
    ):
        self.judge_client = judge_client
        self.prompt_renderer = prompt_renderer
        self.request_interval_sec = (
            request_interval_sec
            if request_interval_sec is not None
            else settings.default_request_interval_sec
        )

    def _call(self, messages):
        time.sleep(self.request_interval_sec)
        return self.judge_client.call(messages)

    def _render(self, **ctx):
        return self.prompt_renderer.render(self.dimension_code, **ctx)

    def evaluate(self, conversation: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Dim1 改写忠实性（逐轮）
# ---------------------------------------------------------------------------

class Dim1Evaluator(BaseEvaluator):
    dimension_name = "改写忠实性"
    dimension_code = "dim1"

    def evaluate(self, conversation):
        turns = conversation["turns"]
        scores = []
        details = []
        for i, turn in enumerate(turns):
            if turn["rewritten_query"] is None:
                continue
            history = turns[:i]
            history_text = build_history_text_with_rewrite(history)
            messages = self._render(
                history_text=history_text,
                current_user_query=turn["user_query"],
                current_rewritten_query=turn["rewritten_query"],
            )
            result = self._call(messages)
            if result:
                score = result.get("overall_score", 0)
                scores.append(score)
                details.append({"turn_index": turn["turn_index"], "score": score, "detail": result})
            else:
                scores.append(0)
                details.append(
                    {
                        "turn_index": turn["turn_index"],
                        "score": 0,
                        "detail": {"error": "judge call failed"},
                    }
                )
        avg = sum(scores) / len(scores) if scores else 0
        return {
            "dimension": self.dimension_name,
            "dimension_code": self.dimension_code,
            "score": round(avg, 4),
            "turn_scores": details,
        }


# ---------------------------------------------------------------------------
# Dim2 跨轮记忆保留（会话级）
# ---------------------------------------------------------------------------

class Dim2Evaluator(BaseEvaluator):
    dimension_name = "跨轮记忆保留"
    dimension_code = "dim2"

    def evaluate(self, conversation):
        turns = conversation["turns"]
        if len(turns) < 3:
            return {
                "dimension": self.dimension_name,
                "dimension_code": self.dimension_code,
                "score": None,
                "detail": {"note": "对话轮次不足3轮，跳过"},
            }
        turns_text = build_turns_text_full(turns)
        messages = self._render(turns_text=turns_text)
        result = self._call(messages)
        if result:
            score = result.get("overall_score", 0)
            return {
                "dimension": self.dimension_name,
                "dimension_code": self.dimension_code,
                "score": round(score, 4),
                "detail": result,
            }
        return {
            "dimension": self.dimension_name,
            "dimension_code": self.dimension_code,
            "score": 0,
            "detail": {"error": "judge call failed"},
        }


# ---------------------------------------------------------------------------
# Dim3/4/5 共享：逐轮 + applicable 过滤
# ---------------------------------------------------------------------------

class _SingleTurnApplicableEvaluator(BaseEvaluator):
    """子类通过 _build_ctx(history, current_turn) -> dict 提供模板变量。"""

    def _build_ctx(self, history_turns: list[dict], current_turn: dict) -> dict:
        raise NotImplementedError

    def evaluate(self, conversation):
        turns = conversation["turns"]
        scores = []
        details = []
        applicable_count = 0
        for i, turn in enumerate(turns):
            if turn["rewritten_query"] is None:
                continue
            history = turns[:i]
            ctx = self._build_ctx(history, turn)
            messages = self._render(**ctx)
            result = self._call(messages)
            if result:
                applicable = result.get("applicable", False)
                if applicable:
                    applicable_count += 1
                    scores.append(result.get("score", 0))
                details.append(
                    {
                        "turn_index": turn["turn_index"],
                        "applicable": applicable,
                        "score": result.get("score"),
                        "detail": result,
                    }
                )
            else:
                details.append(
                    {"turn_index": turn["turn_index"], "detail": {"error": "judge call failed"}}
                )
        if applicable_count == 0:
            avg = None
        else:
            avg = round(sum(scores) / len(scores), 4) if scores else 0
        return {
            "dimension": self.dimension_name,
            "dimension_code": self.dimension_code,
            "score": avg,
            "applicable_turns": applicable_count,
            "turn_scores": details,
        }


class Dim3Evaluator(_SingleTurnApplicableEvaluator):
    dimension_name = "意图边界识别"
    dimension_code = "dim3"

    def _build_ctx(self, history_turns, current_turn):
        # dim3 历史只看最近 5 轮
        history_text = build_history_text_with_rewrite(history_turns[-5:])
        return {
            "history_text": history_text,
            "current_user_query": current_turn["user_query"],
            "current_rewritten_query": current_turn["rewritten_query"],
        }


class Dim4Evaluator(_SingleTurnApplicableEvaluator):
    dimension_name = "指代消解准确性"
    dimension_code = "dim4"

    def _build_ctx(self, history_turns, current_turn):
        history_text = build_history_text_with_rewrite(history_turns)
        return {
            "history_text": history_text,
            "current_user_query": current_turn["user_query"],
            "current_rewritten_query": current_turn["rewritten_query"],
        }


class Dim5Evaluator(_SingleTurnApplicableEvaluator):
    dimension_name = "重复请求处理"
    dimension_code = "dim5"

    def _build_ctx(self, history_turns, current_turn):
        # dim5 历史只列 user_query
        history_text = build_history_text_user_only(history_turns)
        return {
            "history_text": history_text,
            "current_user_query": current_turn["user_query"],
            "current_rewritten_query": current_turn["rewritten_query"],
        }


# ---------------------------------------------------------------------------
# Dim6 用户纠错响应（会话级）
# ---------------------------------------------------------------------------

class Dim6Evaluator(BaseEvaluator):
    dimension_name = "用户纠错响应"
    dimension_code = "dim6"

    def evaluate(self, conversation):
        turns = conversation["turns"]
        if len(turns) < 3:
            return {
                "dimension": self.dimension_name,
                "dimension_code": self.dimension_code,
                "score": None,
                "detail": {"note": "对话轮次不足3轮，跳过"},
            }
        turns_text = build_turns_text_full(turns)
        messages = self._render(turns_text=turns_text)
        result = self._call(messages)
        if result:
            if not result.get("applicable", False):
                return {
                    "dimension": self.dimension_name,
                    "dimension_code": self.dimension_code,
                    "score": None,
                    "detail": result,
                }
            score = result.get("score", 0)
            return {
                "dimension": self.dimension_name,
                "dimension_code": self.dimension_code,
                "score": round(score, 4) if score is not None else None,
                "detail": result,
            }
        return {
            "dimension": self.dimension_name,
            "dimension_code": self.dimension_code,
            "score": 0,
            "detail": {"error": "judge call failed"},
        }
