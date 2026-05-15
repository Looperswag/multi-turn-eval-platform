"""Badcase tag CRUD（plan §8 B 周 / §9.B.9）。

端点：
- POST /api/badcases/{case_id}/tag                    新建 tag
- DELETE /api/badcases/tags/{tag_id}                  删除 tag
- POST /api/badcases/tags/{tag_id}/confirm            切换 is_confirmed
- POST /api/badcases/tags/{tag_id}/regression         切换 added_to_regression
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import BadcaseTag, EvalCaseResult
from app.schemas.badcase import (
    BadcaseTagConfirm,
    BadcaseTagCreate,
    BadcaseTagOut,
    BadcaseTagRegression,
)

router = APIRouter(prefix="/api/badcases", tags=["badcases"])


@router.post("/{case_id}/tag", response_model=BadcaseTagOut)
def create_tag(case_id: int, payload: BadcaseTagCreate, db: Session = Depends(get_db)):
    """为指定 case 新增 badcase tag。"""
    tag_name = payload.tag.strip()
    if not tag_name:
        raise HTTPException(400, "tag 必填")

    case = db.get(EvalCaseResult, case_id)
    if case is None:
        raise HTTPException(404, f"case id={case_id} 不存在")

    # B.1 reviewer P1：幂等 —— 同 case 同 tag 返回现有行（避免创建重复）
    existing = (
        db.query(BadcaseTag)
        .filter(
            BadcaseTag.eval_case_result_id == case_id,
            BadcaseTag.tag == tag_name,
        )
        .first()
    )
    if existing:
        if payload.notes is not None and payload.notes != existing.notes:
            existing.notes = payload.notes
            db.commit()
            db.refresh(existing)
        return BadcaseTagOut.model_validate(existing)

    row = BadcaseTag(
        eval_case_result_id=case_id,
        tag=tag_name,
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return BadcaseTagOut.model_validate(row)


@router.delete("/tags/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    obj = db.get(BadcaseTag, tag_id)
    if obj is None:
        raise HTTPException(404, "tag not found")
    db.delete(obj)
    db.commit()
    return {"status": "deleted", "id": tag_id}


@router.post("/tags/{tag_id}/confirm", response_model=BadcaseTagOut)
def confirm_tag(tag_id: int, payload: BadcaseTagConfirm, db: Session = Depends(get_db)):
    obj = db.get(BadcaseTag, tag_id)
    if obj is None:
        raise HTTPException(404, "tag not found")
    obj.is_confirmed = payload.is_confirmed
    db.commit()
    db.refresh(obj)
    return BadcaseTagOut.model_validate(obj)


@router.post("/tags/{tag_id}/regression", response_model=BadcaseTagOut)
def regression_tag(tag_id: int, payload: BadcaseTagRegression, db: Session = Depends(get_db)):
    obj = db.get(BadcaseTag, tag_id)
    if obj is None:
        raise HTTPException(404, "tag not found")
    obj.added_to_regression = payload.added
    db.commit()
    db.refresh(obj)
    return BadcaseTagOut.model_validate(obj)
