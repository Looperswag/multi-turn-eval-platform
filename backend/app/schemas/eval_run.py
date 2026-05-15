from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class EvalRunCreate(BaseModel):
    name: str
    description: str | None = None
    dataset_id: int
    bot_version_id: int
    judge_model_id: int
    # {dim1: prompt_version_id, dim2: ...}
    judge_prompt_version_ids: dict[str, int]
    dimensions_selected: list[str] = Field(
        default_factory=lambda: ["dim1", "dim2", "dim3", "dim4", "dim5", "dim6"]
    )
    concurrency: int = 5
    sampling_count: int | None = None
    baseline_run_id: int | None = None


class EvalRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    status: str
    dataset_id: int
    bot_version_id: int
    judge_model_id: int
    judge_prompt_version_ids: dict
    dimensions_selected: list
    total: int
    completed: int
    failed: int
    weighted_score: float | None
    pass_rate: float | None
    baseline_run_id: int | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class DimensionSummary(BaseModel):
    dimension_code: str
    dimension_name: str
    avg_score: float | None
    sample_count: int
    pass_count: int
    pass_rate: float | None
    min_score: float | None
    max_score: float | None


class EvalRunDashboard(BaseModel):
    run: EvalRunOut
    dimension_summary: list[DimensionSummary]
    score_distribution: dict[str, int]  # bucket -> count


# ===== B.2 dimension slice =====

class DimensionPromptInfo(BaseModel):
    id: int
    version_tag: str
    notes: str | None = None


class DimensionStats(BaseModel):
    total_cases: int
    applicable_count: int
    trigger_rate: float | None
    avg_score: float | None
    min_score: float | None
    max_score: float | None
    pass_count: int
    pass_rate: float | None


class DimensionHistBucket(BaseModel):
    bucket: str
    count: int


class DimensionTopBadcase(BaseModel):
    case_id: int
    conversation_id_src: str
    dim_score: float | None
    weighted_score: float | None
    explanation: str | None


class DimensionIssueCluster(BaseModel):
    key: str
    count: int


class DimensionSliceResponse(BaseModel):
    dim_code: str
    dim_name: str
    weight: float
    prompt_version: DimensionPromptInfo | None
    stats: DimensionStats
    histogram: list[DimensionHistBucket]
    top_badcases: list[DimensionTopBadcase]
    issue_clusters: list[DimensionIssueCluster]
