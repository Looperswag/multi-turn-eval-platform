"""add dimension_strategy column to judge_prompt_version (P0-2)

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-22

Why:
- 此前 Dim1Dispatcher 通过嗅探 prompt 模板字符串里是否含 turns_text/meta_id
  来路由 per-turn vs session-level 评估器；用户改 prompt 删错关键字就会
  路由到错误评估器，体验脆弱。
- 加一个显式枚举列存放策略，Dispatcher 改读字段，prompt CRUD UI 用单选。

策略取值：
- per_turn (默认)：评估器逐轮 N 次调用 judge
- session_returns_per_turn：一次调用 judge 看完整 session、模型按轮输出
- session_single_score：一次调用 judge 看完整 session、单一总分（dim2/dim6 现状）

向后兼容：
- 默认 per_turn → 旧 dim1 prompt 行为不变
- dim2/dim6 老 prompt 默认 per_turn 也无影响，因为它们的评估器代码本来就 session-level
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "judge_prompt_version",
        sa.Column(
            "dimension_strategy",
            sa.String(length=64),
            nullable=False,
            server_default="per_turn",
        ),
    )
    # 自动把 dim2 / dim6 的现有版本标为 session_single_score（它们的评估器就是
    # session-once-with-one-score 模式）。dim1 默认仍是 per_turn；用户的新
    # line_198_v1 prompt 后续显式改成 session_returns_per_turn。
    op.execute(
        "UPDATE judge_prompt_version "
        "SET dimension_strategy='session_single_score' "
        "WHERE dimension_code IN ('dim2', 'dim6')"
    )


def downgrade() -> None:
    op.drop_column("judge_prompt_version", "dimension_strategy")
