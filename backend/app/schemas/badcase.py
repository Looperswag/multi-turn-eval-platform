"""Badcase 钻取页 API schemas（plan §8 B 周 / §9.B.9）。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ====================================================================
# BadcaseTag
# ====================================================================


class BadcaseTagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tag: str
    is_confirmed: bool
    added_to_regression: bool
    notes: str | None
    created_at: datetime


class BadcaseTagCreate(BaseModel):
    tag: str
    notes: str | None = None


class BadcaseTagConfirm(BaseModel):
    is_confirmed: bool


class BadcaseTagRegression(BaseModel):
    added: bool


# ====================================================================
# Badcase 列表
# ====================================================================


class BadcaseListItem(BaseModel):
    case_id: int
    conversation_id: int
    conversation_id_src: str
    weighted_score: float | None
    lowest_dim_code: str | None
    dim_scores: dict[str, float | None]
    tags: list[BadcaseTagOut]
    preview_query: str


class BadcaseFacet(BaseModel):
    tag: str
    count: int


class BadcaseStats(BaseModel):
    total_cases: int
    below_threshold: int
    tagged: int
    confirmed: int


class BadcaseListResponse(BaseModel):
    total: int
    items: list[BadcaseListItem]
    tag_facets: list[BadcaseFacet]
    stats: BadcaseStats


# ====================================================================
# Case 完整钻取
# ====================================================================


class CaseFullTurn(BaseModel):
    turn_index: int
    user_query: str
    rewritten_query: str | None = None
    timestamp: str | None = None


class CaseFullTurnResult(BaseModel):
    turn_index: int
    dimension_code: str
    score: float | None
    applicable: bool | None
    judge_raw_response: dict | None


class CaseConversationMeta(BaseModel):
    dimension_tag: str | None
    quality_label: str | None
    issue_type: str | None


class CaseFullDetail(BaseModel):
    case_id: int
    conversation_id: int
    conversation_id_src: str
    weighted_score: float | None
    lowest_dim_code: str | None
    dim_scores: dict[str, float | None]
    turns: list[CaseFullTurn]
    dim_results_full: dict
    turn_results: list[CaseFullTurnResult]
    tags: list[BadcaseTagOut]
    conversation_meta: CaseConversationMeta
