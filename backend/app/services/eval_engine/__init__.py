"""复用现有 multi_turn_eval 评测引擎，做最小改造以适配平台。"""
from .evaluators import (
    BaseEvaluator,
    Dim1Evaluator,
    Dim1SessionEvaluator,
    Dim2Evaluator,
    Dim3Evaluator,
    Dim4Evaluator,
    Dim5Evaluator,
    Dim6Evaluator,
)
from .judge_client import (
    BaseJudgeClient,
    ArkJudgeClient,
    DeepSeekJudgeClient,
    build_judge_client,
    set_cost_sink,
)
from .prompt_renderer import PromptRenderer


class Dim1Dispatcher(BaseEvaluator):
    """根据 JudgePromptVersion.dimension_strategy 选 per-turn 还是 session-level 的 Dim1 评估器。

    P0-2 之后：优先读 renderer.strategy('dim1')；只在 strategy 留空（旧数据）时
    才回落到模板嗅探（含 `turns_text`/`meta_id` 关键字）。这样配置显式、可在
    prompt CRUD UI 单选切换，避免误删模板关键字导致评估路径漂移。
    """

    dimension_code = "dim1"
    dimension_name = "改写忠实性"

    def __init__(self, judge_client, prompt_renderer, request_interval_sec=None):
        super().__init__(judge_client, prompt_renderer, request_interval_sec)
        self._per_turn = Dim1Evaluator(judge_client, prompt_renderer, request_interval_sec)
        self._session = Dim1SessionEvaluator(judge_client, prompt_renderer, request_interval_sec)

    def evaluate(self, conversation):
        strategy = self.prompt_renderer.strategy("dim1")
        if strategy == "session_returns_per_turn":
            return self._session.evaluate(conversation)
        if strategy == "per_turn":
            return self._per_turn.evaluate(conversation)
        # 旧数据 / 未知策略 → 回落到模板嗅探，保留 P0-2 之前的兼容行为
        tpl = self.prompt_renderer.template_source("dim1") or ""
        is_session = ("turns_text" in tpl) or ("{{ meta_id" in tpl) or ("{{meta_id" in tpl)
        return (self._session if is_session else self._per_turn).evaluate(conversation)


ALL_EVALUATOR_CLASSES = {
    "dim1": Dim1Dispatcher,
    "dim2": Dim2Evaluator,
    "dim3": Dim3Evaluator,
    "dim4": Dim4Evaluator,
    "dim5": Dim5Evaluator,
    "dim6": Dim6Evaluator,
}

__all__ = [
    "Dim1Evaluator",
    "Dim1SessionEvaluator",
    "Dim1Dispatcher",
    "Dim2Evaluator",
    "Dim3Evaluator",
    "Dim4Evaluator",
    "Dim5Evaluator",
    "Dim6Evaluator",
    "BaseJudgeClient",
    "ArkJudgeClient",
    "DeepSeekJudgeClient",
    "build_judge_client",
    "set_cost_sink",
    "PromptRenderer",
    "ALL_EVALUATOR_CLASSES",
]
