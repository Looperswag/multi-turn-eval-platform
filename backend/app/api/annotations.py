"""Annotation & Agreement API（plan §8.A.5.2）。

端点：
- GET  /api/annotations/queue?run_id=...&dimension_code=...&annotator=...    标注队列（Spec-9 排序）
- POST /api/annotations                                                       UPSERT 单条标注（Spec-10）
- GET  /api/annotations                                                       列表（按 conv/dim/annotator 过滤）
- DELETE /api/annotations/{id}                                                删除单条
- GET  /api/agreement/{run_id}?annotator=...&merge=true                       一致率看板（Spec-11/12/13）

Spec 落地：
- Spec-9：队列 ORDER BY case judge_score（0→0.5→1→NA），二级按 confidence asc nulls last，三级按 conversation_id
- Spec-10：UPSERT 走 PostgreSQL INSERT ... ON CONFLICT DO UPDATE
- Spec-11：标注表单 score=None & is_applicable=False 表示"不适用"；agreement 算法按 4 档归类
- Spec-12：每维度返回 sample_size；前端 < 20 时不展示 kappa
- Spec-13：默认按 annotator 分组返回；merge=true 时合并视图（众数 / 票数相等 abstain）
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import DIMENSION_NAMES
from app.core.db import get_db
from app.models import (
    BotRewrite,
    Conversation,
    EvalCaseResult,
    EvalRun,
    EvalTurnResult,
    HumanAnnotation,
    Turn,
)
from app.schemas.annotation import (
    AgreementAnnotator,
    AgreementDim,
    AgreementResponse,
    AnnotationCreate,
    AnnotationOut,
    QueueItem,
    QueueResponse,
    QueueTurn,
)
from app.services.agreement import compute_agreement, majority_vote

router = APIRouter(prefix="/api", tags=["annotations"])


# ====================================================================
# 工具：从 EvalCaseResult.dim_results_full / EvalTurnResult 提取维度结果
# ====================================================================


def _extract_judge_dim_info(
    case: EvalCaseResult, dim: str, turn_results_by_dim: dict[str, list[EvalTurnResult]]
) -> dict[str, Any]:
    """从 case 提取该维度的 judge 信息 (score / applicable / explanation / confidence / raw)。

    dim_results_full 结构（约定，按 EvalEngine 输出）：
        {dim1: {score, applicable, explanation, confidence, raw_response, ...}, ...}
    若 dim_results_full 不存在或缺该 dim，回退到 turn_results 中聚合。
    """
    score = getattr(case, f"{dim}_score", None)

    applicable: bool | None = None
    explanation: str | None = None
    confidence: float | None = None
    raw: dict | None = None

    full = case.dim_results_full or {}
    dim_block = full.get(dim) if isinstance(full, dict) else None
    if isinstance(dim_block, dict):
        applicable = dim_block.get("applicable")
        explanation = dim_block.get("explanation") or dim_block.get("reason")
        confidence = dim_block.get("confidence")
        raw = dim_block.get("raw_response") or dim_block.get("raw") or dim_block
        # 兜底：从 turn_scores 拼出 explanation
        if explanation is None and isinstance(dim_block.get("turn_scores"), list):
            parts: list[str] = []
            for ts in dim_block["turn_scores"]:
                if not isinstance(ts, dict):
                    continue
                detail = ts.get("detail") or {}
                exp = detail.get("explanation") or detail.get("reason")
                if exp:
                    parts.append(f"Turn {ts.get('turn_index', '?')}：{exp}")
            if parts:
                explanation = "\n".join(parts)

    # 回退：用 turn-level 第一条记录的 applicable / raw
    if (applicable is None or explanation is None) and turn_results_by_dim.get(dim):
        first = turn_results_by_dim[dim][0]
        if applicable is None:
            applicable = first.applicable
        if raw is None and first.judge_raw_response:
            raw = first.judge_raw_response
            if explanation is None and isinstance(raw, dict):
                explanation = raw.get("explanation") or raw.get("reason")

    # score=None 且 applicable=False 时表示 N/A 评分
    return {
        "score": score,
        "applicable": applicable,
        "explanation": explanation,
        "confidence": confidence,
        "raw": raw,
    }


# ====================================================================
# Queue
# ====================================================================


def _spec9_order_key(score: float | None, applicable: bool | None, confidence: float | None) -> tuple:
    """Spec-9：(bucket, confidence, conversation_id) 三级排序。

    bucket: 0=score=0(最差先) → 1=score=0.5 → 2=score=1 → 3=NA(applicable=false)
    （与前端"0 → 0.5 → 1 → N/A"文字一致，修自 reviewer P1）
    confidence: asc, None last
    """
    if applicable is False:
        bucket = 3
    elif score is None:
        bucket = 3  # 未知归到 NA 桶
    elif score == 0.0:
        bucket = 0
    elif score == 0.5:
        bucket = 1
    elif score == 1.0:
        bucket = 2
    else:
        bucket = 2

    conf_key = (1, 0.0) if confidence is None else (0, confidence)
    return (bucket, conf_key)


@router.get("/annotations/queue", response_model=QueueResponse)
def get_annotation_queue(
    run_id: int,
    dimension_code: str,
    annotator: str = "",
    include_done: bool = False,
    db: Session = Depends(get_db),
):
    """Spec-9：列出待标注 case，按 (judge_score bucket → confidence asc → conv_id asc) 排序。"""
    run = db.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(404, f"eval_run id={run_id} 不存在")

    if dimension_code not in DIMENSION_NAMES:
        raise HTTPException(400, f"dimension_code='{dimension_code}' 不合法")

    # 拉该 run 的所有 case_result（按 conversation_id 升序，作为稳定排序的 tiebreaker）
    cases = (
        db.query(EvalCaseResult)
        .filter(EvalCaseResult.eval_run_id == run_id)
        .order_by(EvalCaseResult.conversation_id.asc())
        .all()
    )
    if not cases:
        return QueueResponse(
            items=[], total=0,
            dimension_code=dimension_code,
            dimension_name=DIMENSION_NAMES[dimension_code],
        )

    # 拉 conversation map
    conv_ids = [c.conversation_id for c in cases]
    convs: dict[int, Conversation] = {
        c.id: c
        for c in db.query(Conversation).filter(Conversation.id.in_(conv_ids)).all()
    }

    # 拉 turns（按 conv 分组）
    turns_by_conv: dict[int, list[Turn]] = defaultdict(list)
    for t in (
        db.query(Turn)
        .filter(Turn.conversation_id.in_(conv_ids))
        .order_by(Turn.conversation_id.asc(), Turn.turn_index.asc())
        .all()
    ):
        turns_by_conv[t.conversation_id].append(t)

    # 拉 bot_rewrite（key=turn_id）
    rewrites_by_turn: dict[int, BotRewrite] = {}
    all_turn_ids = [t.id for ts in turns_by_conv.values() for t in ts]
    if all_turn_ids:
        for r in (
            db.query(BotRewrite)
            .filter(
                BotRewrite.turn_id.in_(all_turn_ids),
                BotRewrite.bot_version_id == run.bot_version_id,
            )
            .all()
        ):
            rewrites_by_turn[r.turn_id] = r

    # 拉 turn_results，按 case_id+dim 分组
    case_ids = [c.id for c in cases]
    turn_results_by_case_dim: dict[tuple[int, str], list[EvalTurnResult]] = defaultdict(list)
    if case_ids:
        for tr in (
            db.query(EvalTurnResult)
            .filter(
                EvalTurnResult.eval_case_result_id.in_(case_ids),
                EvalTurnResult.dimension_code == dimension_code,
            )
            .order_by(EvalTurnResult.eval_case_result_id.asc(), EvalTurnResult.turn_index.asc())
            .all()
        ):
            turn_results_by_case_dim[(tr.eval_case_result_id, tr.dimension_code)].append(tr)

    # 拉 existing annotation map（per annotator）
    existing_anno: dict[int, HumanAnnotation] = {}
    if annotator:
        for ha in (
            db.query(HumanAnnotation)
            .filter(
                HumanAnnotation.conversation_id.in_(conv_ids),
                HumanAnnotation.dimension_code == dimension_code,
                HumanAnnotation.annotator == annotator,
            )
            .all()
        ):
            existing_anno[ha.conversation_id] = ha

    items: list[tuple[tuple, QueueItem]] = []
    for case in cases:
        conv = convs.get(case.conversation_id)
        if conv is None:
            continue
        already = existing_anno.get(case.conversation_id)
        if already is not None and not include_done:
            continue

        turn_results_for_dim = {dimension_code: turn_results_by_case_dim.get((case.id, dimension_code), [])}
        judge = _extract_judge_dim_info(case, dimension_code, turn_results_for_dim)

        # 构造 turns
        turn_list: list[QueueTurn] = []
        for t in turns_by_conv.get(case.conversation_id, []):
            rw = rewrites_by_turn.get(t.id)
            turn_list.append(QueueTurn(
                turn_index=t.turn_index,
                user_query=t.user_query,
                rewritten_query=rw.rewritten_query if rw else None,
            ))

        item = QueueItem(
            case_id=case.id,
            conversation_id=case.conversation_id,
            conversation_id_src=conv.conversation_id_src,
            dimension_tag=conv.dimension_tag,
            quality_label=conv.quality_label,
            judge_score=judge["score"],
            judge_applicable=judge["applicable"],
            judge_explanation=judge["explanation"],
            judge_confidence=judge["confidence"],
            judge_raw=judge["raw"] if isinstance(judge["raw"], dict) else None,
            turns=turn_list,
            existing_annotation=AnnotationOut.model_validate(already) if already else None,
        )

        # Spec-9 排序 key
        key = _spec9_order_key(judge["score"], judge["applicable"], judge["confidence"]) + (case.conversation_id,)
        items.append((key, item))

    items.sort(key=lambda x: x[0])

    return QueueResponse(
        items=[it for _, it in items],
        total=len(items),
        dimension_code=dimension_code,
        dimension_name=DIMENSION_NAMES[dimension_code],
    )


# ====================================================================
# CRUD: human_annotation
# ====================================================================


@router.post("/annotations", response_model=AnnotationOut)
def upsert_annotation(payload: AnnotationCreate, db: Session = Depends(get_db)):
    """Spec-10：ON CONFLICT DO UPDATE UPSERT — 同 (conv, dim, annotator) 永远 1 行。"""
    conv = db.get(Conversation, payload.conversation_id)
    if conv is None:
        raise HTTPException(404, f"conversation id={payload.conversation_id} 不存在")

    if payload.dimension_code not in DIMENSION_NAMES:
        raise HTTPException(400, f"dimension_code='{payload.dimension_code}' 不合法")

    if not payload.annotator.strip():
        raise HTTPException(400, "annotator 必填")

    # Spec-11 校验：评分 / 不适用 二选一（跳过不会到这里）
    if payload.is_applicable is False:
        # 不适用：score 应当为 None
        score = None
        applicable = False
    elif payload.score is not None:
        if payload.score not in (0.0, 0.5, 1.0):
            raise HTTPException(400, f"score={payload.score} 必须是 0/0.5/1 之一")
        score = payload.score
        applicable = True if payload.is_applicable is None else payload.is_applicable
    else:
        raise HTTPException(400, "score 与 is_applicable=False 二选一")

    stmt = pg_insert(HumanAnnotation).values(
        conversation_id=payload.conversation_id,
        dimension_code=payload.dimension_code,
        annotator=payload.annotator.strip(),
        score=score,
        is_applicable=applicable,
        comment=payload.comment,
        evidence_text=payload.evidence_text,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_annot_conv_dim_anno",
        set_={
            "score": stmt.excluded.score,
            "is_applicable": stmt.excluded.is_applicable,
            "comment": stmt.excluded.comment,
            "evidence_text": stmt.excluded.evidence_text,
            "updated_at": text("now()"),
        },
    ).returning(HumanAnnotation.id)
    new_id = db.execute(stmt).scalar_one()
    db.commit()

    row = db.get(HumanAnnotation, new_id)
    return AnnotationOut.model_validate(row)


@router.get("/annotations", response_model=list[AnnotationOut])
def list_annotations(
    conversation_id: int | None = None,
    dimension_code: str | None = None,
    annotator: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    q = db.query(HumanAnnotation)
    if conversation_id is not None:
        q = q.filter(HumanAnnotation.conversation_id == conversation_id)
    if dimension_code is not None:
        q = q.filter(HumanAnnotation.dimension_code == dimension_code)
    if annotator is not None:
        q = q.filter(HumanAnnotation.annotator == annotator)
    items = q.order_by(HumanAnnotation.updated_at.desc()).limit(limit).all()
    return [AnnotationOut.model_validate(it) for it in items]


@router.delete("/annotations/{aid}")
def delete_annotation(aid: int, db: Session = Depends(get_db)):
    obj = db.get(HumanAnnotation, aid)
    if obj is None:
        raise HTTPException(404, "annotation not found")
    db.delete(obj)
    db.commit()
    return {"status": "deleted", "id": aid}


# ====================================================================
# Agreement dashboard
# ====================================================================


def _judge_dim_info_for_agreement(
    case: EvalCaseResult, dim: str, turn_appl_map: dict[tuple[int, str], bool | None]
) -> tuple[float | None, bool | None]:
    """提取 judge 在指定 dim 上的 (score, applicable)。

    applicable 优先从 dim_results_full 取；缺失时回退到 turn_results.applicable。
    若 score=None（机评未给分），通常意味着该维度不适用。
    """
    score = getattr(case, f"{dim}_score", None)
    applicable: bool | None = None
    full = case.dim_results_full or {}
    block = full.get(dim) if isinstance(full, dict) else None
    if isinstance(block, dict):
        applicable = block.get("applicable")
    if applicable is None:
        # 回退到 turn-level
        applicable = turn_appl_map.get((case.id, dim))
    # 进一步推断：score=None 且 applicable 未明确，视为 N/A（applicable=False）
    if score is None and applicable is None:
        applicable = False
    return score, applicable


def _build_dim_agreements(
    judge_data: dict[str, list[tuple[float | None, bool | None]]],
    human_data: dict[str, list[tuple[float | None, bool | None]]],
    dim_codes: list[str],
) -> tuple[list[AgreementDim], float | None, float | None, int]:
    """对 6 维分别计算 agreement，并返回 overall 聚合。"""
    dim_outs: list[AgreementDim] = []
    accuracies: list[tuple[float, int]] = []
    kappas: list[tuple[float, int]] = []
    total_n = 0

    for dim in dim_codes:
        jds = judge_data.get(dim, [])
        hms = human_data.get(dim, [])
        n = min(len(jds), len(hms))
        if n == 0:
            dim_outs.append(AgreementDim(
                dim_code=dim,
                dim_name=DIMENSION_NAMES.get(dim, dim),
                accuracy=None, kappa=None,
                confusion_matrix=[[0] * 4 for _ in range(4)],
                sample_size=0,
            ))
            continue
        j_scores = [t[0] for t in jds[:n]]
        j_appl = [t[1] for t in jds[:n]]
        h_scores = [t[0] for t in hms[:n]]
        h_appl = [t[1] for t in hms[:n]]
        result = compute_agreement(j_scores, h_scores, j_appl, h_appl)
        dim_outs.append(AgreementDim(
            dim_code=dim,
            dim_name=DIMENSION_NAMES.get(dim, dim),
            accuracy=result["accuracy"],
            kappa=result["kappa"],
            confusion_matrix=result["confusion_matrix"],
            sample_size=result["sample_size"],
        ))
        if result["accuracy"] is not None:
            accuracies.append((result["accuracy"], result["sample_size"]))
        if result["kappa"] is not None:
            kappas.append((result["kappa"], result["sample_size"]))
        total_n += result["sample_size"]

    def _weighted_avg(pairs: list[tuple[float, int]]) -> float | None:
        if not pairs:
            return None
        w_sum = sum(w for _, w in pairs)
        if w_sum == 0:
            return None
        return round(sum(v * w for v, w in pairs) / w_sum, 4)

    return dim_outs, _weighted_avg(accuracies), _weighted_avg(kappas), total_n


@router.get("/agreement/{run_id}", response_model=AgreementResponse)
def get_agreement(
    run_id: int,
    annotator: str | None = None,
    merge: bool = False,
    db: Session = Depends(get_db),
):
    """Spec-11/12/13：一致率看板。

    - 默认：按 annotator 分组返回每个 annotator 一组 (kappa/accuracy/混淆矩阵)
    - merge=true：把同一 (conv, dim) 多 annotator 标注按众数合并为单一"人工标注"，
      返回一组合并结果（annotator="<merged>"）
    """
    run = db.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(404, f"eval_run id={run_id} 不存在")

    dim_codes: list[str] = run.dimensions_selected or list(DIMENSION_NAMES.keys())

    # 拉该 run 的所有 case
    cases = (
        db.query(EvalCaseResult)
        .filter(EvalCaseResult.eval_run_id == run_id)
        .all()
    )
    if not cases:
        return AgreementResponse(
            run_id=run_id,
            mode="merged" if merge else "per_annotator",
            per_annotator=[],
        )

    case_by_conv: dict[int, EvalCaseResult] = {c.conversation_id: c for c in cases}
    conv_ids = list(case_by_conv.keys())

    # 拉该 run 涉及到的 conv 的所有 annotation
    anno_q = db.query(HumanAnnotation).filter(HumanAnnotation.conversation_id.in_(conv_ids))
    if annotator:
        anno_q = anno_q.filter(HumanAnnotation.annotator == annotator)
    annotations: list[HumanAnnotation] = anno_q.all()

    if not annotations:
        return AgreementResponse(
            run_id=run_id,
            mode="merged" if merge else "per_annotator",
            per_annotator=[],
        )

    # 拉 turn_results 的 applicable，构建 (case_id, dim) → applicable 映射
    case_ids = [c.id for c in cases]
    turn_appl_map: dict[tuple[int, str], bool | None] = {}
    if case_ids:
        for tr in (
            db.query(EvalTurnResult.eval_case_result_id, EvalTurnResult.dimension_code, EvalTurnResult.applicable)
            .filter(EvalTurnResult.eval_case_result_id.in_(case_ids))
            .all()
        ):
            key = (tr[0], tr[1])
            # 任一 turn applicable=True 视为整体 True；全 False 才记 False
            cur = turn_appl_map.get(key)
            if cur is True:
                continue
            if tr[2] is True:
                turn_appl_map[key] = True
            elif cur is None:
                turn_appl_map[key] = tr[2]

    # 预计算 judge 数据：{dim: {conv_id: (score, applicable)}}
    judge_map: dict[str, dict[int, tuple[float | None, bool | None]]] = {
        dim: {} for dim in dim_codes
    }
    for case in cases:
        for dim in dim_codes:
            judge_map[dim][case.conversation_id] = _judge_dim_info_for_agreement(case, dim, turn_appl_map)

    if merge:
        # Spec-13 合并视图：把 (conv, dim) 上多 annotator 标注按众数合并
        # 数据结构：{dim: {conv_id: [(score, appl), ...]}}
        pool: dict[str, dict[int, list[tuple[float | None, bool | None]]]] = defaultdict(lambda: defaultdict(list))
        for ha in annotations:
            if ha.dimension_code not in dim_codes:
                continue
            pool[ha.dimension_code][ha.conversation_id].append((ha.score, ha.is_applicable))

        # 对齐 judge 与 human（merge）
        judge_aligned: dict[str, list[tuple[float | None, bool | None]]] = {}
        human_aligned: dict[str, list[tuple[float | None, bool | None]]] = {}
        for dim in dim_codes:
            merged_map = majority_vote(pool[dim])  # {conv_id: (score, applicable)}
            j_list: list[tuple[float | None, bool | None]] = []
            h_list: list[tuple[float | None, bool | None]] = []
            for cid, h_pair in merged_map.items():
                if h_pair == (None, None):  # abstain 跳过
                    continue
                if cid not in judge_map[dim]:
                    continue
                j_list.append(judge_map[dim][cid])
                h_list.append(h_pair)
            judge_aligned[dim] = j_list
            human_aligned[dim] = h_list

        dim_outs, overall_acc, overall_kappa, total_n = _build_dim_agreements(
            judge_aligned, human_aligned, dim_codes
        )
        return AgreementResponse(
            run_id=run_id,
            mode="merged",
            per_annotator=[
                AgreementAnnotator(
                    annotator="<merged>",
                    dims=dim_outs,
                    overall_accuracy=overall_acc,
                    overall_kappa=overall_kappa,
                    total_sample_size=total_n,
                )
            ],
        )

    # 默认 per_annotator：按 annotator 分组
    by_annotator: dict[str, list[HumanAnnotation]] = defaultdict(list)
    for ha in annotations:
        by_annotator[ha.annotator].append(ha)

    out_annotators: list[AgreementAnnotator] = []
    for ann, items in sorted(by_annotator.items()):
        judge_aligned: dict[str, list[tuple[float | None, bool | None]]] = {dim: [] for dim in dim_codes}
        human_aligned: dict[str, list[tuple[float | None, bool | None]]] = {dim: [] for dim in dim_codes}
        for ha in items:
            if ha.dimension_code not in dim_codes:
                continue
            if ha.conversation_id not in judge_map[ha.dimension_code]:
                continue
            judge_aligned[ha.dimension_code].append(judge_map[ha.dimension_code][ha.conversation_id])
            human_aligned[ha.dimension_code].append((ha.score, ha.is_applicable))

        dim_outs, overall_acc, overall_kappa, total_n = _build_dim_agreements(
            judge_aligned, human_aligned, dim_codes
        )
        out_annotators.append(AgreementAnnotator(
            annotator=ann,
            dims=dim_outs,
            overall_accuracy=overall_acc,
            overall_kappa=overall_kappa,
            total_sample_size=total_n,
        ))

    return AgreementResponse(
        run_id=run_id,
        mode="per_annotator",
        per_annotator=out_annotators,
    )
