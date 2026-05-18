"""A.2.2 deferred：judge_model.is_default 部分唯一索引

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-14

C.4 整合 A.2.2 reviewer 的 P2：原方案靠 Python 端在 update_model
保护"同时只有一个 is_default=True"，并发下不可靠。
加 PostgreSQL 部分唯一索引保证 DB 层最终一致。
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 防御：清掉多于一行的 is_default=True（保留最大 id）
    op.execute("""
        UPDATE judge_model SET is_default = false
        WHERE is_default = true
          AND id NOT IN (SELECT MAX(id) FROM judge_model WHERE is_default = true);
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_judge_model_one_default
        ON judge_model (is_default)
        WHERE is_default = true;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_judge_model_one_default;")
