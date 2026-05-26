"""Comparison API schemas（plan §8.A.5.1）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DiffPoint(BaseModel):
    field: str
    value_a: Any = None
    value_b: Any = None
    reason: str | None = None


class DiffRunsResult(BaseModel):
    diff_points: list[DiffPoint]
    suggested_type: str | None = None
    run_a_id: int
    run_b_id: int


class MovementCase(BaseModel):
    conversation_id_src: str
    conversation_id: int
    score_a: float | None
    score_b: float | None


class DimensionMovement(BaseModel):
    improved: list[MovementCase]
    regressed: list[MovementCase]


class RunSummary(BaseModel):
    id: int
    name: str
    status: str
    weighted_score: float | None
    pass_rate: float | None
    dataset_id: int
    bot_version_id: int
    judge_model_id: int
    judge_prompt_version_ids: dict
    dimensions_selected: list
    finished_at: str | None


class DimDelta(BaseModel):
    dim_code: str
    dim_name: str
    avg_a: float | None
    avg_b: float | None
    delta: float | None
    chi_square_pvalue: float | None
    # M1.1: bootstrap CI of mean delta（任一组 n<30 时为 None）
    delta_ci_low: float | None = None
    delta_ci_high: float | None = None
    sample_size: int


class ComparisonPayload(BaseModel):
    type: str
    run_a_summary: RunSummary
    run_b_summary: RunSummary
    aligned_count: int
    sample_size: int
    session_movement: DimensionMovement
    dimension_movements: dict[str, DimensionMovement]
    dim_deltas: list[DimDelta]
    # M1.1: 替代错位 kappa——Cohen's d 衡量两 run 分布差距的标准化效应量
    score_distribution_overlap: float | None = None
    computed_at: str | None = None


class ComparisonCreate(BaseModel):
    run_a_id: int
    run_b_id: int
    type: str  # prompt / bot / judge
    name: str | None = None


class ComparisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str | None
    type: str
    run_a_id: int
    run_b_id: int | None
    created_at: datetime
    computed_at: datetime | None
    payload: ComparisonPayload
