"""bot_rewrite: 加入线上格式 bot 自报元信息字段

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-20

A.4 改造：线上抓回的 Excel（`60个对话多轮数据for测评线上最新版本515.xlsx`）含
`llm_resp` JSON 与 `historyquery` 两列，bot 已经声明了 intent_type、
inherited_constraints、dropped_constraints、needs_rewrite 等信号；
另外 historyquery 里的 `#第N轮追问` 是 bot 实际回复，对 dim3/4/5/6 评测有价值。

本次给 bot_rewrite 加 5 个 nullable 字段：
- bot_response (Text)          — bot 在该轮的回复正文（参与 dim3/4/5/6 上下文）
- intent_type (Varchar 32)     — bot 自报的本轮意图（商品检索/选项点选/闲聊/纠错…）
- inherited_constraints (JSON) — bot 自报继承的约束列表（dim2 验证用）
- dropped_constraints (JSON)   — bot 自报丢弃的约束列表（dim2/6 验证用）
- needs_rewrite (Boolean)      — bot 自判该轮是否需要改写

老数据全 NULL，evaluator/exporter 均按 nullable 处理。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels = None
depends_on = None


_NEW_COLUMNS = [
    ("bot_response", sa.Text()),
    ("intent_type", sa.String(32)),
    ("inherited_constraints", sa.JSON()),
    ("dropped_constraints", sa.JSON()),
    ("needs_rewrite", sa.Boolean()),
]


def upgrade() -> None:
    for name, type_ in _NEW_COLUMNS:
        op.add_column("bot_rewrite", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    # 反向按降序删（无依赖顺序，但保持对称）
    for name, _ in reversed(_NEW_COLUMNS):
        op.drop_column("bot_rewrite", name)
