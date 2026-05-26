"""Prompt version lifecycle 业务逻辑：jinja2 校验、版本号推断、引用计数、preview 渲染。

M3.5 从 api/judge_config.py 抽出 — 让 router 只剩薄 HTTP 层。
不直接依赖 FastAPI（HTTPException 等抛给 caller）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, meta
from sqlalchemy.orm import Session

from app.models import EvalRun, JudgePromptVersion


# ---------------------------------------------------------------------------
# Jinja2 语法校验 — 抛 ValueError，caller 转 400 HTTPException
# ---------------------------------------------------------------------------


class TemplateValidationError(ValueError):
    """Caller (FastAPI router) catches this and turns into HTTP 400."""


def validate_jinja2_template(tmpl: str) -> None:
    """保存 prompt 前校验 jinja2 语法。语法错则抛 TemplateValidationError + 错误位置。"""
    if not tmpl:
        return
    try:
        Environment(undefined=StrictUndefined, autoescape=False).parse(tmpl)
    except TemplateSyntaxError as exc:
        raise TemplateValidationError(
            f"jinja2 语法错误 (line {exc.lineno}): {exc.message}"
        ) from exc


# ---------------------------------------------------------------------------
# 引用计数 + 版本号推断
# ---------------------------------------------------------------------------


def runs_referencing_prompt(db: Session, prompt: JudgePromptVersion) -> list[EvalRun]:
    """查找所有 judge_prompt_version_ids[dim_code] == prompt.id 的 run。

    简化做法：拉所有 run 在 Python 端判断，W1.5 数据量小可接受。
    """
    runs = db.query(EvalRun).all()
    out: list[EvalRun] = []
    for r in runs:
        ids = r.judge_prompt_version_ids or {}
        if not isinstance(ids, dict):
            continue
        try:
            v = ids.get(prompt.dimension_code)
        except AttributeError:
            continue
        if v is None:
            continue
        try:
            if int(v) == prompt.id:
                out.append(r)
        except (TypeError, ValueError):
            continue
    return out


def count_prompt_in_use(db: Session, prompt: JudgePromptVersion) -> int:
    return len(runs_referencing_prompt(db, prompt))


def build_prompt_usage_map(db: Session) -> dict[int, int]:
    """一次扫所有 EvalRun.judge_prompt_version_ids，得到 {prompt_version_id: in_use_count}。

    列表渲染时用一次，避免 O(P×R) 重复查询。
    """
    out: dict[int, int] = {}
    for run in db.query(EvalRun.judge_prompt_version_ids).all():
        ids = run[0] or {}
        if not isinstance(ids, dict):
            continue
        for v in ids.values():
            try:
                pv_id = int(v)
            except (TypeError, ValueError):
                continue
            out[pv_id] = out.get(pv_id, 0) + 1
    return out


def next_version_tag(db: Session, dimension_code: str, source_tag: str) -> str:
    """根据源 version_tag 推断下一个未占用的 tag。

    源是 "v4" → "v5"；源是 "v5" → "v6"。
    源是 "v4-test" / 其它格式 → 取当前 dim 下最大 v<n> 的下一个；
    找不到则 "源_clone_N"。
    """
    existing = {
        v.version_tag
        for v in db.query(JudgePromptVersion).filter(
            JudgePromptVersion.dimension_code == dimension_code
        )
    }

    # case 1: 形如 "v<n>"，直接递增
    m = re.fullmatch(r"v(\d+)", source_tag)
    if m:
        n = int(m.group(1)) + 1
        while f"v{n}" in existing:
            n += 1
        return f"v{n}"

    # case 2: 找当前 dim 下最大的 v<n>
    nums: list[int] = []
    for tag in existing:
        m2 = re.fullmatch(r"v(\d+)", tag)
        if m2:
            nums.append(int(m2.group(1)))
    if nums:
        n = max(nums) + 1
        while f"v{n}" in existing:
            n += 1
        return f"v{n}"

    # case 3: fallback —— 在 source_tag 加 _clone_N
    n = 1
    while f"{source_tag}_clone_{n}" in existing:
        n += 1
    return f"{source_tag}_clone_{n}"


# ---------------------------------------------------------------------------
# Prompt preview — 让用户在新建 / 编辑 prompt 时实时看到渲染结果
# ---------------------------------------------------------------------------


_SAMPLE_TURN = {
    "turn_index": 2,
    "user_query": "再推荐个 8000 以内的设计笔记本",
    "rewritten_query": "8000 以内设计用笔记本电脑",
}
_SAMPLE_TURNS_TEXT = (
    "  第1轮 用户query: 想买个设计师用的笔记本，预算 5000\n"
    "  第1轮 改写query: 5000 以内 设计师笔记本电脑\n\n"
    "  第2轮 用户query: 再推荐个 8000 以内的设计笔记本\n"
    "  第2轮 改写query: 8000 以内设计用笔记本电脑\n\n"
    "  第3轮 用户query: 再来个鼠标\n"
    "  第3轮 改写query: 鼠标\n\n"
)
_SAMPLE_TURNS_TEXT_WITH_META = _SAMPLE_TURNS_TEXT + (
    "（meta: total_turns=3, has_brand_pin=false）\n"
)
_SAMPLE_HISTORY_TEXT = (
    "  第1轮 用户query: 想买个设计师用的笔记本，预算 5000\n"
    "  第1轮 改写query: 5000 以内 设计师笔记本电脑\n\n"
)


def _build_preview_context() -> dict:
    return {
        "history_text": _SAMPLE_HISTORY_TEXT,
        "current_user_query": _SAMPLE_TURN["user_query"],
        "current_rewritten_query": _SAMPLE_TURN["rewritten_query"],
        "turns_text": _SAMPLE_TURNS_TEXT,
        "turns_text_with_meta": _SAMPLE_TURNS_TEXT_WITH_META,
        "meta_id": "demo_meta_001",
        "total_turns": 3,
        "turn_index": _SAMPLE_TURN["turn_index"],
        "user_query": _SAMPLE_TURN["user_query"],
        "rewritten_query": _SAMPLE_TURN["rewritten_query"],
    }


@dataclass
class PreviewResult:
    rendered: str
    vars_detected: list[str]
    vars_used: list[str]
    error: str | None


def render_preview(template: str) -> PreviewResult:
    """渲染 prompt 模板到样例 context；缺失变量以 «var» 占位。"""
    env = Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)
    ctx = _build_preview_context()
    try:
        ast = env.parse(template)
    except TemplateSyntaxError as exc:
        return PreviewResult(
            rendered="",
            vars_detected=[],
            vars_used=[],
            error=f"jinja2 语法错误 (line {exc.lineno}): {exc.message}",
        )

    detected = sorted(meta.find_undeclared_variables(ast))
    available = set(ctx.keys())
    used = [v for v in detected if v in available]
    missing = [v for v in detected if v not in available]

    render_ctx = dict(ctx)
    for v in missing:
        render_ctx[v] = f"«{v}»"

    try:
        rendered = env.from_string(template).render(**render_ctx)
    except Exception as exc:  # noqa: BLE001
        return PreviewResult(
            rendered="",
            vars_detected=detected,
            vars_used=used,
            error=f"渲染失败: {exc}",
        )

    err: str | None = None
    if missing:
        err = f"模板引用了样例上下文未提供的变量: {', '.join(missing)}（已用 «{{var}}» 占位）"
    return PreviewResult(
        rendered=rendered, vars_detected=detected, vars_used=used, error=err
    )
