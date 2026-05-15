from datetime import datetime
from pydantic import BaseModel, ConfigDict


class JudgePromptVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    dimension_code: str
    version_tag: str
    weight: float
    notes: str | None
    is_active: bool
    parent_version_id: int | None
    created_at: datetime
    updated_at: datetime


class JudgePromptVersionDetail(JudgePromptVersionOut):
    prompt_template: str


class JudgePromptVersionCreate(BaseModel):
    dimension_code: str
    version_tag: str
    prompt_template: str
    weight: float = 0.0
    notes: str | None = None


class JudgePromptVersionUpdate(BaseModel):
    # 不允许改 dimension_code / version_tag —— 改了等于换身份
    prompt_template: str | None = None
    weight: float | None = None
    notes: str | None = None


class JudgePromptPerformanceItem(BaseModel):
    eval_run_id: int
    run_name: str
    weighted_score: float | None
    dim_score: float | None  # 该 prompt 对应维度的具体分数
    used_at: datetime  # eval_run.started_at 或 created_at fallback


class JudgePromptPerformance(BaseModel):
    prompt_version_id: int
    dimension_code: str
    version_tag: str
    is_active: bool
    in_use_count: int
    avg_weighted_score: float | None
    avg_dim_score: float | None
    items: list[JudgePromptPerformanceItem]


class JudgeModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    provider: str
    model_id: str
    temperature: float
    max_tokens: int | None
    is_default: bool
    created_at: datetime


class JudgeModelCreate(BaseModel):
    name: str
    provider: str = "ark"
    model_id: str
    temperature: float = 0.1
    max_tokens: int | None = None
    is_default: bool = False


class JudgeModelUpdate(BaseModel):
    name: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    is_default: bool | None = None


class JudgeModelTestResult(BaseModel):
    ok: bool
    elapsed_ms: int
    raw_response: str | None = None
    error: str | None = None
    model_id: str
    provider: str


class BotVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    version_tag: str
    description: str | None
    bot_provider: str | None
    base_model: str | None
    created_at: datetime


class BotVersionCreate(BaseModel):
    name: str
    version_tag: str
    description: str | None = None
    bot_provider: str | None = None
    base_model: str | None = None


class BotRewriteDatasetStat(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dataset_id: int
    dataset_name: str
    rewrite_count: int
    total_turns: int


class BotVersionDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    bot_version: BotVersionOut
    rewrite_stats: list[BotRewriteDatasetStat]
