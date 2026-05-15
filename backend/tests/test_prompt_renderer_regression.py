"""回归测试：jinja2 渲染产物 vs 原 f-string prompts.py 产物逐字一致。

策略：
- 取 mock_multi_turn_queries_100.json 前 2 条 conversation
- 对每条 conversation × 每个维度，分别走旧路径（prompts.py 内 build_dim*）与新路径
  （prompt_renderer + prompts_v4_templates.ALL_V4_TEMPLATES）
- 断言 messages[0]["content"] 字符串完全一致

不需要 DB / Judge API，纯字符串比对。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


# 找 mock 数据：容器内挂载到 /seeds，本地仓库挂在上一级
def _find_mock_data() -> Path:
    env_path = os.environ.get("SEED_DATA_PATH")
    if env_path and Path(env_path).exists():
        return Path(env_path)
    here = Path(__file__).resolve()
    candidates = [Path("/seeds/mock_multi_turn_queries_100.json")]
    # 向上遍历仓库各层，找到第一个匹配
    for parent in here.parents:
        candidates.append(parent / "mock_multi_turn_queries_100.json")
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(f"mock data not found in any of: {candidates}")


@pytest.fixture(scope="module")
def conversations() -> list[dict]:
    data_path = _find_mock_data()
    data = json.loads(data_path.read_text(encoding="utf-8"))
    # 前 2 条
    return data[:2]


@pytest.fixture(scope="module")
def renderer():
    from app.services.eval_engine.prompt_renderer import PromptRenderer
    from app.services.eval_engine.prompts_v4_templates import ALL_V4_TEMPLATES

    return PromptRenderer(ALL_V4_TEMPLATES)


# ---------------------------------------------------------------------------
# 工具：把 conversation -> turns list（与 evaluators 中 payload.turns 等价）
# ---------------------------------------------------------------------------

def _conv_to_turns(conv: dict) -> list[dict]:
    """mock 数据结构与 _load_conversation_payload 输出对齐。"""
    return [
        {
            "turn_index": t["turn_index"],
            "user_query": t["user_query"],
            "rewritten_query": t.get("rewritten_query"),
            "timestamp": t.get("timestamp"),
        }
        for t in conv.get("turns", [])
    ]


# ---------------------------------------------------------------------------
# 各维度回归
# ---------------------------------------------------------------------------

def _compare_dim1(conv, renderer):
    from app.services.eval_engine import prompts as old
    from app.services.eval_engine.evaluators import build_history_text_with_rewrite

    turns = _conv_to_turns(conv)
    diffs = []
    for i, turn in enumerate(turns):
        if turn["rewritten_query"] is None:
            continue
        history = turns[:i]
        old_msgs = old.build_dim1_prompt(history, turn)
        new_msgs = renderer.render(
            "dim1",
            history_text=build_history_text_with_rewrite(history),
            current_user_query=turn["user_query"],
            current_rewritten_query=turn["rewritten_query"],
        )
        if old_msgs[0]["content"] != new_msgs[0]["content"]:
            diffs.append((turn["turn_index"], old_msgs[0]["content"], new_msgs[0]["content"]))
    return diffs


def _compare_dim2(conv, renderer):
    from app.services.eval_engine import prompts as old
    from app.services.eval_engine.evaluators import build_turns_text_full

    turns = _conv_to_turns(conv)
    if len(turns) < 3:
        return []  # evaluator 会跳过
    old_msgs = old.build_dim2_prompt(turns)
    new_msgs = renderer.render("dim2", turns_text=build_turns_text_full(turns))
    if old_msgs[0]["content"] != new_msgs[0]["content"]:
        return [("conv", old_msgs[0]["content"], new_msgs[0]["content"])]
    return []


def _compare_dim3(conv, renderer):
    from app.services.eval_engine import prompts as old
    from app.services.eval_engine.evaluators import build_history_text_with_rewrite

    turns = _conv_to_turns(conv)
    diffs = []
    for i, turn in enumerate(turns):
        if turn["rewritten_query"] is None:
            continue
        history = turns[:i]
        old_msgs = old.build_dim3_prompt(history, turn)
        new_msgs = renderer.render(
            "dim3",
            history_text=build_history_text_with_rewrite(history[-5:]),
            current_user_query=turn["user_query"],
            current_rewritten_query=turn["rewritten_query"],
        )
        if old_msgs[0]["content"] != new_msgs[0]["content"]:
            diffs.append((turn["turn_index"], old_msgs[0]["content"], new_msgs[0]["content"]))
    return diffs


def _compare_dim4(conv, renderer):
    from app.services.eval_engine import prompts as old
    from app.services.eval_engine.evaluators import build_history_text_with_rewrite

    turns = _conv_to_turns(conv)
    diffs = []
    for i, turn in enumerate(turns):
        if turn["rewritten_query"] is None:
            continue
        history = turns[:i]
        old_msgs = old.build_dim4_prompt(history, turn)
        new_msgs = renderer.render(
            "dim4",
            history_text=build_history_text_with_rewrite(history),
            current_user_query=turn["user_query"],
            current_rewritten_query=turn["rewritten_query"],
        )
        if old_msgs[0]["content"] != new_msgs[0]["content"]:
            diffs.append((turn["turn_index"], old_msgs[0]["content"], new_msgs[0]["content"]))
    return diffs


def _compare_dim5(conv, renderer):
    from app.services.eval_engine import prompts as old
    from app.services.eval_engine.evaluators import build_history_text_user_only

    turns = _conv_to_turns(conv)
    diffs = []
    for i, turn in enumerate(turns):
        if turn["rewritten_query"] is None:
            continue
        history = turns[:i]
        old_msgs = old.build_dim5_prompt(history, turn)
        new_msgs = renderer.render(
            "dim5",
            history_text=build_history_text_user_only(history),
            current_user_query=turn["user_query"],
            current_rewritten_query=turn["rewritten_query"],
        )
        if old_msgs[0]["content"] != new_msgs[0]["content"]:
            diffs.append((turn["turn_index"], old_msgs[0]["content"], new_msgs[0]["content"]))
    return diffs


def _compare_dim6(conv, renderer):
    from app.services.eval_engine import prompts as old
    from app.services.eval_engine.evaluators import build_turns_text_full

    turns = _conv_to_turns(conv)
    if len(turns) < 3:
        return []
    old_msgs = old.build_dim6_prompt(turns)
    new_msgs = renderer.render("dim6", turns_text=build_turns_text_full(turns))
    if old_msgs[0]["content"] != new_msgs[0]["content"]:
        return [("conv", old_msgs[0]["content"], new_msgs[0]["content"])]
    return []


# ---------------------------------------------------------------------------
# pytest 入口
# ---------------------------------------------------------------------------

DIM_COMPARERS = {
    "dim1": _compare_dim1,
    "dim2": _compare_dim2,
    "dim3": _compare_dim3,
    "dim4": _compare_dim4,
    "dim5": _compare_dim5,
    "dim6": _compare_dim6,
}


@pytest.mark.parametrize("dim_code", list(DIM_COMPARERS.keys()))
def test_renderer_equivalence(dim_code, conversations, renderer):
    """对前 2 条 conversation，每个维度的渲染产物应与旧 f-string 完全一致。"""
    all_diffs = []
    for idx, conv in enumerate(conversations):
        diffs = DIM_COMPARERS[dim_code](conv, renderer)
        if diffs:
            for d in diffs:
                all_diffs.append((idx, d))
    if all_diffs:
        # 打印第一处 diff 便于排查
        idx, (turn_index, old_text, new_text) = all_diffs[0]
        msg_lines = [
            f"dim={dim_code} conv_idx={idx} turn_index={turn_index} 渲染产物不一致：",
            "=" * 30 + " OLD " + "=" * 30,
            old_text,
            "=" * 30 + " NEW " + "=" * 30,
            new_text,
        ]
        pytest.fail("\n".join(msg_lines))
