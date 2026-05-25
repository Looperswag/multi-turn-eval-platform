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

import logging
import time
from typing import Any

from app.core.config import settings
from .judge_client import BaseJudgeClient
from .prompt_renderer import PromptRenderer

logger = logging.getLogger(__name__)


def _pick_score(result: dict, key: str, dim_code: str, context: str = "") -> float | None:
    """从 judge JSON 提取数值字段；缺失/非数值时记 warning 并返回 None。

    设计：原 .get(key, 0) 会把"prompt 没让模型输出该字段"和"模型真的判 0"
    混到一起拉低 dim 均值。改为 None 后由 scoring 在权重聚合时跳过，
    既不污染 avg，也能在日志里看出是哪一类失败。
    """
    if key not in result:
        logger.warning(
            "[%s] judge response missing field %r%s; keys=%s",
            dim_code,
            key,
            f" ({context})" if context else "",
            list(result.keys()),
        )
        return None
    val = result[key]
    if val is None:
        logger.warning(
            "[%s] judge response field %r is null%s",
            dim_code,
            key,
            f" ({context})" if context else "",
        )
        return None
    if not isinstance(val, (int, float)):
        logger.warning(
            "[%s] judge response field %r is non-numeric%s: %r",
            dim_code,
            key,
            f" ({context})" if context else "",
            val,
        )
        return None
    return float(val)


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
# A.4 v5 专用：扩展的 history / turns 字符串拼装（含 bot_response）
# ---------------------------------------------------------------------------


def build_history_text_with_bot_reply(history_turns: list[dict]) -> str:
    """v5 通用：每轮含 user_query + 改写 + bot 回复 + 意图分类。无字段时跳过该行。"""
    text = ""
    for t in history_turns:
        text += f"  第{t['turn_index']}轮 用户query: {t['user_query']}\n"
        if t.get("rewritten_query"):
            text += f"  第{t['turn_index']}轮 改写query: {t['rewritten_query']}\n"
        if t.get("intent_type"):
            text += f"  第{t['turn_index']}轮 bot意图判定: {t['intent_type']}\n"
        if t.get("bot_response"):
            # 截到 200 字避免历史 token 爆炸
            br = str(t["bot_response"])[:200].replace("\n", " ")
            text += f"  第{t['turn_index']}轮 bot回复(节选): {br}\n"
    return text


def build_turns_text_with_meta(all_turns: list[dict]) -> str:
    """v5 dim2/6 用：每轮 user / 改写 / inherited / dropped / bot 回复全列。"""
    text = ""
    for t in all_turns:
        text += f"  第{t['turn_index']}轮 用户query: {t['user_query']}\n"
        rq = t.get("rewritten_query") or "(无改写)"
        text += f"  第{t['turn_index']}轮 改写query: {rq}\n"
        inh = t.get("inherited_constraints")
        if inh:
            text += f"  第{t['turn_index']}轮 bot自报继承约束: {inh}\n"
        drp = t.get("dropped_constraints")
        if drp:
            text += f"  第{t['turn_index']}轮 bot自报丢弃约束: {drp}\n"
        if t.get("intent_type"):
            text += f"  第{t['turn_index']}轮 bot意图: {t['intent_type']}\n"
        if t.get("bot_response"):
            br = str(t["bot_response"])[:200].replace("\n", " ")
            text += f"  第{t['turn_index']}轮 bot回复(节选): {br}\n"
        text += "\n"
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
        scores: list[float] = []  # 只放有效分；judge 失败 / 缺字段不入此列表
        details = []
        for i, turn in enumerate(turns):
            if turn["rewritten_query"] is None:
                continue
            history = turns[:i]
            history_text = build_history_text_with_rewrite(history)
            history_text_with_bot = build_history_text_with_bot_reply(history)
            messages = self._render(
                history_text=history_text,
                history_text_with_bot=history_text_with_bot,
                current_user_query=turn["user_query"],
                current_rewritten_query=turn["rewritten_query"],
                current_intent_type=(turn.get("intent_type") or "未知"),
                current_inherited_constraints=(turn.get("inherited_constraints") or []),
                current_dropped_constraints=(turn.get("dropped_constraints") or []),
                current_bot_response=(turn.get("bot_response") or ""),
            )
            result = self._call(messages)
            if result:
                score = _pick_score(result, "overall_score", self.dimension_code,
                                    context=f"turn={turn['turn_index']}")
                if score is not None:
                    scores.append(score)
                details.append({"turn_index": turn["turn_index"], "score": score, "detail": result})
            else:
                logger.warning(
                    "[%s] judge call failed after retries; turn=%s rewritten=%r",
                    self.dimension_code, turn["turn_index"], turn["rewritten_query"],
                )
                details.append(
                    {
                        "turn_index": turn["turn_index"],
                        "score": None,
                        "detail": {"error": "judge call failed"},
                    }
                )
        avg = round(sum(scores) / len(scores), 4) if scores else None
        return {
            "dimension": self.dimension_name,
            "dimension_code": self.dimension_code,
            "score": avg,
            "turn_scores": details,
        }


# ---------------------------------------------------------------------------
# Dim1 改写忠实性（会话级一次调用，模型返回 evaluations[] per-turn）
# ---------------------------------------------------------------------------
# 与 Dim1Evaluator 的区别：
#  - 老的 per-turn 评估器：每轮调 1 次 judge，模型只看历史 + 当前轮
#  - 这个 session 版：1 次 judge 看完整 session，模型自己按轮输出
#    {evaluations: [{turn_index, overall_score, ...}, ...]}
# pipeline 仍按 turn_scores 数组写 EvalTurnResult，前端 drawer 直接复用。
# 首轮无改写 → 模型按 prompt 自处理 overall_score=1（但参与平均；
# 用户 prompt 明确说首轮算 1）。

class Dim1SessionEvaluator(BaseEvaluator):
    dimension_name = "改写忠实性"
    dimension_code = "dim1"

    def evaluate(self, conversation):
        turns = conversation["turns"]
        meta_id = conversation.get("conversation_id", "")
        total_turns = conversation.get("total_turns", len(turns))

        turns_text = build_turns_text_full(turns)
        turns_text_with_meta = build_turns_text_with_meta(turns)
        messages = self._render(
            meta_id=meta_id,
            total_turns=total_turns,
            turns_text=turns_text,
            turns_text_with_meta=turns_text_with_meta,
        )
        result = self._call(messages)
        if not result:
            logger.warning(
                "[%s] session-level judge call failed after retries; conv=%s",
                self.dimension_code, meta_id,
            )
            return {
                "dimension": self.dimension_name,
                "dimension_code": self.dimension_code,
                "score": None,
                "detail": {"error": "judge call failed"},
                "turn_scores": [],
            }

        evaluations = result.get("evaluations") or []
        details: list[dict] = []
        scores: list[float] = []
        # 按模型给出的 evaluations 拆 per-turn 分数
        for ev in evaluations:
            if not isinstance(ev, dict):
                continue
            t_idx = ev.get("turn_index")
            s = _pick_score(
                ev, "overall_score", self.dimension_code,
                context=f"session={meta_id} turn={t_idx}",
            )
            if s is not None:
                scores.append(s)
            details.append({
                "turn_index": t_idx,
                "score": s,
                "detail": ev,
            })

        # 优先使用模型给出的 total_score（保留 prompt 原语义）；缺失则用本地均值
        model_total = result.get("total_score")
        if isinstance(model_total, (int, float)):
            avg = round(float(model_total), 4)
        else:
            avg = round(sum(scores) / len(scores), 4) if scores else None

        return {
            "dimension": self.dimension_name,
            "dimension_code": self.dimension_code,
            "score": avg,
            "detail": result,
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
        # 2 轮即可评估约束保留：≥2 轮才有"前一轮约束 → 当前轮是否保留"的判断对象
        if len(turns) < 2:
            return {
                "dimension": self.dimension_name,
                "dimension_code": self.dimension_code,
                "score": None,
                "detail": {"note": "对话轮次不足2轮，跳过"},
            }
        turns_text = build_turns_text_full(turns)
        turns_text_with_meta = build_turns_text_with_meta(turns)
        messages = self._render(
            meta_id=conversation.get("conversation_id", ""),
            total_turns=conversation.get("total_turns", len(turns)),
            turns_text=turns_text,
            turns_text_with_meta=turns_text_with_meta,
        )
        result = self._call(messages)
        if result:
            score = _pick_score(result, "overall_score", self.dimension_code)
            return {
                "dimension": self.dimension_name,
                "dimension_code": self.dimension_code,
                "score": round(score, 4) if score is not None else None,
                "detail": result,
            }
        logger.warning("[%s] judge call failed after retries; session-level", self.dimension_code)
        return {
            "dimension": self.dimension_name,
            "dimension_code": self.dimension_code,
            "score": None,
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
        scores: list[float] = []
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
                applicable = bool(result.get("applicable", False))
                turn_score = (
                    _pick_score(result, "score", self.dimension_code,
                                context=f"turn={turn['turn_index']}")
                    if applicable
                    else None
                )
                if applicable:
                    applicable_count += 1
                    if turn_score is not None:
                        scores.append(turn_score)
                details.append(
                    {
                        "turn_index": turn["turn_index"],
                        "applicable": applicable,
                        "score": turn_score,
                        "detail": result,
                    }
                )
            else:
                logger.warning(
                    "[%s] judge call failed after retries; turn=%s",
                    self.dimension_code, turn["turn_index"],
                )
                details.append(
                    {"turn_index": turn["turn_index"], "detail": {"error": "judge call failed"}}
                )
        if applicable_count == 0 or not scores:
            avg = None
        else:
            avg = round(sum(scores) / len(scores), 4)
        return {
            "dimension": self.dimension_name,
            "dimension_code": self.dimension_code,
            "score": avg,
            "applicable_turns": applicable_count,
            "turn_scores": details,
        }


def _v5_common_ctx(history_turns: list[dict], current_turn: dict) -> dict:
    """v5 通用上下文：v4 模板只用 history_text/current_*，v5 模板额外用其余字段。
    PromptRenderer 用 StrictUndefined，但仅对"模板引用了未传"的变量报错，
    多传不影响 → 同一份 ctx 同时兼容 v4 / v5。
    """
    return {
        "history_text_with_bot": build_history_text_with_bot_reply(history_turns),
        "current_intent_type": (current_turn.get("intent_type") or "未知"),
        "current_inherited_constraints": (current_turn.get("inherited_constraints") or []),
        "current_dropped_constraints": (current_turn.get("dropped_constraints") or []),
        "current_bot_response": (current_turn.get("bot_response") or ""),
    }


class Dim3Evaluator(_SingleTurnApplicableEvaluator):
    dimension_name = "意图边界识别"
    dimension_code = "dim3"

    def _build_ctx(self, history_turns, current_turn):
        # dim3 历史只看最近 5 轮
        history_window = history_turns[-5:]
        history_text = build_history_text_with_rewrite(history_window)
        ctx = {
            "history_text": history_text,
            "current_user_query": current_turn["user_query"],
            "current_rewritten_query": current_turn["rewritten_query"],
        }
        ctx.update(_v5_common_ctx(history_window, current_turn))
        return ctx


class Dim4Evaluator(_SingleTurnApplicableEvaluator):
    dimension_name = "指代消解准确性"
    dimension_code = "dim4"

    def _build_ctx(self, history_turns, current_turn):
        history_text = build_history_text_with_rewrite(history_turns)
        ctx = {
            "history_text": history_text,
            "current_user_query": current_turn["user_query"],
            "current_rewritten_query": current_turn["rewritten_query"],
        }
        ctx.update(_v5_common_ctx(history_turns, current_turn))
        return ctx


class Dim5Evaluator(_SingleTurnApplicableEvaluator):
    dimension_name = "重复请求处理"
    dimension_code = "dim5"

    def _build_ctx(self, history_turns, current_turn):
        # dim5 历史只列 user_query
        history_text = build_history_text_user_only(history_turns)
        ctx = {
            "history_text": history_text,
            "current_user_query": current_turn["user_query"],
            "current_rewritten_query": current_turn["rewritten_query"],
        }
        ctx.update(_v5_common_ctx(history_turns, current_turn))
        return ctx


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
        turns_text_with_meta = build_turns_text_with_meta(turns)
        messages = self._render(
            meta_id=conversation.get("conversation_id", ""),
            total_turns=conversation.get("total_turns", len(turns)),
            turns_text=turns_text,
            turns_text_with_meta=turns_text_with_meta,
        )
        result = self._call(messages)
        if result:
            if not result.get("applicable", False):
                return {
                    "dimension": self.dimension_name,
                    "dimension_code": self.dimension_code,
                    "score": None,
                    "detail": result,
                }
            score = _pick_score(result, "score", self.dimension_code)
            return {
                "dimension": self.dimension_name,
                "dimension_code": self.dimension_code,
                "score": round(score, 4) if score is not None else None,
                "detail": result,
            }
        logger.warning("[%s] judge call failed after retries; session-level", self.dimension_code)
        return {
            "dimension": self.dimension_name,
            "dimension_code": self.dimension_code,
            "score": None,
            "detail": {"error": "judge call failed"},
        }
