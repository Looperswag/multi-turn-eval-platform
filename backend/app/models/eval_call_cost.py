"""EvalCallCost：每次 judge 调用的 token + 成本明细。

M1.5 — 用于看板成本卡 + comparison 成本 delta。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class EvalCallCost(Base):
    __tablename__ = "eval_call_cost"

    id: Mapped[int] = mapped_column(primary_key=True)
    eval_case_result_id: Mapped[int] = mapped_column(
        ForeignKey("eval_case_result.id", ondelete="CASCADE"), index=True
    )
    dimension_code: Mapped[str] = mapped_column(String(16), index=True)
    model_id: Mapped[str] = mapped_column(String(64))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    cost_cny: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
