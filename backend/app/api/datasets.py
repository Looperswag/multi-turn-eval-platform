import json
import uuid
from dataclasses import asdict

import redis as redis_sync
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.core.db import get_db
from app.models import BotRewrite, BotVersion, Conversation, Dataset, Turn
from app.schemas.dataset import (
    ConfirmPayload,
    ConversationDetail,
    DatasetCreate,
    DatasetDetail,
    DatasetOut,
    FieldMappingPayload,
    ParseSessionOut,
    PreviewPayload,
    PreviewResult,
    ValidationIssueOut,
    ValidationReportOut,
)
from app.services import dataset_parser

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

# Redis 句柄（同步）—— 用于 parse 会话缓存
_redis = redis_sync.Redis.from_url(settings.redis_url, decode_responses=True)
_PARSE_TTL_SECONDS = 1800  # 30 分钟
_PARSE_KEY_PREFIX = "dataset_parse:"


@router.get("", response_model=list[DatasetOut])
def list_datasets(db: Session = Depends(get_db)):
    return db.query(Dataset).order_by(Dataset.created_at.desc()).all()


@router.post("", response_model=DatasetOut)
def create_dataset(payload: DatasetCreate, db: Session = Depends(get_db)):
    obj = Dataset(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{dataset_id}", response_model=DatasetDetail)
def get_dataset(dataset_id: int, db: Session = Depends(get_db)):
    obj = db.get(Dataset, dataset_id)
    if not obj:
        raise HTTPException(404, "dataset not found")
    return obj


@router.get("/{dataset_id}/conversations/{conv_id}", response_model=ConversationDetail)
def get_conversation(dataset_id: int, conv_id: int, db: Session = Depends(get_db)):
    obj = (
        db.query(Conversation)
        .filter(Conversation.id == conv_id, Conversation.dataset_id == dataset_id)
        .first()
    )
    if not obj:
        raise HTTPException(404, "conversation not found")
    return obj


@router.get("/{dataset_id}/export")
def export_dataset(dataset_id: int, db: Session = Depends(get_db)):
    """以 mock_multi_turn_queries 同格式导出整个 dataset 为 JSON 数组下载。

    返回字段对齐源种子（rewritten_query 当前仅 BotRewrite 存，此处恒为 null；
    query_id 由 {conversation_id_src}_q{turn_index} 重建）。
    """
    ds = (
        db.query(Dataset)
        .options(selectinload(Dataset.conversations).selectinload(Conversation.turns))
        .filter(Dataset.id == dataset_id)
        .first()
    )
    if not ds:
        raise HTTPException(404, "dataset not found")

    payload = []
    for conv in sorted(ds.conversations, key=lambda c: c.id):
        payload.append(
            {
                "conversation_id": conv.conversation_id_src,
                "dimension_tag": conv.dimension_tag,
                "quality_label": conv.quality_label,
                "issue_type": conv.issue_type,
                "total_turns": conv.total_turns,
                "turns": [
                    {
                        "query_id": f"{conv.conversation_id_src}_q{t.turn_index}",
                        "turn_index": t.turn_index,
                        "timestamp": t.timestamp,
                        "user_query": t.user_query,
                        "rewritten_query": None,
                    }
                    for t in conv.turns
                ],
            }
        )

    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    filename = f"{ds.name}_{ds.version}.json"
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{dataset_id}/search")
def search_dataset(
    dataset_id: int,
    q: str = Query("", description="模糊搜索关键字"),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """在 conversation_id_src / dimension_tag / issue_type / quality_label / turn.user_query
    上做 ILIKE 匹配，返回会话列表 + 命中 turn 摘要。空 q 等价于列出全部（截到 limit）。
    """
    ds = db.get(Dataset, dataset_id)
    if not ds:
        raise HTTPException(404, "dataset not found")

    q_strip = (q or "").strip()

    base = db.query(Conversation).filter(Conversation.dataset_id == dataset_id)

    if q_strip:
        like = f"%{q_strip}%"
        # 用 EXISTS 子查询匹配 turn.user_query，避免 join 后行膨胀
        turn_match = (
            db.query(Turn.id)
            .filter(
                Turn.conversation_id == Conversation.id,
                Turn.user_query.ilike(like),
            )
            .exists()
        )
        base = base.filter(
            or_(
                Conversation.conversation_id_src.ilike(like),
                Conversation.dimension_tag.ilike(like),
                Conversation.issue_type.ilike(like),
                Conversation.quality_label.ilike(like),
                turn_match,
            )
        )

    base = base.order_by(Conversation.id).limit(limit)
    conversations = base.all()

    # 对命中 turn 的会话，附上前 3 条匹配 turn 的简短摘要，方便前端高亮预览
    matched_turns_by_conv: dict[int, list[dict]] = {}
    if q_strip and conversations:
        like = f"%{q_strip}%"
        conv_ids = [c.id for c in conversations]
        turn_hits = (
            db.query(Turn)
            .filter(
                Turn.conversation_id.in_(conv_ids),
                Turn.user_query.ilike(like),
            )
            .order_by(Turn.conversation_id, Turn.turn_index)
            .all()
        )
        for t in turn_hits:
            bucket = matched_turns_by_conv.setdefault(t.conversation_id, [])
            if len(bucket) < 3:
                bucket.append({"turn_index": t.turn_index, "user_query": t.user_query})

    items = [
        {
            "id": c.id,
            "conversation_id_src": c.conversation_id_src,
            "dimension_tag": c.dimension_tag,
            "quality_label": c.quality_label,
            "issue_type": c.issue_type,
            "total_turns": c.total_turns,
            "matched_turns": matched_turns_by_conv.get(c.id, []),
        }
        for c in conversations
    ]

    return {
        "dataset_id": dataset_id,
        "q": q_strip,
        "total": len(items),
        "truncated": len(items) >= limit,
        "items": items,
    }


@router.post("/upload", response_model=DatasetOut)
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str | None = Form(default=None),
    version: str = Form(default="v1"),
    db: Session = Depends(get_db),
):
    """上传 JSON 评测集（mock_multi_turn_queries 同格式）。CSV/Excel 后续支持。"""
    raw = (await file.read()).decode("utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"invalid json: {exc}") from exc
    if not isinstance(data, list):
        raise HTTPException(400, "expect JSON array of conversations")

    dataset = Dataset(name=name, description=description, version=version)
    db.add(dataset)
    db.flush()

    for conv_payload in data:
        conv = Conversation(
            dataset_id=dataset.id,
            conversation_id_src=conv_payload["conversation_id"],
            dimension_tag=conv_payload.get("dimension_tag"),
            quality_label=conv_payload.get("quality_label"),
            issue_type=conv_payload.get("issue_type"),
            total_turns=conv_payload.get("total_turns", len(conv_payload.get("turns", []))),
        )
        db.add(conv)
        db.flush()
        for t in conv_payload.get("turns", []):
            db.add(
                Turn(
                    conversation_id=conv.id,
                    turn_index=t["turn_index"],
                    user_query=t["user_query"],
                    timestamp=t.get("timestamp"),
                )
            )
    dataset.conversation_count = len(data)
    db.commit()
    db.refresh(dataset)
    return dataset


# ---------------------------------------------------------------------------
# A.4 — 4 步向导端点
# ---------------------------------------------------------------------------


def _mapping_from_payload(payload: FieldMappingPayload) -> dataset_parser.FieldMapping:
    return dataset_parser.FieldMapping(
        conversation_id=payload.conversation_id or None,
        turn_index=payload.turn_index or None,
        user_query=payload.user_query or None,
        rewritten_query=payload.rewritten_query or None,
        dimension_tag=payload.dimension_tag or None,
        quality_label=payload.quality_label or None,
        issue_type=payload.issue_type or None,
        turn_index_source=payload.turn_index_source or "turn_index",
    )


def _persist_conversations(
    db: Session,
    dataset: Dataset,
    convs: list[dict],
) -> None:
    """复用 /upload 的入库逻辑：写 Conversation + Turn，并更新 conversation_count。"""
    for conv_payload in convs:
        conv = Conversation(
            dataset_id=dataset.id,
            conversation_id_src=conv_payload["conversation_id"],
            dimension_tag=conv_payload.get("dimension_tag"),
            quality_label=conv_payload.get("quality_label"),
            issue_type=conv_payload.get("issue_type"),
            total_turns=conv_payload.get("total_turns", len(conv_payload.get("turns", []))),
        )
        db.add(conv)
        db.flush()
        for t in conv_payload.get("turns", []):
            db.add(
                Turn(
                    conversation_id=conv.id,
                    turn_index=t["turn_index"],
                    user_query=t["user_query"],
                    timestamp=t.get("timestamp"),
                )
            )
    dataset.conversation_count = len(convs)


def _attach_rewrites_for_dataset(
    db: Session,
    bot_version_id: int,
    dataset_id: int,
    convs: list[dict],
) -> int:
    """复用 bots.attach_rewrites 的 UPSERT 模式：把 convs 里的 rewritten_query 写入 bot_rewrite。"""
    rows = (
        db.query(Conversation.conversation_id_src, Turn.turn_index, Turn.id)
        .join(Turn, Turn.conversation_id == Conversation.id)
        .filter(Conversation.dataset_id == dataset_id)
        .all()
    )
    turn_lookup = {(r[0], r[1]): r[2] for r in rows}

    rows_to_upsert = []
    for conv in convs:
        for t in conv.get("turns", []):
            rw = t.get("rewritten_query")
            if not rw:
                continue
            turn_id = turn_lookup.get((conv["conversation_id"], t["turn_index"]))
            if turn_id is None:
                continue
            rows_to_upsert.append({
                "turn_id": turn_id,
                "bot_version_id": bot_version_id,
                "rewritten_query": rw,
            })
    if rows_to_upsert:
        stmt = pg_insert(BotRewrite.__table__).values(rows_to_upsert)
        stmt = stmt.on_conflict_do_update(
            index_elements=["turn_id", "bot_version_id"],
            set_={"rewritten_query": stmt.excluded.rewritten_query},
        )
        db.execute(stmt)
    return len(rows_to_upsert)


@router.post("/upload/parse", response_model=ParseSessionOut)
async def parse_upload(
    file: UploadFile = File(...),
    format: str | None = Form(default=None),
):
    """Step 1：解析文件 → 提取 columns + suggested mapping + 前 10 行样例。

    把解析后的全量 rows 序列化为 JSON 暂存到 redis（TTL 30 分钟）。
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(400, "empty file")
    # P0: 30MB 上限防 OOM；前端已提示 ≤30MB，后端再守一道
    _MAX_UPLOAD_BYTES = 30 * 1024 * 1024
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            413,
            f"文件 {len(file_bytes) / 1024 / 1024:.1f} MB 超过上限 30 MB；请拆分后重试",
        )

    try:
        parsed = dataset_parser.parse_any(file_bytes, file.filename or "", format)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"解析失败：{exc}") from exc

    if not parsed.rows:
        raise HTTPException(400, "未解析出任何行")
    if not parsed.columns:
        raise HTTPException(400, "未解析出列名（请检查首行 header）")

    suggested = dataset_parser.infer_field_mapping(parsed.columns)

    session_id = uuid.uuid4().hex
    key = f"{_PARSE_KEY_PREFIX}{session_id}"
    payload = {
        "columns": parsed.columns,
        "rows": parsed.rows,
        "format": parsed.format,
        "filename": file.filename,
    }
    _redis.set(key, json.dumps(payload, ensure_ascii=False, default=str), ex=_PARSE_TTL_SECONDS)

    return ParseSessionOut(
        parse_session_id=session_id,
        columns=parsed.columns,
        sample_rows=parsed.rows[:10],
        suggested_mapping=FieldMappingPayload(**asdict(suggested)),
        format=parsed.format,
        total_rows=len(parsed.rows),
    )


def _load_session(parse_session_id: str) -> dict:
    raw = _redis.get(f"{_PARSE_KEY_PREFIX}{parse_session_id}")
    if not raw:
        raise HTTPException(410, "parse session 已过期或不存在，请重新上传")
    return json.loads(raw)


@router.post("/upload/preview", response_model=PreviewResult)
def preview_upload(payload: PreviewPayload):
    """Step 2/3：用户调整 mapping 后，重新校验并返回前 5 条预览。"""
    session = _load_session(payload.parse_session_id)
    rows: list[dict] = session["rows"]
    mapping = _mapping_from_payload(payload.mapping)

    report = dataset_parser.validate(rows, mapping)
    preview_convs: list[dict] = []
    if report.is_passable:
        try:
            convs = dataset_parser.transform(rows, mapping)
            preview_convs = convs[:5]
        except Exception:  # noqa: BLE001
            preview_convs = []

    return PreviewResult(
        validation_report=ValidationReportOut(
            issues=[ValidationIssueOut(**asdict(i)) for i in report.issues],
            total_conversations=report.total_conversations,
            total_turns=report.total_turns,
            is_passable=report.is_passable,
        ),
        preview_conversations=preview_convs,
    )


@router.post("/upload/confirm", response_model=DatasetOut)
def confirm_upload(payload: ConfirmPayload, db: Session = Depends(get_db)):
    """Step 4：确认入库。可选 attach 到 bot_version_id 同时写 rewrite。"""
    session = _load_session(payload.parse_session_id)
    rows: list[dict] = session["rows"]
    mapping = _mapping_from_payload(payload.mapping)

    report = dataset_parser.validate(rows, mapping)
    if not report.is_passable:
        raise HTTPException(
            422,
            detail={
                "message": "校验未通过，无法入库",
                "issues": [asdict(i) for i in report.issues if i.severity == "error"],
            },
        )

    convs = dataset_parser.transform(rows, mapping)
    if not convs:
        raise HTTPException(422, "无可入库的 conversation")

    # 若指定 bot version，先校验存在
    bot_version_id = payload.attach_bot_version_id
    if bot_version_id is not None:
        if not db.get(BotVersion, bot_version_id):
            raise HTTPException(404, "bot_version not found")

    dataset = Dataset(
        name=payload.dataset_name,
        description=payload.description,
        version=payload.version,
        source_file_uri=session.get("filename"),
    )
    db.add(dataset)
    db.flush()
    _persist_conversations(db, dataset, convs)
    db.flush()

    if bot_version_id is not None:
        _attach_rewrites_for_dataset(db, bot_version_id, dataset.id, convs)

    db.commit()
    db.refresh(dataset)

    # 清掉 redis 缓存（成功入库后不再需要）
    _redis.delete(f"{_PARSE_KEY_PREFIX}{payload.parse_session_id}")
    return dataset
