"""C.2 回归集管理 API。

端点：
- GET    /api/regression-sets                          列表
- POST   /api/regression-sets                          创建
- GET    /api/regression-sets/{id}                     详情（含 items）
- DELETE /api/regression-sets/{id}                     删除
- POST   /api/regression-sets/{id}/items               批量加入 conversation
- DELETE /api/regression-sets/{id}/items/{item_id}     删除单条
- POST   /api/regression-sets/{id}/items/from-badcases 一键把某 run 中带特定 tag 的 case 加入

注意：与 badcase tag 上 `added_to_regression` 字段语义解耦——
该字段保留作 UI 上的视觉标记（=「已加入 default 集合」），
但真正的回归集存储在 regression_set / regression_set_item 表。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import (
    BadcaseTag,
    Conversation,
    EvalCaseResult,
    RegressionSet,
    RegressionSetItem,
)
from app.schemas.regression_set import (
    RegressionSetAddItems,
    RegressionSetAddItemsResult,
    RegressionSetCreate,
    RegressionSetDetail,
    RegressionSetFromBadcases,
    RegressionSetFromBadcasesResult,
    RegressionSetItemOut,
    RegressionSetOut,
)

router = APIRouter(prefix="/api/regression-sets", tags=["regression-sets"])


# ---------- helpers ----------


def _item_to_out(db: Session, item: RegressionSetItem) -> RegressionSetItemOut:
    conv = db.get(Conversation, item.conversation_id)
    return RegressionSetItemOut(
        id=item.id,
        conversation_id=item.conversation_id,
        conversation_id_src=conv.conversation_id_src if conv else None,
        dimension_tag=conv.dimension_tag if conv else None,
        source_case_id=item.source_case_id,
        added_at=item.added_at,
    )


# ---------- regression set CRUD ----------


@router.get("", response_model=list[RegressionSetOut])
def list_sets(db: Session = Depends(get_db)):
    rows = (
        db.query(RegressionSet)
        .order_by(RegressionSet.created_at.desc())
        .all()
    )
    # 用一次 group-by 拿 item_count，避免 N+1
    counts: dict[int, int] = {}
    if rows:
        from sqlalchemy import func

        for set_id, cnt in (
            db.query(RegressionSetItem.regression_set_id, func.count(RegressionSetItem.id))
            .group_by(RegressionSetItem.regression_set_id)
            .all()
        ):
            counts[set_id] = cnt
    return [
        RegressionSetOut(
            id=r.id,
            name=r.name,
            description=r.description,
            created_at=r.created_at,
            item_count=counts.get(r.id, 0),
        )
        for r in rows
    ]


@router.post("", response_model=RegressionSetOut)
def create_set(payload: RegressionSetCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "name 必填")
    existing = db.query(RegressionSet).filter(RegressionSet.name == name).first()
    if existing:
        raise HTTPException(409, f"name='{name}' 已存在")
    row = RegressionSet(name=name, description=payload.description)
    db.add(row)
    db.commit()
    db.refresh(row)
    return RegressionSetOut(
        id=row.id,
        name=row.name,
        description=row.description,
        created_at=row.created_at,
        item_count=0,
    )


@router.get("/{rs_id}", response_model=RegressionSetDetail)
def get_set(rs_id: int, db: Session = Depends(get_db)):
    rs = db.get(RegressionSet, rs_id)
    if rs is None:
        raise HTTPException(404, f"regression_set id={rs_id} 不存在")
    items_out = [_item_to_out(db, it) for it in rs.items]
    return RegressionSetDetail(
        id=rs.id,
        name=rs.name,
        description=rs.description,
        created_at=rs.created_at,
        items=items_out,
    )


@router.delete("/{rs_id}")
def delete_set(rs_id: int, db: Session = Depends(get_db)):
    rs = db.get(RegressionSet, rs_id)
    if rs is None:
        raise HTTPException(404, "regression_set not found")
    db.delete(rs)
    db.commit()
    return {"status": "deleted", "id": rs_id}


# ---------- items ----------


@router.post("/{rs_id}/items", response_model=RegressionSetAddItemsResult)
def add_items(
    rs_id: int, payload: RegressionSetAddItems, db: Session = Depends(get_db)
):
    rs = db.get(RegressionSet, rs_id)
    if rs is None:
        raise HTTPException(404, "regression_set not found")
    if not payload.conversation_ids:
        raise HTTPException(400, "conversation_ids 不可为空")

    # 校验 conv 存在
    conv_ids = list({int(x) for x in payload.conversation_ids})
    existing_conv_ids = {
        cid
        for (cid,) in db.query(Conversation.id)
        .filter(Conversation.id.in_(conv_ids))
        .all()
    }
    missing = [c for c in conv_ids if c not in existing_conv_ids]
    if missing:
        raise HTTPException(400, f"conversation_id 不存在: {missing}")

    # 取已有 item 用于去重
    already = {
        cid
        for (cid,) in db.query(RegressionSetItem.conversation_id)
        .filter(
            RegressionSetItem.regression_set_id == rs_id,
            RegressionSetItem.conversation_id.in_(conv_ids),
        )
        .all()
    }

    added_rows: list[RegressionSetItem] = []
    skipped = 0
    for cid in conv_ids:
        if cid in already:
            skipped += 1
            continue
        row = RegressionSetItem(
            regression_set_id=rs_id,
            conversation_id=cid,
            source_case_id=payload.source_case_id,
        )
        db.add(row)
        added_rows.append(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "唯一性冲突（conversation 已在集合中）")

    for r in added_rows:
        db.refresh(r)

    return RegressionSetAddItemsResult(
        added=len(added_rows),
        skipped=skipped,
        items=[_item_to_out(db, r) for r in added_rows],
    )


@router.delete("/{rs_id}/items/{item_id}")
def delete_item(rs_id: int, item_id: int, db: Session = Depends(get_db)):
    row = db.get(RegressionSetItem, item_id)
    if row is None or row.regression_set_id != rs_id:
        raise HTTPException(404, "item not found")
    db.delete(row)
    db.commit()
    return {"status": "deleted", "id": item_id}


@router.post(
    "/{rs_id}/items/from-badcases",
    response_model=RegressionSetFromBadcasesResult,
)
def add_from_badcases(
    rs_id: int,
    payload: RegressionSetFromBadcases,
    db: Session = Depends(get_db),
):
    """一键把 eval_run 中带指定 tag 的 case 的 conversation 全部加入。"""
    rs = db.get(RegressionSet, rs_id)
    if rs is None:
        raise HTTPException(404, "regression_set not found")
    tag_name = payload.tag.strip()
    if not tag_name:
        raise HTTPException(400, "tag 必填")

    # 找出 run 内 case_id × tag 命中的 case
    rows = (
        db.query(EvalCaseResult.id, EvalCaseResult.conversation_id)
        .join(BadcaseTag, BadcaseTag.eval_case_result_id == EvalCaseResult.id)
        .filter(
            EvalCaseResult.eval_run_id == payload.eval_run_id,
            BadcaseTag.tag == tag_name,
        )
        .all()
    )
    matched = len(rows)
    if matched == 0:
        return RegressionSetFromBadcasesResult(added=0, skipped=0, matched_cases=0)

    # conversation_id -> case_id（取一条做溯源）
    conv_to_case: dict[int, int] = {}
    for case_id, conv_id in rows:
        conv_to_case.setdefault(conv_id, case_id)

    already = {
        cid
        for (cid,) in db.query(RegressionSetItem.conversation_id)
        .filter(
            RegressionSetItem.regression_set_id == rs_id,
            RegressionSetItem.conversation_id.in_(list(conv_to_case.keys())),
        )
        .all()
    }

    added = 0
    skipped = 0
    for conv_id, case_id in conv_to_case.items():
        if conv_id in already:
            skipped += 1
            continue
        db.add(
            RegressionSetItem(
                regression_set_id=rs_id,
                conversation_id=conv_id,
                source_case_id=case_id,
            )
        )
        added += 1
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "唯一性冲突")

    return RegressionSetFromBadcasesResult(
        added=added, skipped=skipped, matched_cases=matched
    )
