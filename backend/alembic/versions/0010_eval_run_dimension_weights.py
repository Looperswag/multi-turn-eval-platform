"""eval_run.dimension_weights：每次评测的维度权重覆盖

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-18

W2：原先 scoring 用 DEFAULT_DIMENSION_WEIGHTS 硬编码，
本次扩展允许 run 自带 weights（NULL 时 fallback 到 DEFAULT）。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "eval_run",
        sa.Column("dimension_weights", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("eval_run", "dimension_weights")
