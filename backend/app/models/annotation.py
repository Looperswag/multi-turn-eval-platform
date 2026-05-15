from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, DateTime, Float, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class HumanAnnotation(Base):
    __tablename__ = "human_annotation"
    # Spec-10：同一 annotator 对同 (conv, dim) 只允许 1 行，UPSERT 覆盖
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "dimension_code", "annotator",
            name="uq_annot_conv_dim_anno",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversation.id", ondelete="CASCADE"), index=True
    )
    dimension_code: Mapped[str] = mapped_column(String(16), index=True)
    annotator: Mapped[str] = mapped_column(String(64), index=True)  # plain string in MVP

    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_applicable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class BadcaseTag(Base):
    __tablename__ = "badcase_tag"
    # B.1 reviewer P1：同一 case 内同名 tag 唯一（避免重复 POST 创建多行）
    __table_args__ = (
        UniqueConstraint(
            "eval_case_result_id", "tag",
            name="uq_badcase_case_tag",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    eval_case_result_id: Mapped[int] = mapped_column(
        ForeignKey("eval_case_result.id", ondelete="CASCADE"), index=True
    )
    tag: Mapped[str] = mapped_column(String(128), index=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    added_to_regression: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
