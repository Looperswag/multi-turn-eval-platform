"""C.2 回归集（regression_set + regression_set_item）+ eval_run.regression_set_id

附带：整合 A.2.3 deferred —— 给 eval_run.judge_prompt_version_ids 加 GIN 索引，
提升 _runs_referencing_prompt 的扫描性能。

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------- regression_set ----------
    op.create_table(
        "regression_set",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_regression_set_name", "regression_set", ["name"]
    )

    # ---------- regression_set_item ----------
    op.create_table(
        "regression_set_item",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "regression_set_id",
            sa.Integer,
            sa.ForeignKey("regression_set.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            sa.Integer,
            sa.ForeignKey("conversation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_case_id",
            sa.Integer,
            sa.ForeignKey("eval_case_result.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "added_at",
            sa.DateTime,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "regression_set_id", "conversation_id",
            name="uq_regression_set_conv",
        ),
    )
    op.create_index(
        "ix_regression_set_item_set", "regression_set_item", ["regression_set_id"]
    )
    op.create_index(
        "ix_regression_set_item_conv", "regression_set_item", ["conversation_id"]
    )
    op.create_index(
        "ix_regression_set_item_src_case", "regression_set_item", ["source_case_id"]
    )

    # ---------- eval_run.regression_set_id ----------
    op.add_column(
        "eval_run",
        sa.Column(
            "regression_set_id",
            sa.Integer,
            sa.ForeignKey("regression_set.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_eval_run_regression_set", "eval_run", ["regression_set_id"]
    )

    # ---------- A.2.3 deferred：GIN 索引（提速 _runs_referencing_prompt）----------
    # 列原本是 json（非 jsonb），GIN 没有默认 op class，所以用表达式索引转 jsonb。
    # 查询侧需用 `(judge_prompt_version_ids::jsonb) @> '{"dimX": id}'` 才能命中。
    op.execute(
        "CREATE INDEX ix_eval_run_judge_prompt_gin "
        "ON eval_run USING GIN ((judge_prompt_version_ids::jsonb) jsonb_path_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_eval_run_judge_prompt_gin")
    op.drop_index("ix_eval_run_regression_set", table_name="eval_run")
    op.drop_column("eval_run", "regression_set_id")

    op.drop_index("ix_regression_set_item_src_case", table_name="regression_set_item")
    op.drop_index("ix_regression_set_item_conv", table_name="regression_set_item")
    op.drop_index("ix_regression_set_item_set", table_name="regression_set_item")
    op.drop_table("regression_set_item")

    op.drop_index("ix_regression_set_name", table_name="regression_set")
    op.drop_table("regression_set")
