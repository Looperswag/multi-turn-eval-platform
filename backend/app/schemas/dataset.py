from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict


class TurnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    turn_index: int
    user_query: str
    timestamp: str | None = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    conversation_id_src: str
    dimension_tag: str | None
    quality_label: str | None
    issue_type: str | None
    total_turns: int


class ConversationDetail(ConversationOut):
    turns: list[TurnOut] = []


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    version: str
    conversation_count: int
    created_at: datetime


class DatasetDetail(DatasetOut):
    conversations: list[ConversationOut] = []


class DatasetCreate(BaseModel):
    name: str
    description: str | None = None
    version: str = "v1"


# --- A.4 上传向导 ---


class FieldMappingPayload(BaseModel):
    conversation_id: str | None = None
    turn_index: str | None = None  # turn_index_source=="timestamp" 时此处为时间戳列名
    user_query: str | None = None
    rewritten_query: str | None = None
    dimension_tag: str | None = None
    quality_label: str | None = None
    issue_type: str | None = None
    turn_index_source: Literal["turn_index", "timestamp"] = "turn_index"


class ValidationIssueOut(BaseModel):
    severity: str
    code: str
    message: str
    count: int
    sample: list[str] = []


class ValidationReportOut(BaseModel):
    issues: list[ValidationIssueOut]
    total_conversations: int
    total_turns: int
    is_passable: bool


class ParseSessionOut(BaseModel):
    parse_session_id: str
    columns: list[str]
    sample_rows: list[dict]
    suggested_mapping: FieldMappingPayload
    format: str
    total_rows: int


class PreviewPayload(BaseModel):
    parse_session_id: str
    mapping: FieldMappingPayload


class PreviewResult(BaseModel):
    validation_report: ValidationReportOut
    preview_conversations: list[dict]


class ConfirmPayload(BaseModel):
    parse_session_id: str
    mapping: FieldMappingPayload
    dataset_name: str
    version: str = "v1"
    description: str | None = None
    attach_bot_version_id: int | None = None
