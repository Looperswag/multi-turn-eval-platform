"""Annotation & Agreement API schemas（plan §8.A.5.2）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


# ====================================================================
# HumanAnnotation
# ====================================================================


class AnnotationCreate(BaseModel):
    """POST /api/annotations 入参。

    Spec-11 三选一：
    - 评分（score=0/0.5/1, is_applicable=True/None）
    - 不适用（score=None, is_applicable=False）
    - 跳过（前端不发请求）
    """
    conversation_id: int
    dimension_code: str
    annotator: str
    score: float | None = None
    is_applicable: bool | None = None
    comment: str | None = None
    evidence_text: str | None = None


class AnnotationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    conversation_id: int
    dimension_code: str
    annotator: str
    score: float | None
    is_applicable: bool | None
    comment: str | None
    evidence_text: str | None
    created_at: datetime
    updated_at: datetime


# ====================================================================
# Annotation queue
# ====================================================================


class QueueTurn(BaseModel):
    turn_index: int
    user_query: str
    rewritten_query: str | None = None


class QueueItem(BaseModel):
    case_id: int
    conversation_id: int
    conversation_id_src: str
    dimension_tag: str | None
    quality_label: str | None
    judge_score: float | None
    judge_applicable: bool | None
    judge_explanation: str | None
    judge_confidence: float | None
    judge_raw: dict | None
    turns: list[QueueTurn]
    existing_annotation: AnnotationOut | None = None


class QueueResponse(BaseModel):
    items: list[QueueItem]
    total: int
    dimension_code: str
    dimension_name: str


# ====================================================================
# Agreement dashboard
# ====================================================================


class AgreementDim(BaseModel):
    dim_code: str
    dim_name: str
    accuracy: float | None
    kappa: float | None
    confusion_matrix: list[list[int]]  # 4×4 [ZERO/HALF/ONE/NA]
    sample_size: int


class AgreementAnnotator(BaseModel):
    annotator: str  # "<merged>" for merge mode
    dims: list[AgreementDim]
    overall_accuracy: float | None
    overall_kappa: float | None
    total_sample_size: int


class AgreementResponse(BaseModel):
    run_id: int
    mode: str  # "per_annotator" | "merged"
    per_annotator: list[AgreementAnnotator]
    levels: list[str] = ["ZERO", "HALF", "ONE", "NA"]
