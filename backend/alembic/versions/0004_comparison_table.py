"""comparison table (A.5.1)

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-14

为对比能力（W1.5 提前合并自原 W3）建表 comparison：
- type ∈ {prompt, bot, judge, human}
- run_a_id / run_b_id 走 ondelete=CASCADE（Spec-9）
- cache_key 检测 run 重跑（Spec-3）
- result_payload 存即时计算结果
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comparison",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255)),
        sa.Column("type", sa.String(16), nullable=False, index=True),
        sa.Column(
            "run_a_id",
            sa.Integer(),
            sa.ForeignKey("eval_run.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "run_b_id",
            sa.Integer(),
            sa.ForeignKey("eval_run.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("cache_key", sa.String(128), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("computed_at", sa.DateTime()),
        sa.UniqueConstraint("run_a_id", "run_b_id", "type", name="uq_comparison_runs_type"),
    )
    op.create_index(
        "ix_comparison_run_a_run_b", "comparison", ["run_a_id", "run_b_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_comparison_run_a_run_b", table_name="comparison")
    op.drop_table("comparison")
