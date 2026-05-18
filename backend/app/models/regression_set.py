"""C.2 回归集（regression set）ORM 模型。

- RegressionSet：人工策划的「必须能跑过」的对话集合
- RegressionSetItem：集合成员（conversation 级别）
  - source_case_id 可选，记录该条最初来自哪个 eval_case_result（便于溯源）
"""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class RegressionSet(Base):
    __tablename__ = "regression_set"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    items: Mapped[list["RegressionSetItem"]] = relationship(
        back_populates="regression_set",
        cascade="all, delete-orphan",
        order_by="RegressionSetItem.added_at.desc()",
    )


class RegressionSetItem(Base):
    __tablename__ = "regression_set_item"
    __table_args__ = (
        UniqueConstraint(
            "regression_set_id", "conversation_id",
            name="uq_regression_set_conv",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    regression_set_id: Mapped[int] = mapped_column(
        ForeignKey("regression_set.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversation.id", ondelete="CASCADE"), index=True
    )
    source_case_id: Mapped[int | None] = mapped_column(
        ForeignKey("eval_case_result.id", ondelete="SET NULL"), nullable=True, index=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    regression_set: Mapped[RegressionSet] = relationship(back_populates="items")
