from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, DateTime, Float, Integer, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class EvalRun(Base):
    __tablename__ = "eval_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    # pending / running / success / partial / failed / cancelled

    dataset_id: Mapped[int] = mapped_column(ForeignKey("dataset.id"), index=True)
    bot_version_id: Mapped[int] = mapped_column(ForeignKey("bot_version.id"), index=True)
    judge_model_id: Mapped[int] = mapped_column(ForeignKey("judge_model.id"), index=True)

    # {dim1: prompt_version_id, dim2: ..., ...}
    judge_prompt_version_ids: Mapped[dict] = mapped_column(JSON)
    dimensions_selected: Mapped[list] = mapped_column(JSON)  # ["dim1","dim2",...]

    concurrency: Mapped[int] = mapped_column(Integer, default=5)
    sampling_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    total: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)

    weighted_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    pass_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    baseline_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("eval_run.id"), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    case_results: Mapped[list["EvalCaseResult"]] = relationship(
        back_populates="eval_run", cascade="all, delete-orphan",
        foreign_keys="EvalCaseResult.eval_run_id",
    )


class EvalCaseResult(Base):
    __tablename__ = "eval_case_result"
    __table_args__ = (UniqueConstraint("eval_run_id", "conversation_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    eval_run_id: Mapped[int] = mapped_column(ForeignKey("eval_run.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversation.id"), index=True)

    weighted_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    lowest_dim_code: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # 维度得分宽列（dashboard 高性能查询用）
    dim1_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    dim2_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    dim3_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    dim4_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    dim5_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    dim6_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 完整 judge raw response（含 explanation / applicable / confidence）
    dim_results_full: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    eval_run: Mapped[EvalRun] = relationship(back_populates="case_results", foreign_keys=[eval_run_id])
    turn_results: Mapped[list["EvalTurnResult"]] = relationship(
        back_populates="case_result", cascade="all, delete-orphan"
    )


class EvalTurnResult(Base):
    __tablename__ = "eval_turn_result"

    id: Mapped[int] = mapped_column(primary_key=True)
    eval_case_result_id: Mapped[int] = mapped_column(
        ForeignKey("eval_case_result.id", ondelete="CASCADE"), index=True
    )
    turn_index: Mapped[int] = mapped_column(Integer)
    dimension_code: Mapped[str] = mapped_column(String(16), index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    applicable: Mapped[bool | None] = mapped_column(nullable=True)
    judge_raw_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    case_result: Mapped[EvalCaseResult] = relationship(back_populates="turn_results")
