"""Comparison API（plan §8.A.5.1）。

端点：
- GET  /api/comparisons/diff-runs?a=...&b=...    自动差异检测 + 类型推断（Spec-7）
- POST /api/comparisons                          创建并即时计算（Spec-1/2/4/8）
- GET  /api/comparisons                          列表
- GET  /api/comparisons/{id}                     详情（含 Spec-3 缓存失效检查）
- DELETE /api/comparisons/{id}                   清理
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Comparison, EvalRun
from app.schemas.comparison import (
    ComparisonCreate,
    ComparisonOut,
    ComparisonPayload,
    DiffRunsResult,
)
from app.services.comparison import (
    build_cache_key,
    compute_comparison_payload,
    diff_runs,
    validate_run_compat,
)

router = APIRouter(prefix="/api/comparisons", tags=["comparisons"])


def _serialize(c: Comparison) -> ComparisonOut:
    """从 ORM + 缓存的 result_payload 构造 ComparisonOut。"""
    return ComparisonOut(
        id=c.id,
        name=c.name,
        type=c.type,
        run_a_id=c.run_a_id,
        run_b_id=c.run_b_id,
        created_at=c.created_at,
        computed_at=c.computed_at,
        payload=ComparisonPayload(**c.result_payload),
    )


@router.get("/diff-runs", response_model=DiffRunsResult)
def get_diff_runs(a: int, b: int, db: Session = Depends(get_db)):
    """Spec-7：返回两 run 的差异字段 + 推荐对比类型。

    前端在 /comparisons/new 选完 A/B 后即时调用。
    """
    if a == b:
        raise HTTPException(400, "run_a 与 run_b 不能相同")
    run_a = db.get(EvalRun, a)
    run_b = db.get(EvalRun, b)
    if run_a is None:
        raise HTTPException(404, f"run_a id={a} 不存在")
    if run_b is None:
        raise HTTPException(404, f"run_b id={b} 不存在")
    result = diff_runs(run_a, run_b)
    return DiffRunsResult(
        diff_points=result["diff_points"],
        suggested_type=result["suggested_type"],
        run_a_id=a,
        run_b_id=b,
    )


@router.post("", response_model=ComparisonOut)
def create_comparison(payload: ComparisonCreate, db: Session = Depends(get_db)):
    """Spec-1/2/4/8：校验 → 即时计算 → 入库。"""
    if payload.run_a_id == payload.run_b_id:
        raise HTTPException(400, "run_a 与 run_b 不能相同")
    if payload.type not in {"prompt", "bot", "judge"}:
        # human 类型留给 A.5.2 走独立端点
        raise HTTPException(
            400,
            f"type='{payload.type}' 不支持，可选 prompt/bot/judge（human 走 A.5.2 端点）",
        )

    run_a = db.get(EvalRun, payload.run_a_id)
    run_b = db.get(EvalRun, payload.run_b_id)
    if run_a is None or run_b is None:
        raise HTTPException(404, "run_a 或 run_b 不存在")

    # 必须是 success/partial 才能对比（不然没数据）
    for r, label in [(run_a, "run_a"), (run_b, "run_b")]:
        if r.status not in ("success", "partial"):
            raise HTTPException(
                400,
                f"{label} 状态 '{r.status}' 不可对比，需 success/partial",
            )

    # Spec-1 / Spec-2 校验
    issues = validate_run_compat(run_a, run_b, payload.type)
    if issues:
        raise HTTPException(
            400,
            {
                "message": f"run 配置与 comparison.type='{payload.type}' 不兼容",
                "diff_points": issues,
            },
        )

    # 同 (run_a, run_b, type) 已存在 → 复用并更新缓存
    existing = (
        db.query(Comparison)
        .filter(
            Comparison.run_a_id == payload.run_a_id,
            Comparison.run_b_id == payload.run_b_id,
            Comparison.type == payload.type,
        )
        .first()
    )
    if existing:
        # 直接复用，触发缓存刷新（GET 路径会处理）
        return get_comparison(existing.id, db)

    # Spec-8：同步即时计算
    result_payload = compute_comparison_payload(db, run_a, run_b, payload.type)
    cache_key = build_cache_key(run_a, run_b)

    comparison = Comparison(
        name=payload.name
        or f"{payload.type}: #{run_a.id} vs #{run_b.id}",
        type=payload.type,
        run_a_id=run_a.id,
        run_b_id=run_b.id,
        cache_key=cache_key,
        result_payload=result_payload,
        computed_at=datetime.utcnow(),
    )
    db.add(comparison)
    db.commit()
    db.refresh(comparison)
    return _serialize(comparison)


@router.get("", response_model=list[ComparisonOut])
def list_comparisons(db: Session = Depends(get_db)):
    items = (
        db.query(Comparison).order_by(Comparison.created_at.desc()).all()
    )
    return [_serialize(c) for c in items]


@router.get("/{cid}", response_model=ComparisonOut)
def get_comparison(cid: int, db: Session = Depends(get_db)):
    c = db.get(Comparison, cid)
    if not c:
        raise HTTPException(404, "comparison not found")

    # Spec-3：检查缓存键是否失效
    run_a = db.get(EvalRun, c.run_a_id)
    run_b = db.get(EvalRun, c.run_b_id) if c.run_b_id else None
    if run_a is None or run_b is None:
        raise HTTPException(404, "关联的 run 不存在")
    fresh_key = build_cache_key(run_a, run_b)
    if fresh_key != c.cache_key:
        # 重算
        c.result_payload = compute_comparison_payload(db, run_a, run_b, c.type)
        c.cache_key = fresh_key
        c.computed_at = datetime.utcnow()
        db.add(c)
        db.commit()
        db.refresh(c)

    return _serialize(c)


@router.delete("/{cid}")
def delete_comparison(cid: int, db: Session = Depends(get_db)):
    c = db.get(Comparison, cid)
    if not c:
        raise HTTPException(404, "comparison not found")
    db.delete(c)
    db.commit()
    return {"status": "deleted", "id": cid}
