import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import BotRewrite, BotVersion, Conversation, Dataset, Turn
from app.schemas.judge import (
    BotRewriteDatasetStat,
    BotVersionCreate,
    BotVersionDetailOut,
    BotVersionOut,
)

router = APIRouter(prefix="/api/bot-versions", tags=["bots"])


@router.get("", response_model=list[BotVersionOut])
def list_bot_versions(db: Session = Depends(get_db)):
    return db.query(BotVersion).order_by(BotVersion.created_at.desc()).all()


@router.post("", response_model=BotVersionOut)
def create_bot_version(payload: BotVersionCreate, db: Session = Depends(get_db)):
    obj = BotVersion(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{bot_version_id}", response_model=BotVersionDetailOut)
def get_bot_version(bot_version_id: int, db: Session = Depends(get_db)):
    bot = db.get(BotVersion, bot_version_id)
    if not bot:
        raise HTTPException(404, "bot_version not found")

    # 每个 dataset 的 turn 总数
    total_rows = (
        db.query(Dataset.id, Dataset.name, func.count(Turn.id))
        .select_from(Dataset)
        .outerjoin(Conversation, Conversation.dataset_id == Dataset.id)
        .outerjoin(Turn, Turn.conversation_id == Conversation.id)
        .group_by(Dataset.id, Dataset.name)
        .all()
    )

    # 该 bot_version 在每个 dataset 上的改写数
    rewrite_rows = (
        db.query(Dataset.id, func.count(BotRewrite.id))
        .select_from(BotRewrite)
        .join(Turn, Turn.id == BotRewrite.turn_id)
        .join(Conversation, Conversation.id == Turn.conversation_id)
        .join(Dataset, Dataset.id == Conversation.dataset_id)
        .filter(BotRewrite.bot_version_id == bot_version_id)
        .group_by(Dataset.id)
        .all()
    )
    rewrite_map = {r[0]: r[1] for r in rewrite_rows}

    stats = [
        BotRewriteDatasetStat(
            dataset_id=ds_id,
            dataset_name=ds_name,
            rewrite_count=int(rewrite_map.get(ds_id, 0)),
            total_turns=int(total or 0),
        )
        for ds_id, ds_name, total in total_rows
    ]
    stats.sort(key=lambda s: s.dataset_id)

    return BotVersionDetailOut(
        bot_version=BotVersionOut.model_validate(bot),
        rewrite_stats=stats,
    )


@router.post("/{bot_version_id}/attach/{dataset_id}")
async def attach_rewrites(
    bot_version_id: int,
    dataset_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传 bot 对某 dataset 的改写输出。

    支持两种数据来源：
    1. 与 mock_multi_turn_queries_100.json 同格式（含 rewritten_query 字段）
    2. 扁平格式：[{conversation_id, turn_index, rewritten_query}, ...]
    """
    if not db.get(BotVersion, bot_version_id):
        raise HTTPException(404, "bot_version not found")
    raw = (await file.read()).decode("utf-8")
    data = json.loads(raw)

    pairs: list[tuple[str, int, str | None]] = []
    if isinstance(data, list) and data and "turns" in data[0]:
        for conv in data:
            for t in conv["turns"]:
                pairs.append((conv["conversation_id"], t["turn_index"], t.get("rewritten_query")))
    elif isinstance(data, list):
        for row in data:
            pairs.append((row["conversation_id"], row["turn_index"], row.get("rewritten_query")))
    else:
        raise HTTPException(400, "unsupported format")

    # 查询所有相关 turn 的 (conv_src, turn_index) -> turn.id
    rows = (
        db.query(Conversation.conversation_id_src, Turn.turn_index, Turn.id)
        .join(Turn, Turn.conversation_id == Conversation.id)
        .filter(Conversation.dataset_id == dataset_id)
        .all()
    )
    turn_lookup = {(r[0], r[1]): r[2] for r in rows}

    # Postgres UPSERT：UniqueConstraint(turn_id, bot_version_id) 命中时更新 rewritten_query；
    # 避免重复上传同一份文件触发 IntegrityError → 500。
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    rows_to_upsert = []
    for conv_src, turn_idx, rewrite in pairs:
        turn_id = turn_lookup.get((conv_src, turn_idx))
        if turn_id is None:
            continue
        rows_to_upsert.append({
            "turn_id": turn_id,
            "bot_version_id": bot_version_id,
            "rewritten_query": rewrite,
        })
    inserted = len(rows_to_upsert)
    if rows_to_upsert:
        stmt = pg_insert(BotRewrite.__table__).values(rows_to_upsert)
        stmt = stmt.on_conflict_do_update(
            index_elements=["turn_id", "bot_version_id"],
            set_={"rewritten_query": stmt.excluded.rewritten_query},
        )
        db.execute(stmt)
    db.commit()
    return {"attached": inserted, "skipped": len(pairs) - inserted}
