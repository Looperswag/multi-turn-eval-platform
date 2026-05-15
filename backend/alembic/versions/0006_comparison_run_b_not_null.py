"""P1 修复：comparison.run_b_id 改为 NOT NULL

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-14

A.5.1 reviewer 指出：原 nullable=True 与 PostgreSQL UniqueConstraint 语义不一致
(NULL 不参与唯一性判断 → (run_a_id, NULL, type) 多行可绕过约束)。
当前 POST schema 已强制 run_b_id: int，但 model 层须收口。
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 防御：清掉任何 NULL 行（W1.5 阶段实际无）
    op.execute("DELETE FROM comparison WHERE run_b_id IS NULL")
    op.alter_column("comparison", "run_b_id", nullable=False)


def downgrade() -> None:
    op.alter_column("comparison", "run_b_id", nullable=True)
