import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import DIMENSION_NAMES
from app.core.db import get_db
from app.models import Conversation, EvalCaseResult, EvalRun
from app.schemas.eval_run import (
    DimensionSummary,
    EvalRunCreate,
    EvalRunDashboard,
    EvalRunOut,
)
from app.services.exporter import export_eval_run_xlsx
from app.services.scoring import aggregate_dimension_summary

router = APIRouter(prefix="/api/eval-runs", tags=["eval-runs"])


@router.get("", response_model=list[EvalRunOut])
def list_runs(db: Session = Depends(get_db)):
    return db.query(EvalRun).order_by(EvalRun.created_at.desc()).all()


@router.post("", response_model=EvalRunOut)
def create_run(payload: EvalRunCreate, db: Session = Depends(get_db)):
    total = db.query(Conversation).filter(Conversation.dataset_id == payload.dataset_id).count()
    if payload.sampling_count and payload.sampling_count < total:
        total = payload.sampling_count
    run = EvalRun(
        **payload.model_dump(),
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
    return EvalRunDashboard(run=run, dimension_summary=summary, score_distribution=buckets)


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


@router.get("/{run_id}/export")
def export_run(run_id: int, format: str = "xlsx", db: Session = Depends(get_db)):
    """导出评测报告。当前仅支持 xlsx（4-sheet）。"""
    if format != "xlsx":
        raise HTTPException(400, "only xlsx supported in W1.5")
    run = db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    if run.status not in ("success", "partial"):
        raise HTTPException(
            400,
            f"run status is '{run.status}', only success/partial runs can be exported",
        )
    try:
        content = export_eval_run_xlsx(db, run_id)
    except ValueError:
        raise HTTPException(404, "run not found")
    filename = f"eval_run_{run_id}.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
