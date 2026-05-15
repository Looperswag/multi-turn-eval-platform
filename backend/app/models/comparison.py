"""Comparison ORM 模型：对比两个 eval_run，缓存计算结果。

实现自 plan §8.A.5.1：
- type ∈ {prompt, bot, judge, human}（human 留给 A.5.2 走另一端点）
- run_a / run_b FK ondelete=CASCADE（Spec-9）
- cache_key 用于检测 run 是否被重跑（Spec-3）
- result_payload 存放即时计算的结果（movements / kappa / chi-square）
"""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Comparison(Base):
    __tablename__ = "comparison"
    __table_args__ = (
        UniqueConstraint("run_a_id", "run_b_id", "type", name="uq_comparison_runs_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # prompt / bot / judge / human

    run_a_id: Mapped[int] = mapped_column(
        ForeignKey("eval_run.id", ondelete="CASCADE"), index=True
    )
    # P1 修复（A.5.1 reviewer）：原 nullable=True + PG NULL 不参与 UniqueConstraint
    # 会让 (run_a_id, NULL, type) 重复行绕过约束。POST schema 已要求 int 必填，
    # 但 model 层保持一致：run_b_id 必填，"human vs annotation" 走独立端点。
    run_b_id: Mapped[int] = mapped_column(
        ForeignKey("eval_run.id", ondelete="CASCADE"), index=True, nullable=False
    )

    cache_key: Mapped[str] = mapped_column(String(128), nullable=False)
    result_payload: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    computed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    run_a = relationship("EvalRun", foreign_keys=[run_a_id])
    run_b = relationship("EvalRun", foreign_keys=[run_b_id])
