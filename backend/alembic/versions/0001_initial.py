"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dataset",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("version", sa.String(64), nullable=False, server_default="v1"),
        sa.Column("source_file_uri", sa.Text()),
        sa.Column("conversation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "conversation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("dataset.id", ondelete="CASCADE"), index=True),
        sa.Column("conversation_id_src", sa.String(128), nullable=False),
        sa.Column("dimension_tag", sa.String(64)),
        sa.Column("quality_label", sa.String(32)),
        sa.Column("issue_type", sa.String(128)),
        sa.Column("total_turns", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("dataset_id", "conversation_id_src"),
    )

    op.create_table(
        "turn",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversation.id", ondelete="CASCADE"), index=True),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("user_query", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.String(32)),
        sa.UniqueConstraint("conversation_id", "turn_index"),
    )

    op.create_table(
        "bot_version",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version_tag", sa.String(64), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("bot_provider", sa.String(64)),
        sa.Column("base_model", sa.String(128)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "bot_rewrite",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("turn_id", sa.Integer(), sa.ForeignKey("turn.id", ondelete="CASCADE"), index=True),
        sa.Column("bot_version_id", sa.Integer(), sa.ForeignKey("bot_version.id", ondelete="CASCADE"), index=True),
        sa.Column("rewritten_query", sa.Text()),
        sa.Column("raw_response_meta", sa.JSON()),
        sa.UniqueConstraint("turn_id", "bot_version_id"),
    )

    op.create_table(
        "judge_prompt_version",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dimension_code", sa.String(16), nullable=False, index=True),
        sa.Column("version_tag", sa.String(64), nullable=False),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("dimension_code", "version_tag"),
    )

    op.create_table(
        "judge_model",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model_id", sa.String(128), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("max_tokens", sa.Integer()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "model_id"),
    )

    op.create_table(
        "eval_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending", index=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("dataset.id"), index=True),
        sa.Column("bot_version_id", sa.Integer(), sa.ForeignKey("bot_version.id"), index=True),
        sa.Column("judge_model_id", sa.Integer(), sa.ForeignKey("judge_model.id"), index=True),
        sa.Column("judge_prompt_version_ids", sa.JSON(), nullable=False),
        sa.Column("dimensions_selected", sa.JSON(), nullable=False),
        sa.Column("concurrency", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("sampling_count", sa.Integer()),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("weighted_score", sa.Float()),
        sa.Column("pass_rate", sa.Float()),
        sa.Column("baseline_run_id", sa.Integer(), sa.ForeignKey("eval_run.id")),
        sa.Column("created_by", sa.String(64)),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "eval_case_result",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("eval_run_id", sa.Integer(), sa.ForeignKey("eval_run.id", ondelete="CASCADE"), index=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversation.id"), index=True),
        sa.Column("weighted_score", sa.Float()),
        sa.Column("lowest_dim_code", sa.String(16)),
        sa.Column("dim1_score", sa.Float()),
        sa.Column("dim2_score", sa.Float()),
        sa.Column("dim3_score", sa.Float()),
        sa.Column("dim4_score", sa.Float()),
        sa.Column("dim5_score", sa.Float()),
        sa.Column("dim6_score", sa.Float()),
        sa.Column("dim_results_full", sa.JSON()),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("eval_run_id", "conversation_id"),
    )

    op.create_table(
        "eval_turn_result",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("eval_case_result_id", sa.Integer(), sa.ForeignKey("eval_case_result.id", ondelete="CASCADE"), index=True),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("dimension_code", sa.String(16), nullable=False, index=True),
        sa.Column("score", sa.Float()),
        sa.Column("applicable", sa.Boolean()),
        sa.Column("judge_raw_response", sa.JSON()),
    )

    op.create_table(
        "human_annotation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversation.id", ondelete="CASCADE"), index=True),
        sa.Column("dimension_code", sa.String(16), nullable=False, index=True),
        sa.Column("annotator", sa.String(64), nullable=False, index=True),
        sa.Column("score", sa.Float()),
        sa.Column("is_applicable", sa.Boolean()),
        sa.Column("comment", sa.Text()),
        sa.Column("evidence_text", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "badcase_tag",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("eval_case_result_id", sa.Integer(), sa.ForeignKey("eval_case_result.id", ondelete="CASCADE"), index=True),
        sa.Column("tag", sa.String(128), nullable=False, index=True),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("added_to_regression", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in [
        "badcase_tag",
        "human_annotation",
        "eval_turn_result",
        "eval_case_result",
        "eval_run",
        "judge_model",
        "judge_prompt_version",
        "bot_rewrite",
        "bot_version",
        "turn",
        "conversation",
        "dataset",
    ]:
        op.drop_table(table)
