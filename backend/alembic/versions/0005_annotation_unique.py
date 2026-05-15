"""human_annotation unique constraint (A.5.2 Spec-10)

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-14

Spec-10：给 human_annotation 加 UniqueConstraint(conversation_id, dimension_code, annotator)。
- 同一 annotator 对同 (conv, dim) 只允许 1 行
- POST /api/annotations 走 ON CONFLICT DO UPDATE UPSERT
- 防御：先 dedup（保留 max(id) 行），再加约束
"""
from typing import Union

from alembic import op


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 防御：删除重复行（保留 id 最大的，即最新的）
    op.execute(
        """
        DELETE FROM human_annotation a
        USING human_annotation b
        WHERE a.id < b.id
          AND a.conversation_id = b.conversation_id
          AND a.dimension_code  = b.dimension_code
          AND a.annotator       = b.annotator;
        """
    )
    op.create_unique_constraint(
        "uq_annot_conv_dim_anno",
        "human_annotation",
        ["conversation_id", "dimension_code", "annotator"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_annot_conv_dim_anno", "human_annotation", type_="unique"
    )
