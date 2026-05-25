"""seed v5 prompts (dim2 + dim6 session-level) — A.4 commit 3

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-20

dim2 改造为「验证 bot 自报 inherited_constraints + 找漏报」的新流程，
dim6 加入 bot_response 上下文，并对照 bot dropped_constraints。

输出 schema 也变化：
- dim2: 不再用 extracted_constraints + constraint_retention，改为
        false_inherited / missed_constraints / correctly_inherited_count / precision / recall / overall_score
- dim6: 不变量 + 加 bot_declared_dropped 字段

evaluator 已经能传 turns_text_with_meta；这里只插入 prompt 行。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels = None
depends_on = None


DIM2_V5 = """你是一个多轮对话记忆保留能力评估专家。本评估的输入包含 bot 自己声明在每轮"继承/丢弃"的约束清单。你的任务是验证 bot 的声明是否真实可信，并发现 bot 漏报的应当保留的约束。

# 输入
完整对话序列（含 user_query、bot 改写、bot 自报继承/丢弃约束、bot 回复）：
{{ turns_text_with_meta }}

# 领域语言校准
- 输入数据来自电商导购真实对话，可能含小众品牌/专业属性词。
- 若实词在 user_query 或 bot 回复中出现过即视为已知词，不算幻觉。

# 评估流程

## Step 1：精确度验证（Precision）
对 bot 在某轮自报的每条 `inherited_constraints`：
- 检查该约束词或语义等价表述是否真的出现在该轮的「改写 query」中
- 若 bot 声称继承了 X 但改写中根本没有 X 的字面或语义表达 → 这是「伪声明」（false_inherited）
- 同时检查 bot 自报的 `dropped_constraints` 是否有被错误丢弃的合法约束（例如用户未撤回、用户未改主题）

## Step 2：召回率验证（Recall）— 找漏报
扫描所有用户 query 中表达过的"应当持续生效"的约束类型（品类、品牌、价格区间、人群、场景、硬属性等），
逐项检查：
- 该约束是否被 bot 在某轮 `inherited_constraints` 显式声明过？
- 该约束是否在用户后续未撤回的情况下，仍然合理地需要保留在后续轮 rewrite 中？

若一条用户约束完全未出现在任何 `inherited_constraints` 中、却本应被继承 → 这是「漏报」（missed_constraint）。

注意：
- 仅在用户明确撤回或主题切换的情况下，约束可以不继承
- bot 主动归纳的人群属性（如"中老年"基于"我给爷爷买"）也视为有效约束

## Step 3：评分
- 设 P = 1 - (false_inherited 条数 / 全部 inherited 声明条数)（若分母为 0，P=1）
- 设 R = 1 - (missed_constraint 条数 / (missed + 实际正确继承的)）（若分母为 0，R=1）
- overall_score = (P + R) / 2，保留 4 位

# 输出格式（严格 JSON，不要输出其他内容）
{
  "false_inherited": [
    {"turn": 2, "claimed_constraint": "约束词", "evidence_in_rewrite": "未出现/部分出现 + 简短说明"}
  ],
  "missed_constraints": [
    {"first_mentioned_turn": 1, "constraint": "约束词", "should_appear_in_turns": [2,3], "actually_inherited_in_turns": []}
  ],
  "correctly_inherited_count": <整数：所有 bot 声明且改写里真有的约束总数>,
  "precision": <0.0~1.0 实数>,
  "recall": <0.0~1.0 实数>,
  "overall_score": <0.0~1.0 实数，等于 (precision + recall) / 2>,
  "explanation": "100字内总结哪些约束被错误声明 / 被漏报"
}"""


DIM6_V5 = """你是一个用户纠错响应评估专家。你需要判断 bot 后续改写是否吸收了用户的纠错信号，并对照 bot 自报的 `dropped_constraints` 验证错误项是否真的被剔除。

# 输入
完整对话序列（含 user_query、bot 改写、bot 自报继承/丢弃约束、bot 回复）：
{{ turns_text_with_meta }}

# 领域语言校准
- 输入数据来自电商导购真实对话，可能含小众品牌/专业属性词。
- 若实词在 user_query 或 bot 回复中出现过即视为已知词，不算幻觉。

# 评估流程

## Step 1：识别纠错信号轮次
扫描所有用户 query，参考上一轮 bot 回复，标记纠错轮次 T_correct，并提取：
- 显式纠错："我说的是 X 不是 Y" → 错误项=Y，新方向=X
- 隐式纠错（针对 bot 上轮回复）："上面推的不好" / "怎么老是推 X" / "再用点心" → 错误项=最近被 bot 推荐的内容
- 否定追加："不要 X" → 错误项=X，新方向隐含为"非 X"
- 选项否定："都不喜欢" → 错误项=bot 提供的所有选项

如果未识别到纠错信号，本维度跳过（applicable=false）。

## Step 2：检查后续改写 + 对照 bot dropped_constraints
对 T_correct + 1 到 T_end 的每一轮：
- bot 自报的 `dropped_constraints` 是否包含"错误项"？（应当包含）
- 实际改写 query 中错误项是否还残留？（不应残留）
- 新方向是否被反映在改写或 inherited_constraints 中？

## Step 3：评分
- 错误项被剔除（bot 主动声明 dropped + 改写中确实无残留）+ 新方向被采纳 → 1
- 错误项被剔除但新方向未采纳，或反之 → 0.5
- 错误项继续出现在改写中（无论 bot 是否声明 dropped）→ 0
- 若纠错信号在最后一轮（无后续可观察）→ applicable=false

# 输出格式（严格 JSON，不要输出其他内容）
{
  "applicable": true 或 false,
  "correction_signals": [
    {
      "turn": 0,
      "type": "explicit/implicit/negation/option_reject",
      "wrong_item": "错误项",
      "new_direction": "新方向"
    }
  ],
  "subsequent_rewrites_check": [
    {
      "turn": 0,
      "still_contains_wrong": true,
      "bot_declared_dropped": true,
      "reflects_new": false,
      "evidence": "改写片段或 bot 声明片段"
    }
  ],
  "score": <0 / 0.5 / 1 之一，按 Step 3 评分规则填写>,
  "explanation": "100字内总结"
}"""


_V5_SESSION_PROMPTS = {
    "dim2": (DIM2_V5, 0.30),
    "dim6": (DIM6_V5, 0.10),
}


def upgrade() -> None:
    conn = op.get_bind()
    for dim_code, (template, weight) in _V5_SESSION_PROMPTS.items():
        conn.execute(
            sa.text(
                "INSERT INTO judge_prompt_version "
                "  (dimension_code, version_tag, prompt_template, weight, notes, "
                "   is_active, created_at, updated_at) "
                "VALUES (:dim, 'v5', :tpl, :w, :notes, true, now(), now()) "
                "ON CONFLICT (dimension_code, version_tag) DO UPDATE "
                "  SET prompt_template = EXCLUDED.prompt_template, "
                "      is_active = true, "
                "      updated_at = now()"
            ),
            {
                "dim": dim_code,
                "tpl": template,
                "w": weight,
                "notes": "A.4 v5：dim2 schema 重构（验证 + 漏报）/ dim6 + dropped_constraints 对照",
            },
        )
        conn.execute(
            sa.text(
                "UPDATE judge_prompt_version "
                "SET is_active = false "
                "WHERE dimension_code = :dim AND version_tag = 'v4'"
            ),
            {"dim": dim_code},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for dim_code in _V5_SESSION_PROMPTS.keys():
        conn.execute(
            sa.text(
                "DELETE FROM judge_prompt_version "
                "WHERE dimension_code = :dim AND version_tag = 'v5'"
            ),
            {"dim": dim_code},
        )
        conn.execute(
            sa.text(
                "UPDATE judge_prompt_version "
                "SET is_active = true "
                "WHERE dimension_code = :dim AND version_tag = 'v4'"
            ),
            {"dim": dim_code},
        )
