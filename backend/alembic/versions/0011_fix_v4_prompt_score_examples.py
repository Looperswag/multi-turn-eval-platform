"""fix v4 prompt output examples — 去掉字面 "score: 0" 的 priming

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-19

诊断：
  dim2 / dim4 / dim5 / dim6 的 prompt 输出 JSON 示例里把 score / overall_score 写成
  字面 0（如 `"score": 0,`），低温采样时 LLM 倾向于把示例值当默认输出，导致大量
  应当 0.5 / 1 的 case 被打成 0。

本次 migration 只更新仍持有"字面 0"写法的 v4 prompt 行——即只命中初始 seed 后未
被人工 clone & edit 过的记录。已被克隆衍生（version_tag != 'v4'）或已被人改过示例
的不动，避免覆盖用户改动。

同步：app/services/eval_engine/prompts_v4_templates.py 与 prompts.py 已改成相同写法。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels = None
depends_on = None


# 待 patch 的 (旧 substring, 新 substring) 对。每条只在 prompt_template 含旧文本时替换。
_PATCHES: list[tuple[str, str, str]] = [
    # dim2: overall_score
    (
        "dim2",
        '"overall_score": 0.0,',
        '"overall_score": <0.0~1.0 之间的实数，代表所有约束召回率均值>,',
    ),
    # dim4: score
    (
        "dim4",
        '"actual_referent_in_rewrite": "改写中实际包含的指向",\n  "score": 0,',
        '"actual_referent_in_rewrite": "改写中实际包含的指向",\n  "score": <0 / 0.5 / 1 之一，按 Step 4 评分规则填写>,',
    ),
    # dim5: rewrite_length + score 一起改（rewrite_length: 0 也是字面 0，但语义上是"字符数"应当让 LLM 自填）
    (
        "dim5",
        '"rewrite_length": 0,\n  "hallucinated_words": [],\n  "score": 0,',
        '"rewrite_length": <改写后 query 的字符数>,\n  "hallucinated_words": [],\n  "score": <0 / 0.5 / 1 之一，按 Step 4 评分规则填写>,',
    ),
    # dim6: score
    (
        "dim6",
        '"evidence": "改写片段"\n    }\n  ],\n  "score": 0,',
        '"evidence": "改写片段"\n    }\n  ],\n  "score": <0 / 0.5 / 1 之一，按 Step 3 评分规则填写>,',
    ),
]


def upgrade() -> None:
    conn = op.get_bind()
    for dim_code, old, new in _PATCHES:
        conn.execute(
            sa.text(
                "UPDATE judge_prompt_version "
                "SET prompt_template = REPLACE(prompt_template, :old, :new), "
                "    updated_at = now() "
                "WHERE dimension_code = :dim "
                "  AND version_tag = 'v4' "
                "  AND position(:old in prompt_template) > 0"
            ),
            {"old": old, "new": new, "dim": dim_code},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for dim_code, old, new in _PATCHES:
        conn.execute(
            sa.text(
                "UPDATE judge_prompt_version "
                "SET prompt_template = REPLACE(prompt_template, :new, :old) "
                "WHERE dimension_code = :dim "
                "  AND version_tag = 'v4' "
                "  AND position(:new in prompt_template) > 0"
            ),
            {"old": old, "new": new, "dim": dim_code},
        )
