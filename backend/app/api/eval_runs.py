import io
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_DIMENSION_WEIGHTS, DIMENSION_NAMES
from app.core.db import get_db
from app.models import (
    BadcaseTag,
    BotRewrite,
    Conversation,
    EvalCaseResult,
    EvalRun,
    EvalTurnResult,
    JudgePromptVersion,
    RegressionSet,
    RegressionSetItem,
    Turn,
)
from app.schemas.badcase import (
    BadcaseFacet,
    BadcaseListItem,
    BadcaseListResponse,
    BadcaseStats,
    BadcaseTagOut,
    CaseConversationMeta,
    CaseFullDetail,
    CaseFullTurn,
    CaseFullTurnResult,
)
from app.schemas.eval_run import (
    DimensionHistBucket,
    DimensionIssueCluster,
    DimensionPromptInfo,
    DimensionSliceResponse,
    DimensionStats,
    DimensionSummary,
    DimensionTopBadcase,
    EvalRunCreate,
    EvalRunDashboard,
    EvalRunOut,
)
from app.services.exporter import (
    export_eval_run_md,
    export_eval_run_pdf,
    export_eval_run_xlsx,
)
from app.services.scoring import PASS_THRESHOLD, aggregate_dimension_summary, bootstrap_ci
from app.services.dashboard import compute_cost_summary
from app.services.badcase import select_badcases

router = APIRouter(prefix="/api/eval-runs", tags=["eval-runs"])


@router.get("", response_model=list[EvalRunOut])
def list_runs(db: Session = Depends(get_db)):
    return db.query(EvalRun).order_by(EvalRun.created_at.desc()).all()


_VALID_DIM_CODES = {"dim1", "dim2", "dim3", "dim4", "dim5", "dim6"}


def _validate_dimension_weights(
    weights: dict[str, float] | None,
    dimensions_selected: list[str],
) -> dict[str, float] | None:
    """校验 dimension_weights：
    - None → 不指定，scoring fallback DEFAULT
    - 键必须 ⊆ dim1..dim6
    - 值必须 ≥ 0
    - 所有"已选维度"必须出现且至少一个 >0（否则 weighted_score 永远是 None）

    返回规范化后的 dict（删去未选维度的多余 key）。
    """
    if weights is None:
        return None
    cleaned: dict[str, float] = {}
    for k, v in weights.items():
        if k not in _VALID_DIM_CODES:
            raise HTTPException(400, f"invalid dimension code in weights: {k!r}")
        if v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, f"weight for {k!r} not numeric: {v!r}") from exc
        if fv < 0:
            raise HTTPException(400, f"weight for {k!r} must be >= 0, got {fv}")
        cleaned[k] = fv

    # 检查已选维度都有权重，且总和 > 0
    selected_total = sum(cleaned.get(d, 0.0) for d in dimensions_selected)
    if selected_total <= 0:
        raise HTTPException(
            400,
            "dimension_weights 在所有已选维度上的总和必须 > 0（否则 weighted_score 无意义）",
        )
    return cleaned


@router.post("", response_model=EvalRunOut)
def create_run(payload: EvalRunCreate, db: Session = Depends(get_db)):
    # 校验 dimension_weights（None 留空走默认；否则强校验）
    cleaned_weights = _validate_dimension_weights(
        payload.dimension_weights, payload.dimensions_selected
    )
    # C.2：若指定回归集，total = 集合内 conversation 与 dataset 的交集大小
    if payload.regression_set_id is not None:
        rs = db.get(RegressionSet, payload.regression_set_id)
        if rs is None:
            raise HTTPException(400, f"regression_set id={payload.regression_set_id} 不存在")
        total = (
            db.query(RegressionSetItem)
            .join(Conversation, Conversation.id == RegressionSetItem.conversation_id)
            .filter(
                RegressionSetItem.regression_set_id == payload.regression_set_id,
                Conversation.dataset_id == payload.dataset_id,
            )
            .count()
        )
        # C.2 reviewer P1: 空交集 → 400（避免 task 静默 "success" with 0 cases）
        if total == 0:
            raise HTTPException(
                400,
                f"回归集 #{payload.regression_set_id} 与 dataset #{payload.dataset_id} 无交集 "
                "（集合内没有任何 conversation 属于此 dataset）；请改选其他 dataset 或往集合内添加 conversation",
            )
    else:
        total = (
            db.query(Conversation)
            .filter(Conversation.dataset_id == payload.dataset_id)
            .count()
        )
        if payload.sampling_count and payload.sampling_count < total:
            total = payload.sampling_count
    run_kwargs = payload.model_dump()
    run_kwargs["dimension_weights"] = cleaned_weights
    run = EvalRun(
        **run_kwargs,
        status="pending",
        total=total,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    # W1：先创建记录；Celery enqueue 由 tasks 模块在 main.py 启动时绑定。
    from app.tasks.eval_tasks import execute_eval_run

    execute_eval_run.delay(run.id)
    return run


@router.get("/{run_id}", response_model=EvalRunOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    obj = db.get(EvalRun, run_id)
    if not obj:
        raise HTTPException(404, "eval run not found")
    return obj


@router.get("/{run_id}/dashboard", response_model=EvalRunDashboard)
def get_dashboard(run_id: int, db: Session = Depends(get_db)):
    run = db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(404, "eval run not found")
    cases = (
        db.query(EvalCaseResult)
        .filter(EvalCaseResult.eval_run_id == run_id)
        .all()
    )
    case_dicts = [
        {
            f"dim{i}_score": getattr(c, f"dim{i}_score")
            for i in range(1, 7)
        }
        for c in cases
    ]
    summary_raw = aggregate_dimension_summary(case_dicts, run.dimensions_selected)
    summary = [
        DimensionSummary(
            **row,
            dimension_name=DIMENSION_NAMES.get(row["dimension_code"], row["dimension_code"]),
        )
        for row in summary_raw
    ]
    # 加权总分按 0.1 桶分布
    buckets = {f"{i/10:.1f}-{(i+1)/10:.1f}": 0 for i in range(10)}
    for c in cases:
        if c.weighted_score is None:
            continue
        b = min(int(c.weighted_score * 10), 9)
        buckets[f"{b/10:.1f}-{(b+1)/10:.1f}"] += 1
    cost_summary = compute_cost_summary(db, run_id, len(cases))
    return EvalRunDashboard(
        run=run,
        dimension_summary=summary,
        score_distribution=buckets,
        cost_summary=cost_summary,
    )


# cost summary 已下沉到 services/dashboard.py:compute_cost_summary


@router.post("/{run_id}/cancel")
def cancel_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(404, "eval run not found")
    if run.status in ("success", "failed", "cancelled"):
        return {"status": run.status, "message": "already terminal"}
    run.status = "cancelled"
    run.finished_at = datetime.utcnow()
    db.commit()
    return {"status": "cancelled"}


@router.post("/{run_id}/retry-failed")
def retry_failed(run_id: int, db: Session = Depends(get_db)):
    """C.3：重跑当前 run 中所有失败的 case（仅评失败 conv 子集）。

    流程：
    1. 找出该 run 中 error IS NOT NULL 的 case
    2. enqueue retry_failed_cases task —— 在 worker 中删除失败 case 并重跑
    """
    run = db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(404, "eval run not found")
    if run.status == "running":
        raise HTTPException(409, "run is currently running; cancel it first")

    failed_cases = (
        db.query(EvalCaseResult)
        .filter(
            EvalCaseResult.eval_run_id == run_id,
            EvalCaseResult.error.is_not(None),
        )
        .all()
    )
    if not failed_cases:
        return {"queued": 0, "message": "no failed cases to retry"}

    conv_ids = [c.conversation_id for c in failed_cases]

    from app.tasks.eval_tasks import retry_failed_cases as retry_task

    retry_task.delay(run_id, conv_ids)
    return {
        "queued": len(conv_ids),
        "conversation_ids": conv_ids,
        "message": f"retry enqueued for {len(conv_ids)} failed cases",
    }


@router.get("/{run_id}/cases")
def list_cases(
    run_id: int,
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
    min_score: float | None = None,
    max_score: float | None = None,
    sort_by: str = "weighted_score",
):
    q = db.query(EvalCaseResult).filter(EvalCaseResult.eval_run_id == run_id)
    if min_score is not None:
        q = q.filter(EvalCaseResult.weighted_score >= min_score)
    if max_score is not None:
        q = q.filter(EvalCaseResult.weighted_score <= max_score)
    if sort_by == "weighted_score":
        q = q.order_by(EvalCaseResult.weighted_score.asc())
    total = q.count()
    rows = q.offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": r.id,
                "conversation_id": r.conversation_id,
                "weighted_score": r.weighted_score,
                "lowest_dim_code": r.lowest_dim_code,
                "dim_scores": {f"dim{i}": getattr(r, f"dim{i}_score") for i in range(1, 7)},
            }
            for r in rows
        ],
    }


@router.get("/{run_id}/sessions")
def list_sessions(
    run_id: int,
    db: Session = Depends(get_db),
    sort_by: str = "weighted_score",
    sort_dir: str = "asc",
    q: str = "",
    limit: int = 1000,
    offset: int = 0,
):
    """P0-4：返回 run 内全部 session 的概览（meta_id + total_turns + 各维度分 + 加权）。

    与 /cases 的区别：
    - join Conversation 取出 conversation_id_src（即 meta_id）和 total_turns
    - 支持按任意维度 / 加权分 升降序
    - 支持 meta_id 子串模糊搜索
    - 默认返回全量（limit=1000），方便前端做客户端二次过滤
    """
    valid_sort = {
        "weighted_score": EvalCaseResult.weighted_score,
        "dim1_score": EvalCaseResult.dim1_score,
        "dim2_score": EvalCaseResult.dim2_score,
        "dim3_score": EvalCaseResult.dim3_score,
        "dim4_score": EvalCaseResult.dim4_score,
        "dim5_score": EvalCaseResult.dim5_score,
        "dim6_score": EvalCaseResult.dim6_score,
        "total_turns": Conversation.total_turns,
        "meta_id": Conversation.conversation_id_src,
    }
    sort_col = valid_sort.get(sort_by, EvalCaseResult.weighted_score)
    sort_col = sort_col.asc() if sort_dir == "asc" else sort_col.desc()

    base = (
        db.query(EvalCaseResult, Conversation)
        .join(Conversation, Conversation.id == EvalCaseResult.conversation_id)
        .filter(EvalCaseResult.eval_run_id == run_id)
    )
    if q.strip():
        base = base.filter(Conversation.conversation_id_src.ilike(f"%{q.strip()}%"))
    total = base.count()
    rows = base.order_by(sort_col).offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "case_id": r.id,
                "conversation_id": r.conversation_id,
                "meta_id": c.conversation_id_src,
                "total_turns": c.total_turns,
                "weighted_score": r.weighted_score,
                "lowest_dim_code": r.lowest_dim_code,
                "dim_scores": {
                    f"dim{i}": getattr(r, f"dim{i}_score") for i in range(1, 7)
                },
                "error": r.error,
            }
            for r, c in rows
        ],
    }


@router.get("/{run_id}/cases/{case_id}")
def get_case(run_id: int, case_id: int, db: Session = Depends(get_db)):
    case = (
        db.query(EvalCaseResult)
        .filter(EvalCaseResult.eval_run_id == run_id, EvalCaseResult.id == case_id)
        .first()
    )
    if not case:
        raise HTTPException(404, "case not found")
    conv = db.get(Conversation, case.conversation_id)
    return {
        "id": case.id,
        "conversation_id": case.conversation_id,
        "conversation_id_src": conv.conversation_id_src if conv else None,
        "weighted_score": case.weighted_score,
        "lowest_dim_code": case.lowest_dim_code,
        "dim_scores": {f"dim{i}": getattr(case, f"dim{i}_score") for i in range(1, 7)},
        "dim_results_full": case.dim_results_full,
        "turn_results": [
            {
                "turn_index": t.turn_index,
                "dimension_code": t.dimension_code,
                "score": t.score,
                "applicable": t.applicable,
                "judge_raw_response": t.judge_raw_response,
            }
            for t in case.turn_results
        ],
    }


# ====================================================================
# B.1 Badcase 钻取（plan §8 B 周 / §9.B.9）
# ====================================================================


_VALID_DIMS = {"dim1", "dim2", "dim3", "dim4", "dim5", "dim6"}


@router.get("/{run_id}/badcases", response_model=BadcaseListResponse)
def list_badcases(
    run_id: int,
    db: Session = Depends(get_db),
    dim_filter: str | None = Query(default=None, description="dim1..dim6 / None"),
    score_max: float = Query(default=PASS_THRESHOLD, ge=0.0, le=1.0),
    tag_filter: str | None = None,
    confirmed: bool | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """列出 badcase（按 dim 或加权总分过滤），含 tag facet 与统计。

    业务逻辑（filter / sort / facet / stats）在 services/badcase.py:select_badcases；
    本 router 只做参数校验、加载、schema 构造。
    """
    run = db.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(404, f"eval_run id={run_id} 不存在")
    if dim_filter is not None and dim_filter not in _VALID_DIMS:
        raise HTTPException(400, f"dim_filter='{dim_filter}' 必须为 dim1..dim6 或 None")

    # 拉该 run 全部 case + tag（一次性，service 在内存做筛选/排序/分页）
    all_cases = (
        db.query(EvalCaseResult)
        .filter(EvalCaseResult.eval_run_id == run_id)
        .all()
    )
    case_ids = [c.id for c in all_cases]
    tags_by_case: dict[int, list[BadcaseTag]] = defaultdict(list)
    if case_ids:
        for t in (
            db.query(BadcaseTag)
            .filter(BadcaseTag.eval_case_result_id.in_(case_ids))
            .order_by(BadcaseTag.created_at.desc())
            .all()
        ):
            tags_by_case[t.eval_case_result_id].append(t)

    sel = select_badcases(
        all_cases=all_cases,
        tags_by_case=tags_by_case,
        dim_filter=dim_filter,
        score_max=score_max,
        tag_filter=tag_filter,
        confirmed=confirmed,
        limit=limit,
        offset=offset,
    )
    stats = BadcaseStats(
        total_cases=sel.total_cases,
        below_threshold=sel.below_threshold,
        tagged=sel.tagged_count,
        confirmed=sel.confirmed_count,
    )
    tag_facets = [BadcaseFacet(tag=t, count=c) for t, c in sel.tag_counts]
    page = sel.page
    total = sel.total_filtered

    # ---------- 拉本页所需 conversation + 首轮 turn ----------
    page_conv_ids = list({c.conversation_id for c in page})
    convs: dict[int, Conversation] = {}
    first_turn_by_conv: dict[int, Turn] = {}
    if page_conv_ids:
        for conv in (
            db.query(Conversation).filter(Conversation.id.in_(page_conv_ids)).all()
        ):
            convs[conv.id] = conv
        for t in (
            db.query(Turn)
            .filter(Turn.conversation_id.in_(page_conv_ids), Turn.turn_index == 1)
            .all()
        ):
            first_turn_by_conv[t.conversation_id] = t
        # 兜底：若没有 turn_index==1，取 min(turn_index)
        if len(first_turn_by_conv) < len(page_conv_ids):
            missing = [cid for cid in page_conv_ids if cid not in first_turn_by_conv]
            for t in (
                db.query(Turn)
                .filter(Turn.conversation_id.in_(missing))
                .order_by(Turn.conversation_id.asc(), Turn.turn_index.asc())
                .all()
            ):
                if t.conversation_id not in first_turn_by_conv:
                    first_turn_by_conv[t.conversation_id] = t

    items: list[BadcaseListItem] = []
    for c in page:
        conv = convs.get(c.conversation_id)
        first_turn = first_turn_by_conv.get(c.conversation_id)
        preview = (first_turn.user_query if first_turn else "") or ""
        if len(preview) > 60:
            preview = preview[:60] + "…"
        items.append(
            BadcaseListItem(
                case_id=c.id,
                conversation_id=c.conversation_id,
                conversation_id_src=conv.conversation_id_src if conv else f"#{c.conversation_id}",
                weighted_score=c.weighted_score,
                lowest_dim_code=c.lowest_dim_code,
                dim_scores={f"dim{i}": getattr(c, f"dim{i}_score") for i in range(1, 7)},
                tags=[BadcaseTagOut.model_validate(t) for t in tags_by_case.get(c.id, [])],
                preview_query=preview,
            )
        )

    return BadcaseListResponse(
        total=total,
        items=items,
        tag_facets=tag_facets,
        stats=stats,
    )


@router.get("/{run_id}/cases/{case_id}/full", response_model=CaseFullDetail)
def get_case_full(run_id: int, case_id: int, db: Session = Depends(get_db)):
    """单 case 的完整钻取：含 conv turns + bot rewrites + dim_results_full + turn_results + tags。"""
    case = (
        db.query(EvalCaseResult)
        .filter(EvalCaseResult.eval_run_id == run_id, EvalCaseResult.id == case_id)
        .first()
    )
    if case is None:
        raise HTTPException(404, "case not found")

    run = db.get(EvalRun, run_id)
    conv = db.get(Conversation, case.conversation_id)
    if conv is None:
        raise HTTPException(404, "conversation not found")

    # turns + rewrites
    turns = (
        db.query(Turn)
        .filter(Turn.conversation_id == conv.id)
        .order_by(Turn.turn_index.asc())
        .all()
    )
    turn_ids = [t.id for t in turns]
    rewrites_by_turn: dict[int, BotRewrite] = {}
    if turn_ids and run is not None:
        for r in (
            db.query(BotRewrite)
            .filter(
                BotRewrite.turn_id.in_(turn_ids),
                BotRewrite.bot_version_id == run.bot_version_id,
            )
            .all()
        ):
            rewrites_by_turn[r.turn_id] = r

    full_turns = [
        CaseFullTurn(
            turn_index=t.turn_index,
            user_query=t.user_query,
            rewritten_query=(rewrites_by_turn.get(t.id).rewritten_query if rewrites_by_turn.get(t.id) else None),
            timestamp=t.timestamp,
        )
        for t in turns
    ]

    # turn_results
    turn_results = [
        CaseFullTurnResult(
            turn_index=tr.turn_index,
            dimension_code=tr.dimension_code,
            score=tr.score,
            applicable=tr.applicable,
            judge_raw_response=tr.judge_raw_response,
        )
        for tr in sorted(
            case.turn_results,
            key=lambda x: (x.turn_index, x.dimension_code),
        )
    ]

    # tags
    tag_rows = (
        db.query(BadcaseTag)
        .filter(BadcaseTag.eval_case_result_id == case_id)
        .order_by(BadcaseTag.created_at.desc())
        .all()
    )

    return CaseFullDetail(
        case_id=case.id,
        conversation_id=case.conversation_id,
        conversation_id_src=conv.conversation_id_src,
        weighted_score=case.weighted_score,
        lowest_dim_code=case.lowest_dim_code,
        dim_scores={f"dim{i}": getattr(case, f"dim{i}_score") for i in range(1, 7)},
        turns=full_turns,
        dim_results_full=case.dim_results_full or {},
        turn_results=turn_results,
        tags=[BadcaseTagOut.model_validate(t) for t in tag_rows],
        conversation_meta=CaseConversationMeta(
            dimension_tag=conv.dimension_tag,
            quality_label=conv.quality_label,
            issue_type=conv.issue_type,
        ),
    )


@router.get("/{run_id}/export")
def export_run(run_id: int, format: str = "xlsx", db: Session = Depends(get_db)):
    """导出评测报告。支持 xlsx (4-sheet) / md (markdown) / pdf (latin-1 fallback)。"""
    if format not in ("xlsx", "md", "pdf"):
        raise HTTPException(400, "format must be xlsx / md / pdf")
    run = db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    if run.status not in ("success", "partial"):
        raise HTTPException(
            400,
            f"run status is '{run.status}', only success/partial runs can be exported",
        )
    try:
        if format == "xlsx":
            content = export_eval_run_xlsx(db, run_id)
            media_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            ext = "xlsx"
        elif format == "md":
            content = export_eval_run_md(db, run_id)
            media_type = "text/markdown; charset=utf-8"
            ext = "md"
        else:  # pdf
            content = export_eval_run_pdf(db, run_id)
            media_type = "application/pdf"
            ext = "pdf"
    except ValueError:
        raise HTTPException(404, "run not found")
    filename = f"eval_run_{run_id}.{ext}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers=headers,
    )


# ===========================================================================
# B.2  维度切片 — 单维详情
# ===========================================================================

_DIM_ISSUE_KEYWORDS = [
    "幻觉",
    "丢失",
    "未消解",
    "形态",
    "属性",
    "约束",
    "纠错",
    "重复",
    "遗漏",
    "误解",
]


def _extract_explanation(dim_payload) -> str:
    """从 dim_results_full[dim_code] 提取可读 explanation 文本。

    维度间结构不同：
      - dim1/3/4/5: {turn_scores: [{detail: {explanation: ...}}, ...]}
      - dim2/6:     {detail: {explanation: ...}}
    返回拼接后的 explanation 字符串（空则空串）。
    """
    if not isinstance(dim_payload, dict):
        return ""
    parts: list[str] = []
    # 顶层 detail（dim2/6）
    detail = dim_payload.get("detail")
    if isinstance(detail, dict):
        exp = detail.get("explanation")
        if isinstance(exp, str):
            parts.append(exp)
    # turn_scores（dim1/3/4/5）
    for ts in dim_payload.get("turn_scores") or []:
        if not isinstance(ts, dict):
            continue
        ts_detail = ts.get("detail")
        if isinstance(ts_detail, dict):
            exp = ts_detail.get("explanation")
            if isinstance(exp, str):
                parts.append(exp)
    return " | ".join(parts)


@router.get("/{run_id}/dimensions/{dim_code}", response_model=DimensionSliceResponse)
def get_dimension_slice(
    run_id: int,
    dim_code: str,
    db: Session = Depends(get_db),
):
    """单维度切片视图：直方图 / 触发率 / Top badcase / 问题归类。

    用于前端 6-tab 详情页（/eval-runs/{id}/dimensions?dim=...）。
    """
    if dim_code not in DIMENSION_NAMES:
        raise HTTPException(404, f"unknown dimension: {dim_code}")
    run = db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(404, "eval run not found")

    score_col = getattr(EvalCaseResult, f"{dim_code}_score")
    cases = (
        db.query(EvalCaseResult)
        .filter(EvalCaseResult.eval_run_id == run_id)
        .all()
    )
    total_cases = len(cases)

    # ---- prompt 版本与权重 ----
    prompt_version_id = (run.judge_prompt_version_ids or {}).get(dim_code)
    prompt_obj = None
    weight = DEFAULT_DIMENSION_WEIGHTS.get(dim_code, 0.0)
    if prompt_version_id:
        prompt_obj = db.get(JudgePromptVersion, prompt_version_id)
        if prompt_obj and prompt_obj.weight is not None:
            weight = prompt_obj.weight
    prompt_info = (
        DimensionPromptInfo(
            id=prompt_obj.id,
            version_tag=prompt_obj.version_tag,
            notes=prompt_obj.notes,
        )
        if prompt_obj is not None
        else None
    )

    # ---- 统计 + 直方图 ----
    buckets: dict[str, int] = {
        f"{i/10:.1f}-{(i+1)/10:.1f}": 0 for i in range(10)
    }
    scores: list[float] = []
    pass_count = 0
    for c in cases:
        s = getattr(c, f"{dim_code}_score")
        if s is None:
            continue
        scores.append(s)
        b = min(int(s * 10), 9)
        buckets[f"{b/10:.1f}-{(b+1)/10:.1f}"] += 1
        if s >= PASS_THRESHOLD:
            pass_count += 1

    applicable_count = len(scores)
    if applicable_count == 0:
        stats = DimensionStats(
            total_cases=total_cases,
            applicable_count=0,
            trigger_rate=(0.0 if total_cases else None),
            avg_score=None,
            min_score=None,
            max_score=None,
            pass_count=0,
            pass_rate=None,
            mean_ci_low=None,
            mean_ci_high=None,
        )
    else:
        ci_low, ci_high = bootstrap_ci(scores)
        stats = DimensionStats(
            total_cases=total_cases,
            applicable_count=applicable_count,
            trigger_rate=(round(applicable_count / total_cases, 4) if total_cases else None),
            avg_score=round(sum(scores) / applicable_count, 4),
            min_score=min(scores),
            max_score=max(scores),
            pass_count=pass_count,
            pass_rate=round(pass_count / applicable_count, 4),
            mean_ci_low=ci_low,
            mean_ci_high=ci_high,
        )

    histogram = [DimensionHistBucket(bucket=k, count=v) for k, v in buckets.items()]

    # ---- Top 5 Badcase（该维度分数最低）----
    top_q = (
        db.query(EvalCaseResult)
        .filter(
            EvalCaseResult.eval_run_id == run_id,
            score_col.is_not(None),
        )
        .order_by(score_col.asc())
        .limit(5)
        .all()
    )
    conv_ids = [r.conversation_id for r in top_q]
    convs = (
        {c.id: c for c in db.query(Conversation).filter(Conversation.id.in_(conv_ids)).all()}
        if conv_ids
        else {}
    )
    top_badcases: list[DimensionTopBadcase] = []
    for r in top_q:
        explanation = _extract_explanation(
            (r.dim_results_full or {}).get(dim_code, {})
        )
        if len(explanation) > 200:
            explanation = explanation[:200] + "…"
        conv = convs.get(r.conversation_id)
        top_badcases.append(
            DimensionTopBadcase(
                case_id=r.id,
                conversation_id_src=conv.conversation_id_src if conv else str(r.conversation_id),
                dim_score=getattr(r, f"{dim_code}_score"),
                weighted_score=r.weighted_score,
                explanation=explanation or None,
            )
        )

    # ---- Issue clusters（keyword 频次）----
    counter: dict[str, int] = defaultdict(int)
    for c in cases:
        if not c.dim_results_full:
            continue
        text = _extract_explanation(c.dim_results_full.get(dim_code, {}))
        if not text:
            continue
        for kw in _DIM_ISSUE_KEYWORDS:
            if kw in text:
                counter[kw] += 1
    clusters = sorted(
        [DimensionIssueCluster(key=k, count=v) for k, v in counter.items()],
        key=lambda x: -x.count,
    )[:5]

    return DimensionSliceResponse(
        dim_code=dim_code,
        dim_name=DIMENSION_NAMES[dim_code],
        weight=weight,
        prompt_version=prompt_info,
        stats=stats,
        histogram=histogram,
        top_badcases=top_badcases,
        issue_clusters=clusters,
    )
