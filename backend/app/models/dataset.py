from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, Integer, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Dataset(Base):
    __tablename__ = "dataset"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(64), default="v1")
    source_file_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversation_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class Conversation(Base):
    __tablename__ = "conversation"
    __table_args__ = (UniqueConstraint("dataset_id", "conversation_id_src"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("dataset.id", ondelete="CASCADE"), index=True)
    conversation_id_src: Mapped[str] = mapped_column(String(128))  # 业务侧 ID, e.g. conv_10001
    dimension_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quality_label: Mapped[str | None] = mapped_column(String(32), nullable=True)  # good/bad
    issue_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    total_turns: Mapped[int] = mapped_column(Integer, default=0)

    dataset: Mapped[Dataset] = relationship(back_populates="conversations")
    turns: Mapped[list["Turn"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Turn.turn_index"
    )


class Turn(Base):
    __tablename__ = "turn"
    __table_args__ = (UniqueConstraint("conversation_id", "turn_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversation.id", ondelete="CASCADE"), index=True
    )
    turn_index: Mapped[int] = mapped_column(Integer)
    user_query: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[str | None] = mapped_column(String(32), nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="turns")
