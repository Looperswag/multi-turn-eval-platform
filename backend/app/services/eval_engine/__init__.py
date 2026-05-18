"""复用现有 multi_turn_eval 评测引擎，做最小改造以适配平台。"""
from .evaluators import (
    Dim1Evaluator,
    Dim2Evaluator,
    Dim3Evaluator,
    Dim4Evaluator,
    Dim5Evaluator,
    Dim6Evaluator,
)
from .judge_client import BaseJudgeClient, ArkJudgeClient, DeepSeekJudgeClient, build_judge_client
from .prompt_renderer import PromptRenderer

ALL_EVALUATOR_CLASSES = {
    "dim1": Dim1Evaluator,
    "dim2": Dim2Evaluator,
    "dim3": Dim3Evaluator,
    "dim4": Dim4Evaluator,
    "dim5": Dim5Evaluator,
    "dim6": Dim6Evaluator,
}

__all__ = [
    "Dim1Evaluator",
    "Dim2Evaluator",
    "Dim3Evaluator",
    "Dim4Evaluator",
    "Dim5Evaluator",
    "Dim6Evaluator",
    "BaseJudgeClient",
    "ArkJudgeClient",
    "DeepSeekJudgeClient",
    "build_judge_client",
    "PromptRenderer",
    "ALL_EVALUATOR_CLASSES",
]
