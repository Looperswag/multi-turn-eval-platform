"""prompt lifecycle: is_active + parent_version_id + updated_at

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "judge_prompt_version",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "judge_prompt_version",
        sa.Column("parent_version_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "judge_prompt_version",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_foreign_key(
        "fk_prompt_parent_version",
        "judge_prompt_version",
        "judge_prompt_version",
        ["parent_version_id"],
        ["id"],
    )
    op.create_index(
        "ix_prompt_dim_active",
        "judge_prompt_version",
        ["dimension_code", "is_active"],
    )

    # 数据迁移：现有 v4 视为每维度当前 active 版本（每维度唯一）
    op.execute("UPDATE judge_prompt_version SET is_active = true WHERE version_tag = 'v4'")


def downgrade() -> None:
    op.drop_index("ix_prompt_dim_active", table_name="judge_prompt_version")
    op.drop_constraint("fk_prompt_parent_version", "judge_prompt_version", type_="foreignkey")
    op.drop_column("judge_prompt_version", "updated_at")
    op.drop_column("judge_prompt_version", "parent_version_id")
    op.drop_column("judge_prompt_version", "is_active")
