"""B.1 reviewer P1：badcase_tag 加 UniqueConstraint(case_id, tag)

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-14
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 防御：先 dedup（保留每组 max(id)）
    op.execute("""
        DELETE FROM badcase_tag a USING badcase_tag b
        WHERE a.id < b.id
          AND a.eval_case_result_id = b.eval_case_result_id
          AND a.tag = b.tag;
    """)
    op.create_unique_constraint(
        "uq_badcase_case_tag",
        "badcase_tag",
        ["eval_case_result_id", "tag"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_badcase_case_tag", "badcase_tag", type_="unique")
