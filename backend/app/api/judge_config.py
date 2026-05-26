import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import EvalCaseResult, EvalRun, JudgeModel, JudgePromptVersion
from app.schemas.judge import (
    JudgeModelCreate,
    JudgeModelOut,
    JudgeModelTestResult,
    JudgeModelUpdate,
    JudgePromptPerformance,
    JudgePromptPerformanceItem,
    JudgePromptVersionCreate,
    JudgePromptVersionDetail,
    JudgePromptVersionOut,
    JudgePromptVersionUpdate,
)
from app.services.eval_engine.judge_client import build_judge_client
from app.services.prompt_lifecycle import (
    TemplateValidationError,
    build_prompt_usage_map,
    count_prompt_in_use,
    next_version_tag,
    render_preview,
    runs_referencing_prompt,
    validate_jinja2_template,
)


router = APIRouter(prefix="/api/judge-config", tags=["judge-config"])


def _validate_template_or_400(tmpl: str) -> None:
    """薄封装：把 service 层的 TemplateValidationError 转 HTTP 400。"""
    try:
        validate_jinja2_template(tmpl)
    except TemplateValidationError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/prompts", response_model=list[JudgePromptVersionOut])
def list_prompts(dimension_code: str | None = None, db: Session = Depends(get_db)):
    q = db.query(JudgePromptVersion)
    if dimension_code:
        q = q.filter(JudgePromptVersion.dimension_code == dimension_code)
    prompts = q.order_by(
        JudgePromptVersion.dimension_code, JudgePromptVersion.created_at.desc()
    ).all()
    usage = build_prompt_usage_map(db)
    out: list[JudgePromptVersionOut] = []
    for p in prompts:
        item = JudgePromptVersionOut.model_validate(p)
        item.in_use_count = usage.get(p.id, 0)
        out.append(item)
    return out


@router.get("/prompts/{prompt_id}", response_model=JudgePromptVersionDetail)
def get_prompt(prompt_id: int, db: Session = Depends(get_db)):
    obj = db.get(JudgePromptVersion, prompt_id)
    if not obj:
        raise HTTPException(404, "prompt not found")
    detail = JudgePromptVersionDetail.model_validate(obj)
    detail.in_use_count = count_prompt_in_use(db, obj)
    return detail


@router.post("/prompts", response_model=JudgePromptVersionOut)
def create_prompt(payload: JudgePromptVersionCreate, db: Session = Depends(get_db)):
    _validate_template_or_400(payload.prompt_template)
    obj = JudgePromptVersion(**payload.model_dump())
    db.add(obj)
    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(400, f"create failed: {exc}") from exc
    db.refresh(obj)
    return obj


class PromptPreviewIn(BaseModel):
    template: str
    dim_code: str = "dim1"
    strategy: str = "per_turn"


class PromptPreviewOut(BaseModel):
    rendered: str
    vars_detected: list[str]
    vars_used: list[str]
    error: str | None = None


@router.post("/prompts/preview", response_model=PromptPreviewOut)
def preview_prompt(payload: PromptPreviewIn):
    """渲染 prompt 模板到样例 context；逻辑在 services/prompt_lifecycle.render_preview。"""
    result = render_preview(payload.template)
    return PromptPreviewOut(
        rendered=result.rendered,
        vars_detected=result.vars_detected,
        vars_used=result.vars_used,
        error=result.error,
    )


@router.put("/prompts/{prompt_id}", response_model=JudgePromptVersionDetail)
def update_prompt(
    prompt_id: int,
    payload: JudgePromptVersionUpdate,
    db: Session = Depends(get_db),
):
    obj = db.get(JudgePromptVersion, prompt_id)
    if not obj:
        raise HTTPException(404, "prompt not found")

    in_use = count_prompt_in_use(db, obj)
    if in_use > 0:
        raise HTTPException(
            409,
            f"this prompt has been used by {in_use} runs, please clone and edit the new version",
        )

    updates = payload.model_dump(exclude_unset=True)
    # 防御：以防有人构造请求加进禁改字段
    for forbidden in ("dimension_code", "version_tag", "is_active", "parent_version_id"):
        updates.pop(forbidden, None)
    # 改 prompt_template 时强制做 jinja2 语法校验
    if "prompt_template" in updates:
        _validate_template_or_400(updates["prompt_template"])
    for k, v in updates.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/prompts/{prompt_id}")
def delete_prompt(prompt_id: int, db: Session = Depends(get_db)):
    obj = db.get(JudgePromptVersion, prompt_id)
    if not obj:
        raise HTTPException(404, "prompt not found")
    if obj.is_active:
        raise HTTPException(409, "active prompt cannot be deleted; activate another version first")
    in_use = count_prompt_in_use(db, obj)
    if in_use > 0:
        raise HTTPException(409, f"this prompt has been used by {in_use} runs, cannot delete")
    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.post("/prompts/{prompt_id}/clone", response_model=JudgePromptVersionDetail)
def clone_prompt(prompt_id: int, db: Session = Depends(get_db)):
    src = db.get(JudgePromptVersion, prompt_id)
    if not src:
        raise HTTPException(404, "prompt not found")

    new_tag = next_version_tag(db, src.dimension_code, src.version_tag)
    obj = JudgePromptVersion(
        dimension_code=src.dimension_code,
        version_tag=new_tag,
        prompt_template=src.prompt_template,
        weight=src.weight,
        notes=src.notes,
        is_active=False,
        dimension_strategy=src.dimension_strategy,  # P0-2: 克隆保留策略
        parent_version_id=src.id,
    )
    db.add(obj)
    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(400, f"clone failed: {exc}") from exc
    db.refresh(obj)
    return obj


@router.post("/prompts/{prompt_id}/activate", response_model=JudgePromptVersionDetail)
def activate_prompt(prompt_id: int, db: Session = Depends(get_db)):
    obj = db.get(JudgePromptVersion, prompt_id)
    if not obj:
        raise HTTPException(404, "prompt not found")

    # 同一事务：清掉同维度其它 active，再激活当前
    db.query(JudgePromptVersion).filter(
        JudgePromptVersion.dimension_code == obj.dimension_code,
        JudgePromptVersion.id != obj.id,
        JudgePromptVersion.is_active == True,  # noqa: E712
    ).update({"is_active": False})
    obj.is_active = True
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/prompts/{prompt_id}/performance", response_model=JudgePromptPerformance)
def prompt_performance(prompt_id: int, db: Session = Depends(get_db)):
    obj = db.get(JudgePromptVersion, prompt_id)
    if not obj:
        raise HTTPException(404, "prompt not found")

    runs = runs_referencing_prompt(db, obj)
    dim_col = f"{obj.dimension_code}_score"

    items: list[JudgePromptPerformanceItem] = []
    weighted_vals: list[float] = []
    dim_vals: list[float] = []

    for run in runs:
        # 该维度均分（按 conversation 聚合后取均值）
        results = (
            db.query(EvalCaseResult)
            .filter(EvalCaseResult.eval_run_id == run.id)
            .all()
        )
        dim_scores = [
            getattr(r, dim_col)
            for r in results
            if getattr(r, dim_col, None) is not None
        ]
        avg_dim = sum(dim_scores) / len(dim_scores) if dim_scores else None

        items.append(
            JudgePromptPerformanceItem(
                eval_run_id=run.id,
                run_name=run.name,
                weighted_score=run.weighted_score,
                dim_score=avg_dim,
                used_at=run.started_at or run.created_at,
            )
        )
        if run.weighted_score is not None:
            weighted_vals.append(run.weighted_score)
        if avg_dim is not None:
            dim_vals.append(avg_dim)

    items.sort(key=lambda x: x.used_at, reverse=True)

    return JudgePromptPerformance(
        prompt_version_id=obj.id,
        dimension_code=obj.dimension_code,
        version_tag=obj.version_tag,
        is_active=obj.is_active,
        in_use_count=len(items),
        avg_weighted_score=(sum(weighted_vals) / len(weighted_vals)) if weighted_vals else None,
        avg_dim_score=(sum(dim_vals) / len(dim_vals)) if dim_vals else None,
        items=items,
    )


@router.get("/models", response_model=list[JudgeModelOut])
def list_models(db: Session = Depends(get_db)):
    return db.query(JudgeModel).order_by(JudgeModel.created_at.desc()).all()


@router.get("/models/{model_id}", response_model=JudgeModelOut)
def get_model(model_id: int, db: Session = Depends(get_db)):
    obj = db.get(JudgeModel, model_id)
    if not obj:
        raise HTTPException(404, "judge model not found")
    return obj


@router.post("/models", response_model=JudgeModelOut)
def create_model(payload: JudgeModelCreate, db: Session = Depends(get_db)):
    # 若新模型设为默认，清掉其他模型的 is_default
    if payload.is_default:
        db.query(JudgeModel).filter(JudgeModel.is_default == True).update(  # noqa: E712
            {"is_default": False},
            synchronize_session="fetch",
        )
        db.flush()
    obj = JudgeModel(**payload.model_dump())
    db.add(obj)
    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(400, f"create failed: {exc}") from exc
    db.refresh(obj)
    return obj


@router.put("/models/{model_id}", response_model=JudgeModelOut)
def update_model(model_id: int, payload: JudgeModelUpdate, db: Session = Depends(get_db)):
    obj = db.get(JudgeModel, model_id)
    if not obj:
        raise HTTPException(404, "judge model not found")
    updates = payload.model_dump(exclude_unset=True)
    # provider 和 model_id 由 schema 限制，不会进 updates，但额外防御一下
    updates.pop("provider", None)
    updates.pop("model_id", None)

    if updates.get("is_default") is True:
        db.query(JudgeModel).filter(JudgeModel.is_default == True, JudgeModel.id != model_id).update(  # noqa: E712
            {"is_default": False},
            synchronize_session="fetch",
        )
        db.flush()

    for k, v in updates.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/models/{model_id}")
def delete_model(model_id: int, db: Session = Depends(get_db)):
    obj = db.get(JudgeModel, model_id)
    if not obj:
        raise HTTPException(404, "judge model not found")
    in_use = db.query(EvalRun).filter(EvalRun.judge_model_id == model_id).count()
    if in_use > 0:
        raise HTTPException(409, f"in use by {in_use} runs")
    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.post("/models/{model_id}/test", response_model=JudgeModelTestResult)
def test_model(model_id: int, db: Session = Depends(get_db)):
    obj = db.get(JudgeModel, model_id)
    if not obj:
        raise HTTPException(404, "judge model not found")

    messages = [
        {"role": "user", "content": "回复严格 JSON：{\"ok\": true}"},
    ]
    t0 = time.time()
    raw_response: str | None = None
    error: str | None = None
    ok = False
    try:
        client = build_judge_client(
            provider=obj.provider,
            model_id=obj.model_id,
            temperature=obj.temperature,
            max_retries=1,
        )
        content = client._create_completion(messages)  # noqa: SLF001 — 直接调底层，避免 retry 拖慢
        raw_response = (content or "")[:500]
        ok = bool(content)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        ok = False

    elapsed_ms = int((time.time() - t0) * 1000)
    return JudgeModelTestResult(
        ok=ok,
        elapsed_ms=elapsed_ms,
        raw_response=raw_response,
        error=error,
        model_id=obj.model_id,
        provider=obj.provider,
    )
