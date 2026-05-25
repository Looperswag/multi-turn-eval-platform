from datetime import datetime
from sqlalchemy import Boolean, ForeignKey, String, Text, DateTime, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class BotVersion(Base):
    __tablename__ = "bot_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    version_tag: Mapped[str] = mapped_column(String(64))  # "v1-baseline"
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    bot_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    base_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BotRewrite(Base):
    __tablename__ = "bot_rewrite"
    __table_args__ = (UniqueConstraint("turn_id", "bot_version_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    turn_id: Mapped[int] = mapped_column(ForeignKey("turn.id", ondelete="CASCADE"), index=True)
    bot_version_id: Mapped[int] = mapped_column(
        ForeignKey("bot_version.id", ondelete="CASCADE"), index=True
    )
    rewritten_query: Mapped[str | None] = mapped_column(Text, nullable=True)  # 首轮可为 None
    raw_response_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # 线上格式扩展（A.4）：bot 自报的元信息，用于 v5 prompt 做更精准评测
    bot_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    inherited_constraints: Mapped[list | None] = mapped_column(JSON, nullable=True)
    dropped_constraints: Mapped[list | None] = mapped_column(JSON, nullable=True)
    needs_rewrite: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
