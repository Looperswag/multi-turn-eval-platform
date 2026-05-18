"""Excel 导出 — 4-sheet 评测报告生成器。

迁移自 W1 时期 `multi_turn_eval/report.py::build_excel_report`，
改为直接从平台 DB（SQLAlchemy session）拉数据，而非读 JSON 文件。

Sheet 结构：
  1. 总览 — 元信息、加权总分、维度权重表
  2. 维度汇总 — 各维度均值/min/max/通过率/样本数
  3. 会话明细 — 每行一个 case，含 6 维分数、最低维度
  4. 轮次明细 — 从 eval_turn_result 或 dim_results_full 反推每轮分数
"""
from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_DIMENSION_WEIGHTS, DIMENSION_NAMES
from app.models import (
    BotVersion,
    Conversation,
    Dataset,
    EvalCaseResult,
    EvalRun,
    EvalTurnResult,
    JudgeModel,
)
from app.services.scoring import aggregate_dimension_summary

DIM_CODES = ["dim1", "dim2", "dim3", "dim4", "dim5", "dim6"]


# ---------- 样式工具 ----------

_title_font = Font(name="微软雅黑", size=14, bold=True, color="FFFFFF")
_header_font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
_body_font = Font(name="微软雅黑", size=10)
_title_fill = PatternFill("solid", fgColor="305496")
_header_fill = PatternFill("solid", fgColor="4472C4")
_low_fill = PatternFill("solid", fgColor="F8CBAD")
_mid_fill = PatternFill("solid", fgColor="FFF2CC")
_good_fill = PatternFill("solid", fgColor="C6E0B4")
_thin_border = Border(
    left=Side(style="thin", color="BFBFBF"),
    right=Side(style="thin", color="BFBFBF"),
    top=Side(style="thin", color="BFBFBF"),
    bottom=Side(style="thin", color="BFBFBF"),
)
_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
_left = Alignment(horizontal="left", vertical="center", wrap_text=True)


def _style_header_row(ws, row_idx: int, ncols: int) -> None:
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row_idx, column=c)
        cell.font = _header_font
        cell.fill = _header_fill
        cell.alignment = _center
        cell.border = _thin_border


def _score_fill(score: float | None):
    if score is None:
        return None
    if score < 0.6:
        return _low_fill
    if score < 0.8:
        return _mid_fill
    return _good_fill


def _fmt(v: Any) -> Any:
    """None → '-'，float 保留 4 位。"""
    if v is None:
        return "-"
    if isinstance(v, float):
        return round(v, 4)
    return v


# ---------- 主入口 ----------

def export_eval_run_xlsx(db: Session, eval_run_id: int) -> bytes:
    """生成 4-sheet Excel report 字节流。

    Raises:
        ValueError: run 不存在
    """
    run = db.get(EvalRun, eval_run_id)
    if not run:
        raise ValueError(f"eval run {eval_run_id} not found")

    cases = (
        db.query(EvalCaseResult)
        .filter(EvalCaseResult.eval_run_id == eval_run_id)
        .all()
    )

    # 预拉关联实体
    dataset = db.get(Dataset, run.dataset_id) if run.dataset_id else None
    bot = db.get(BotVersion, run.bot_version_id) if run.bot_version_id else None
    judge = db.get(JudgeModel, run.judge_model_id) if run.judge_model_id else None

    # conversation_id → conversation_id_src 映射（用于会话明细可读化）
    conv_ids = [c.conversation_id for c in cases]
    conv_src_map: dict[int, str] = {}
    if conv_ids:
        for conv in db.query(Conversation).filter(Conversation.id.in_(conv_ids)).all():
            conv_src_map[conv.id] = conv.conversation_id_src

    dims_selected = run.dimensions_selected or DIM_CODES
    # 仅用 DIM_CODES 的全集做表头，但根据 dims_selected 决定哪些列有意义
    case_dicts = [
        {f"{code}_score": getattr(c, f"{code}_score") for code in DIM_CODES}
        for c in cases
    ]
    dim_summary = aggregate_dimension_summary(case_dicts, DIM_CODES)
    summary_by_code = {row["dimension_code"]: row for row in dim_summary}

    wb = Workbook()

    _build_sheet_overview(wb, run, dataset, bot, judge, len(cases), summary_by_code)
    _build_sheet_dim_summary(wb, summary_by_code)
    _build_sheet_case_detail(wb, cases, conv_src_map)
    _build_sheet_turn_detail(db, wb, cases, conv_src_map)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------- Sheet 1: 总览 ----------

def _build_sheet_overview(wb, run, dataset, bot, judge, case_count, summary_by_code) -> None:
    ws = wb.active
    ws.title = "总览"

    ws.merge_cells("A1:D1")
    ws["A1"] = "多轮对话评测报告 — 总览"
    ws["A1"].font = _title_font
    ws["A1"].fill = _title_fill
    ws["A1"].alignment = _center

    info_rows = [
        ("评测名称", run.name),
        ("描述", run.description or "-"),
        ("状态", run.status),
        ("创建时间", run.created_at.strftime("%Y-%m-%d %H:%M:%S") if run.created_at else "-"),
        ("开始时间", run.started_at.strftime("%Y-%m-%d %H:%M:%S") if run.started_at else "-"),
        ("结束时间", run.finished_at.strftime("%Y-%m-%d %H:%M:%S") if run.finished_at else "-"),
        ("Dataset", f"#{dataset.id} · {dataset.name}" if dataset else f"#{run.dataset_id}"),
        ("Bot 版本", f"#{bot.id} · {bot.name} ({bot.version_tag})" if bot else f"#{run.bot_version_id}"),
        ("Judge 模型", f"#{judge.id} · {judge.name} ({judge.provider}/{judge.model_id})" if judge else f"#{run.judge_model_id}"),
        ("采样数 / 总数", f"{run.sampling_count or '全量'} / {run.total}"),
        ("已完成", run.completed),
        ("失败", run.failed),
        ("加权总分", _fmt(run.weighted_score)),
        ("通过率", f"{run.pass_rate * 100:.1f}%" if run.pass_rate is not None else "-"),
    ]
    r = 3
    for label, val in info_rows:
        c1 = ws.cell(row=r, column=1, value=label)
        c1.font = Font(bold=True)
        c1.alignment = _left
        ws.cell(row=r, column=2, value=val).alignment = _left
        r += 1

    # 维度权重表
    r += 1
    headers = ["维度", "代码", "权重", "平均分", "加权贡献"]
    for c, h in enumerate(headers, start=1):
        ws.cell(row=r, column=c, value=h)
    _style_header_row(ws, r, len(headers))
    r += 1
    for code in DIM_CODES:
        name = DIMENSION_NAMES.get(code, code)
        weight = DEFAULT_DIMENSION_WEIGHTS.get(code, 0.0)
        avg = summary_by_code.get(code, {}).get("avg_score")
        contrib = round(avg * weight, 4) if avg is not None else None
        ws.cell(row=r, column=1, value=name).alignment = _left
        ws.cell(row=r, column=2, value=code).alignment = _center
        ws.cell(row=r, column=3, value=f"{int(weight * 100)}%").alignment = _center
        c_avg = ws.cell(row=r, column=4, value=_fmt(avg))
        c_avg.alignment = _center
        fill = _score_fill(avg)
        if fill:
            c_avg.fill = fill
            if avg is not None and avg < 0.6:
                c_avg.font = Font(name="微软雅黑", size=10, color="C00000", bold=True)
        ws.cell(row=r, column=5, value=_fmt(contrib)).alignment = _center
        for c in range(1, len(headers) + 1):
            ws.cell(row=r, column=c).border = _thin_border
            if ws.cell(row=r, column=c).font is None or ws.cell(row=r, column=c).font.color is None:
                ws.cell(row=r, column=c).font = _body_font
        r += 1

    for col, w in zip("ABCDE", [22, 14, 12, 14, 14]):
        ws.column_dimensions[col].width = w


# ---------- Sheet 2: 维度汇总 ----------

def _build_sheet_dim_summary(wb, summary_by_code) -> None:
    ws = wb.create_sheet("维度汇总")
    headers = ["维度", "代码", "权重", "样本数", "平均分", "最低分", "最高分", "通过率(>=0.6)"]
    for c, h in enumerate(headers, start=1):
        ws.cell(row=1, column=c, value=h)
    _style_header_row(ws, 1, len(headers))

    r = 2
    for code in DIM_CODES:
        name = DIMENSION_NAMES.get(code, code)
        weight = DEFAULT_DIMENSION_WEIGHTS.get(code, 0.0)
        row = summary_by_code.get(code, {})
        avg = row.get("avg_score")
        pass_r = row.get("pass_rate")

        ws.cell(row=r, column=1, value=name).alignment = _left
        ws.cell(row=r, column=2, value=code).alignment = _center
        ws.cell(row=r, column=3, value=f"{int(weight * 100)}%").alignment = _center
        ws.cell(row=r, column=4, value=row.get("sample_count", 0)).alignment = _center
        c_avg = ws.cell(row=r, column=5, value=_fmt(avg))
        c_avg.alignment = _center
        fill = _score_fill(avg)
        if fill:
            c_avg.fill = fill
        if avg is not None and avg < 0.6:
            c_avg.font = Font(name="微软雅黑", size=10, color="C00000", bold=True)
        ws.cell(row=r, column=6, value=_fmt(row.get("min_score"))).alignment = _center
        ws.cell(row=r, column=7, value=_fmt(row.get("max_score"))).alignment = _center
        ws.cell(
            row=r,
            column=8,
            value=f"{pass_r * 100:.1f}%" if pass_r is not None else "-",
        ).alignment = _center

        for c in range(1, len(headers) + 1):
            ws.cell(row=r, column=c).border = _thin_border
            if c != 5 or avg is None or avg >= 0.6:
                ws.cell(row=r, column=c).font = _body_font
        r += 1

    for i, w in enumerate([20, 10, 10, 10, 12, 12, 12, 18], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


# ---------- Sheet 3: 会话明细 ----------

def _build_sheet_case_detail(wb, cases, conv_src_map) -> None:
    ws = wb.create_sheet("会话明细")
    headers = (
        ["case_id", "会话ID", "源会话ID", "加权得分"]
        + [DIMENSION_NAMES.get(code, code) for code in DIM_CODES]
        + ["最低维度", "最低分", "错误"]
    )
    for c, h in enumerate(headers, start=1):
        ws.cell(row=1, column=c, value=h)
    _style_header_row(ws, 1, len(headers))

    r = 2
    # 按加权得分升序，低分在前
    sorted_cases = sorted(
        cases,
        key=lambda c: (c.weighted_score is None, c.weighted_score if c.weighted_score is not None else 0),
    )
    for case in sorted_cases:
        ws.cell(row=r, column=1, value=case.id).alignment = _center
        ws.cell(row=r, column=2, value=case.conversation_id).alignment = _center
        ws.cell(row=r, column=3, value=conv_src_map.get(case.conversation_id, "-")).alignment = _center

        c_w = ws.cell(row=r, column=4, value=_fmt(case.weighted_score))
        c_w.alignment = _center
        fill = _score_fill(case.weighted_score)
        if fill:
            c_w.fill = fill

        dim_scores = {code: getattr(case, f"{code}_score") for code in DIM_CODES}
        for j, code in enumerate(DIM_CODES):
            v = dim_scores[code]
            cell = ws.cell(row=r, column=5 + j, value=_fmt(v))
            cell.alignment = _center
            cf = _score_fill(v)
            if cf:
                cell.fill = cf
            if v is not None and v < 0.6:
                cell.font = Font(name="微软雅黑", size=10, color="C00000", bold=True)

        valid_dims = {k: v for k, v in dim_scores.items() if v is not None}
        if valid_dims:
            min_code = min(valid_dims, key=lambda k: valid_dims[k])
            ws.cell(row=r, column=5 + len(DIM_CODES), value=DIMENSION_NAMES.get(min_code, min_code)).alignment = _center
            ws.cell(row=r, column=6 + len(DIM_CODES), value=round(valid_dims[min_code], 4)).alignment = _center
        else:
            ws.cell(row=r, column=5 + len(DIM_CODES), value="-").alignment = _center
            ws.cell(row=r, column=6 + len(DIM_CODES), value="-").alignment = _center

        ws.cell(row=r, column=7 + len(DIM_CODES), value=(case.error or "-")[:200]).alignment = _left

        for c in range(1, len(headers) + 1):
            ws.cell(row=r, column=c).border = _thin_border
            if ws.cell(row=r, column=c).font is None or not getattr(ws.cell(row=r, column=c).font, "color", None):
                ws.cell(row=r, column=c).font = _body_font
        r += 1

    ws.freeze_panes = "E2"
    ws.column_dimensions["A"].width = 10
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 20
    ws.column_dimensions["D"].width = 12
    for i in range(5, 5 + len(DIM_CODES)):
        ws.column_dimensions[get_column_letter(i)].width = 16
    ws.column_dimensions[get_column_letter(5 + len(DIM_CODES))].width = 18
    ws.column_dimensions[get_column_letter(6 + len(DIM_CODES))].width = 12
    ws.column_dimensions[get_column_letter(7 + len(DIM_CODES))].width = 40


# ---------- Sheet 4: 轮次明细 ----------

def _build_sheet_turn_detail(db: Session, wb, cases, conv_src_map) -> None:
    ws = wb.create_sheet("轮次明细")
    headers = ["case_id", "源会话ID", "维度", "轮次", "得分", "适用", "说明/原始返回片段"]
    for c, h in enumerate(headers, start=1):
        ws.cell(row=1, column=c, value=h)
    _style_header_row(ws, 1, len(headers))

    r = 2
    if not cases:
        ws.freeze_panes = "A2"
        return

    case_ids = [c.id for c in cases]
    case_by_id = {c.id: c for c in cases}

    # 一次性拉所有 turn_result
    turns = (
        db.query(EvalTurnResult)
        .filter(EvalTurnResult.eval_case_result_id.in_(case_ids))
        .order_by(
            EvalTurnResult.eval_case_result_id.asc(),
            EvalTurnResult.dimension_code.asc(),
            EvalTurnResult.turn_index.asc(),
        )
        .all()
    )

    # 用于反推没有 turn_results 的 case 走 dim_results_full
    cases_with_turns: set[int] = set()

    for t in turns:
        case = case_by_id.get(t.eval_case_result_id)
        if not case:
            continue
        cases_with_turns.add(case.id)
        raw = t.judge_raw_response or {}
        explanation = (
            raw.get("explanation")
            or raw.get("issue")
            or raw.get("note")
            or raw.get("error")
            or ""
        )
        if not explanation and isinstance(raw, dict):
            # 兜底取个简单 dump
            explanation = str(raw)[:300]

        ws.cell(row=r, column=1, value=case.id).alignment = _center
        ws.cell(row=r, column=2, value=conv_src_map.get(case.conversation_id, "-")).alignment = _center
        ws.cell(
            row=r,
            column=3,
            value=DIMENSION_NAMES.get(t.dimension_code, t.dimension_code),
        ).alignment = _center
        ws.cell(row=r, column=4, value=t.turn_index).alignment = _center

        sc = ws.cell(row=r, column=5, value=_fmt(t.score))
        sc.alignment = _center
        cf = _score_fill(t.score)
        if cf:
            sc.fill = cf

        ws.cell(
            row=r,
            column=6,
            value=("是" if t.applicable else "否") if t.applicable is not None else "-",
        ).alignment = _center
        ws.cell(row=r, column=7, value=str(explanation)[:300]).alignment = _left

        for c in range(1, len(headers) + 1):
            ws.cell(row=r, column=c).border = _thin_border
            ws.cell(row=r, column=c).font = _body_font
        r += 1

    # 对没有 turn_results 但有 dim_results_full 的 case 反推
    for case in cases:
        if case.id in cases_with_turns:
            continue
        full = case.dim_results_full or {}
        if not isinstance(full, dict):
            continue
        for code in DIM_CODES:
            dim_data = full.get(code)
            if not dim_data:
                continue
            if isinstance(dim_data, dict):
                # 形如 {"score": 0.8, "applicable": true, "explanation": "..."} 的会话级维度
                score = dim_data.get("score")
                applicable = dim_data.get("applicable")
                explanation = (
                    dim_data.get("explanation")
                    or dim_data.get("note")
                    or dim_data.get("error")
                    or ""
                )
                ws.cell(row=r, column=1, value=case.id).alignment = _center
                ws.cell(row=r, column=2, value=conv_src_map.get(case.conversation_id, "-")).alignment = _center
                ws.cell(row=r, column=3, value=DIMENSION_NAMES.get(code, code)).alignment = _center
                ws.cell(row=r, column=4, value="会话级").alignment = _center
                sc = ws.cell(row=r, column=5, value=_fmt(score))
                sc.alignment = _center
                cf = _score_fill(score)
                if cf:
                    sc.fill = cf
                ws.cell(
                    row=r,
                    column=6,
                    value=("是" if applicable else "否") if applicable is not None else "-",
                ).alignment = _center
                ws.cell(row=r, column=7, value=str(explanation)[:300]).alignment = _left
                for c in range(1, len(headers) + 1):
                    ws.cell(row=r, column=c).border = _thin_border
                    ws.cell(row=r, column=c).font = _body_font
                r += 1

    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 10
    ws.column_dimensions["B"].width = 20
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 10
    ws.column_dimensions["E"].width = 10
    ws.column_dimensions["F"].width = 8
    ws.column_dimensions["G"].width = 60


# ============================================================================
# Markdown export (C.1)
# ============================================================================


def _md_pct(v: float | None) -> str:
    return f"{v * 100:.1f}%" if v is not None else "-"


def _md_num(v: Any, digits: int = 4) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{round(v, digits)}"
    return str(v)


def _md_escape(s: str | None) -> str:
    """转义 Markdown 表格中破坏排版的字符（| 与换行）。"""
    if s is None:
        return "-"
    return str(s).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def export_eval_run_md(db: Session, eval_run_id: int) -> bytes:
    """Markdown 4-section report，UTF-8 编码字节流。

    Section: 标题/元信息 → 维度汇总表 → 会话明细表（低分前若干）→ 低分前 5 case 备注
    """
    run = db.get(EvalRun, eval_run_id)
    if not run:
        raise ValueError(f"eval run {eval_run_id} not found")

    cases = (
        db.query(EvalCaseResult)
        .filter(EvalCaseResult.eval_run_id == eval_run_id)
        .all()
    )
    dataset = db.get(Dataset, run.dataset_id) if run.dataset_id else None
    bot = db.get(BotVersion, run.bot_version_id) if run.bot_version_id else None
    judge = db.get(JudgeModel, run.judge_model_id) if run.judge_model_id else None

    conv_ids = [c.conversation_id for c in cases]
    conv_src_map: dict[int, str] = {}
    if conv_ids:
        for conv in db.query(Conversation).filter(Conversation.id.in_(conv_ids)).all():
            conv_src_map[conv.id] = conv.conversation_id_src

    case_dicts = [
        {f"{code}_score": getattr(c, f"{code}_score") for code in DIM_CODES}
        for c in cases
    ]
    dim_summary = aggregate_dimension_summary(case_dicts, DIM_CODES)
    summary_by_code = {row["dimension_code"]: row for row in dim_summary}

    lines: list[str] = []

    # ---- Section 1: 标题 + 元信息 ----
    lines.append(f"# 多轮对话评测报告 — {run.name}")
    lines.append("")
    lines.append(f"> Run ID: `#{run.id}` · 状态：**{run.status}**")
    lines.append("")
    if run.description:
        lines.append(f"{run.description}")
        lines.append("")

    lines.append("## 1. 评测元信息")
    lines.append("")
    info_rows = [
        ("评测名称", run.name),
        ("状态", run.status),
        (
            "创建时间",
            run.created_at.strftime("%Y-%m-%d %H:%M:%S") if run.created_at else "-",
        ),
        (
            "开始时间",
            run.started_at.strftime("%Y-%m-%d %H:%M:%S") if run.started_at else "-",
        ),
        (
            "结束时间",
            run.finished_at.strftime("%Y-%m-%d %H:%M:%S") if run.finished_at else "-",
        ),
        ("Dataset", f"#{dataset.id} · {dataset.name}" if dataset else f"#{run.dataset_id}"),
        (
            "Bot 版本",
            f"#{bot.id} · {bot.name} ({bot.version_tag})" if bot else f"#{run.bot_version_id}",
        ),
        (
            "Judge 模型",
            f"#{judge.id} · {judge.name} ({judge.provider}/{judge.model_id})"
            if judge
            else f"#{run.judge_model_id}",
        ),
        ("采样数 / 总数", f"{run.sampling_count or '全量'} / {run.total}"),
        ("已完成 / 失败", f"{run.completed} / {run.failed}"),
        ("加权总分", _md_num(run.weighted_score)),
        ("通过率", _md_pct(run.pass_rate)),
    ]
    lines.append("| 字段 | 值 |")
    lines.append("|------|------|")
    for k, v in info_rows:
        lines.append(f"| {_md_escape(k)} | {_md_escape(v)} |")
    lines.append("")

    # ---- Section 2: 维度汇总 ----
    lines.append("## 2. 维度汇总")
    lines.append("")
    lines.append("| 维度 | 代码 | 权重 | 样本数 | 平均分 | 最低分 | 最高分 | 通过率(≥0.6) |")
    lines.append("|------|------|------|------:|------:|------:|------:|------:|")
    for code in DIM_CODES:
        name = DIMENSION_NAMES.get(code, code)
        weight = DEFAULT_DIMENSION_WEIGHTS.get(code, 0.0)
        row = summary_by_code.get(code, {})
        lines.append(
            "| {name} | `{code}` | {weight} | {n} | {avg} | {mn} | {mx} | {pr} |".format(
                name=_md_escape(name),
                code=code,
                weight=f"{int(weight * 100)}%",
                n=row.get("sample_count", 0),
                avg=_md_num(row.get("avg_score")),
                mn=_md_num(row.get("min_score")),
                mx=_md_num(row.get("max_score")),
                pr=_md_pct(row.get("pass_rate")),
            )
        )
    lines.append("")

    # ---- Section 3: 会话明细（按加权分升序）----
    lines.append("## 3. 会话明细")
    lines.append("")
    sorted_cases = sorted(
        cases,
        key=lambda c: (
            c.weighted_score is None,
            c.weighted_score if c.weighted_score is not None else 0,
        ),
    )
    header = (
        "| case_id | 源会话ID | 加权得分 | "
        + " | ".join(DIMENSION_NAMES.get(code, code) for code in DIM_CODES)
        + " | 最低维度 |"
    )
    sep = "|------:|------|------:|" + ":------:|" * len(DIM_CODES) + "------|"
    lines.append(header)
    lines.append(sep)
    for case in sorted_cases:
        dim_scores = {code: getattr(case, f"{code}_score") for code in DIM_CODES}
        valid = {k: v for k, v in dim_scores.items() if v is not None}
        if valid:
            min_code = min(valid, key=lambda k: valid[k])
            min_label = f"{DIMENSION_NAMES.get(min_code, min_code)} ({_md_num(valid[min_code])})"
        else:
            min_label = "-"
        lines.append(
            "| {cid} | {src} | {w} | {dims} | {minlbl} |".format(
                cid=case.id,
                src=_md_escape(conv_src_map.get(case.conversation_id, f"#{case.conversation_id}")),
                w=_md_num(case.weighted_score),
                dims=" | ".join(_md_num(dim_scores[c]) for c in DIM_CODES),
                minlbl=_md_escape(min_label),
            )
        )
    lines.append("")

    # ---- Section 4: 低分前 5 备注 ----
    lines.append("## 4. 低分 Top-5 备注")
    lines.append("")
    low5 = [c for c in sorted_cases if c.weighted_score is not None][:5]
    if not low5:
        lines.append("_无可用低分样本（所有 case 加权得分均为空）_")
        lines.append("")
    else:
        for c in low5:
            src = conv_src_map.get(c.conversation_id, f"#{c.conversation_id}")
            lines.append(
                f"### case #{c.id} · 源会话 `{src}` · 加权 {_md_num(c.weighted_score)}"
            )
            lines.append("")
            for code in DIM_CODES:
                v = getattr(c, f"{code}_score")
                if v is None:
                    continue
                lines.append(f"- **{DIMENSION_NAMES.get(code, code)}** (`{code}`): {_md_num(v)}")
            note_src = c.error or ""
            if note_src:
                lines.append("")
                note_text = str(note_src)[:300]
                lines.append(f"> 错误：{note_text}")
            lines.append("")

    md_text = "\n".join(lines)
    return md_text.encode("utf-8")


# ============================================================================
# PDF export (C.1) — fpdf2 with latin-1 fallback for CJK
# ============================================================================


def _safe_pdf_text(s: Any) -> str:
    """将任意字符串转为 latin-1 安全的形式（CJK → '?'）。

    fpdf2 默认字体（helvetica）仅支持 latin-1。完整中文请走 MD/XLSX 版本。
    """
    if s is None:
        return "-"
    return str(s).encode("latin-1", "replace").decode("latin-1")


def export_eval_run_pdf(db: Session, eval_run_id: int) -> bytes:
    """生成简易 PDF 报告。非 latin-1 字符（中文等）会被替换为 '?'。"""
    from fpdf import FPDF

    run = db.get(EvalRun, eval_run_id)
    if not run:
        raise ValueError(f"eval run {eval_run_id} not found")

    cases = (
        db.query(EvalCaseResult)
        .filter(EvalCaseResult.eval_run_id == eval_run_id)
        .all()
    )
    dataset = db.get(Dataset, run.dataset_id) if run.dataset_id else None
    bot = db.get(BotVersion, run.bot_version_id) if run.bot_version_id else None
    judge = db.get(JudgeModel, run.judge_model_id) if run.judge_model_id else None

    case_dicts = [
        {f"{code}_score": getattr(c, f"{code}_score") for code in DIM_CODES}
        for c in cases
    ]
    dim_summary = aggregate_dimension_summary(case_dicts, DIM_CODES)
    summary_by_code = {row["dimension_code"]: row for row in dim_summary}

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # ---- Disclaimer / Title ----
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(
        0,
        9,
        _safe_pdf_text(f"Eval Run Report #{run.id}: {run.name}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_font("helvetica", "I", 8)
    pdf.set_text_color(150, 60, 60)
    pdf.cell(
        0,
        5,
        "Note: non-Latin chars (e.g. Chinese) are replaced with '?'. "
        "For full CJK content, use the MD or XLSX export.",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    # ---- Meta block ----
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 6, "1. Run Metadata", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 9)
    meta_rows = [
        ("Status", run.status),
        ("Created", run.created_at.strftime("%Y-%m-%d %H:%M:%S") if run.created_at else "-"),
        ("Started", run.started_at.strftime("%Y-%m-%d %H:%M:%S") if run.started_at else "-"),
        ("Finished", run.finished_at.strftime("%Y-%m-%d %H:%M:%S") if run.finished_at else "-"),
        ("Dataset", f"#{dataset.id} {dataset.name}" if dataset else f"#{run.dataset_id}"),
        (
            "Bot",
            f"#{bot.id} {bot.name} ({bot.version_tag})" if bot else f"#{run.bot_version_id}",
        ),
        (
            "Judge",
            f"#{judge.id} {judge.name} ({judge.provider}/{judge.model_id})"
            if judge
            else f"#{run.judge_model_id}",
        ),
        ("Sampled/Total", f"{run.sampling_count or 'all'} / {run.total}"),
        ("Completed/Failed", f"{run.completed} / {run.failed}"),
        (
            "Weighted Score",
            f"{round(run.weighted_score, 4)}" if run.weighted_score is not None else "-",
        ),
        (
            "Pass Rate",
            f"{run.pass_rate * 100:.1f}%" if run.pass_rate is not None else "-",
        ),
    ]
    for k, v in meta_rows:
        pdf.cell(45, 5, _safe_pdf_text(k))
        pdf.cell(0, 5, _safe_pdf_text(v), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # ---- Dimension summary table ----
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 6, "2. Dimension Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "B", 8)
    col_w = [38, 14, 13, 14, 16, 16, 16, 18]
    headers = ["Dimension", "Code", "Weight", "N", "Avg", "Min", "Max", "Pass>=0.6"]
    for w, h in zip(col_w, headers):
        pdf.cell(w, 6, _safe_pdf_text(h), border=1, align="C")
    pdf.ln()

    pdf.set_font("helvetica", "", 8)
    for code in DIM_CODES:
        name = DIMENSION_NAMES.get(code, code)
        weight = DEFAULT_DIMENSION_WEIGHTS.get(code, 0.0)
        row = summary_by_code.get(code, {})
        avg = row.get("avg_score")
        mn = row.get("min_score")
        mx = row.get("max_score")
        pr = row.get("pass_rate")
        n = row.get("sample_count", 0)
        cells = [
            name,
            code,
            f"{int(weight * 100)}%",
            str(n),
            f"{round(avg, 4)}" if avg is not None else "-",
            f"{round(mn, 4)}" if mn is not None else "-",
            f"{round(mx, 4)}" if mx is not None else "-",
            f"{pr * 100:.1f}%" if pr is not None else "-",
        ]
        for w, val in zip(col_w, cells):
            pdf.cell(w, 5, _safe_pdf_text(val), border=1, align="C")
        pdf.ln()
    pdf.ln(3)

    # ---- Low 5 cases ----
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 6, "3. Lowest 5 Cases", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 8)
    low5 = sorted(
        [c for c in cases if c.weighted_score is not None],
        key=lambda c: c.weighted_score,
    )[:5]
    if not low5:
        pdf.cell(0, 5, "(no scored cases)", new_x="LMARGIN", new_y="NEXT")
    else:
        cell_w = [16, 22, 18, 18, 18, 18, 18, 18, 18]
        head = ["case_id", "weighted", "dim1", "dim2", "dim3", "dim4", "dim5", "dim6", "lowest"]
        pdf.set_font("helvetica", "B", 8)
        for w, h in zip(cell_w, head):
            pdf.cell(w, 5, _safe_pdf_text(h), border=1, align="C")
        pdf.ln()
        pdf.set_font("helvetica", "", 8)
        for c in low5:
            cells = [
                str(c.id),
                f"{round(c.weighted_score, 4)}",
            ]
            for code in DIM_CODES:
                v = getattr(c, f"{code}_score")
                cells.append(f"{round(v, 3)}" if v is not None else "-")
            cells.append(c.lowest_dim_code or "-")
            for w, val in zip(cell_w, cells):
                pdf.cell(w, 5, _safe_pdf_text(val), border=1, align="C")
            pdf.ln()

    out = pdf.output()
    # fpdf2 >=2.7 returns bytearray
    return bytes(out)
