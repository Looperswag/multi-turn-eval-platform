"""add eval_call_cost table (M1.5)

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-26

Why:
- 平台跑 1000 条 × N 维 = N000 次 judge 调用没有 token / 金额 dashboard，
  对企业采购是硬伤（LangSmith / Braintrust / Helicone 都默认显示）。
- 每次 judge_client.call() 成功后写一行，eval_runs 看板聚合显示总成本，
  comparison 显示成本 delta。

不在范围内：
- 不回填历史 run 的成本（留 null / 0；只对新 run 起效）
- 不做实时汇率换算（pricing.py 固定 USD_TO_CNY=7.20）
"""
from alembic import op
import sqlalchemy as sa


revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eval_call_cost",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "eval_case_result_id",
            sa.Integer(),
            sa.ForeignKey("eval_case_result.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("dimension_code", sa.String(16), nullable=False, index=True),
        sa.Column("model_id", sa.String(64), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cost_cny", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("eval_call_cost")
