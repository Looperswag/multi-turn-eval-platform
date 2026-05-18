"""C.2 回归集 Pydantic schemas。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RegressionSetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class RegressionSetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    created_at: datetime
    item_count: int = 0


class RegressionSetItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    conversation_id: int
    conversation_id_src: str | None = None
    dimension_tag: str | None = None
    source_case_id: int | None = None
    added_at: datetime


class RegressionSetDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    created_at: datetime
    items: list[RegressionSetItemOut]


class RegressionSetAddItems(BaseModel):
    conversation_ids: list[int] = Field(..., min_length=1)
    source_case_id: int | None = None  # 可选：从单个 case 加入时记溯源


class RegressionSetAddItemsResult(BaseModel):
    added: int
    skipped: int
    items: list[RegressionSetItemOut]


class RegressionSetFromBadcases(BaseModel):
    eval_run_id: int
    tag: str = Field(..., min_length=1)


class RegressionSetFromBadcasesResult(BaseModel):
    added: int
    skipped: int
    matched_cases: int
