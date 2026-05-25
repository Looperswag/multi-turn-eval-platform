from datetime import datetime
from sqlalchemy import Boolean, ForeignKey, Index, String, Text, DateTime, Float, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class JudgePromptVersion(Base):
    __tablename__ = "judge_prompt_version"
    __table_args__ = (
        UniqueConstraint("dimension_code", "version_tag"),
        Index("ix_prompt_dim_active", "dimension_code", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dimension_code: Mapped[str] = mapped_column(String(16), index=True)  # dim1..dim6
    version_tag: Mapped[str] = mapped_column(String(64))  # "v3" / "v4"
    prompt_template: Mapped[str] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # 评估调用策略：per_turn / session_returns_per_turn / session_single_score
    # 由 Dim1Dispatcher 等评估器读取以选择对应路径，取代基于模板嗅探的脆弱路由。
    dimension_strategy: Mapped[str] = mapped_column(
        String(64), default="per_turn", server_default="per_turn"
    )
    parent_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("judge_prompt_version.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=func.now(),
    )


class JudgeModel(Base):
    __tablename__ = "judge_model"
    __table_args__ = (UniqueConstraint("provider", "model_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))  # 展示用
    provider: Mapped[str] = mapped_column(String(32))  # ark/anthropic/openai
    model_id: Mapped[str] = mapped_column(String(128))
    temperature: Mapped[float] = mapped_column(Float, default=0.1)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
