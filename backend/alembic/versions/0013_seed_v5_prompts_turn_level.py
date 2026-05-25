"""seed v5 prompts (dim1/3/4/5 turn-level) — A.4 commit 2

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-20

插入 dim1/3/4/5 的 v5 prompt 版本（dim2/6 留到 0014）。
- 新建 v5 行；同 dim 下 v4 改为 is_active=false，v5 = is_active=true
- 模板内联在本文件，避免 alembic ↔ app code 的 import 链
- downgrade 完整可逆：删 v5 行 + v4 恢复 is_active=true
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels = None
depends_on = None


# 直接复用 prompts_v5_templates.py 的字符串字面值（避免 import app code）
# 注：与 backend/app/services/eval_engine/prompts_v5_templates.py 同步更新

DIM1_V5 = """你是一个 query 改写质量评估专家。你需要判断"改写后的 query"是否忠实地反映了用户的真实意图。

# 输入
- 历史对话（含 bot 回复与意图分类）:
{{ history_text_with_bot }}
- 当前用户 query: {{ current_user_query }}
- 改写后的 query: {{ current_rewritten_query }}
- bot 自报本轮意图: {{ current_intent_type }}
- bot 自报本轮回复(节选): {{ current_bot_response }}

# 领域语言校准（重要）
- 输入数据来自电商导购真实对话，可能含小众品牌（如「谜姬」「飞利浦星空」）、
  专业属性（如「铂金液态硅胶」「阔腿牛仔裤」）、外语品牌（如「ZARA」）。
- 若实词出现在「用户当前 query / 历史 user_query / bot 回复 / 改写 query」任意来源中，
  视为「已被引入的已知词」，不能判定为「用户从未说过」的幻觉。
- 仅当改写中的实词在以上所有来源里都查不到时，才视为幻觉。

# 评估要求

请按以下三个维度独立判断：

## 维度 A：用户原话保留完整性
检查当前用户 query 中的实词（名词、形容词、品类词、品牌词、数字、属性词）是否全部出现在改写结果中。
- 全部保留 → A=1
- 关键词缺失（如品类词、价格数字丢失）→ A=0
- 仅丢失语气词或冗余词 → A=1

## 维度 B：是否引入幻觉
检查改写结果中的每个实词，是否能在以下来源中找到证据：
1. 当前用户 query 原文
2. 历史 user_query 中用户曾经说过的内容
3. 历史 bot 回复中提到过的、用户明确确认/选择的内容（如"我选 X"中的 X）
4. 用户明确确认过的 AI 推荐

若改写中的实词在以上所有来源中都查不到，视为幻觉。
- 无幻觉 → B=1
- 引入了 1 个或多个完全无来源的实词 → B=0
- 同时给出引入的具体词

## 维度 C：上下文补全合理性
判断改写是否合理地补全了上下文主题；**重点参考 bot 自报的 intent_type**：
- intent_type=「商品检索」：rewrite 应合理补全主题与历史持续约束（若 query 是补语型）
- intent_type=「选项点选」：rewrite 应保留点选项 + 沿用近期主题；不必再次补全所有约束
- intent_type=「闲聊 / 非导购 / 闲聊话题」：rewrite 应当保持原样，不要拼接历史品类
- intent_type=「纠错」：rewrite 应反映纠正方向，不能保留被纠正的错误词

合理 → C=1，不合理 → C=0

# 输出格式（严格 JSON，不要输出其他内容）
{
  "A_completeness": 0 或 1,
  "B_no_hallucination": 0 或 1,
  "B_hallucinated_words": [],
  "C_reasonable_completion": 0 或 1,
  "overall_score": <0.0~1.0 之间的实数，等于 (A+B+C)/3>,
  "explanation": "80字内说明，引用具体证据"
}"""


DIM3_V5 = """你是一个对话边界处理能力评估专家。你需要判断系统当轮的改写 query 在面对边界输入时是否做出了合理处理。

# 输入
- 历史对话上下文（含 bot 回复）:
{{ history_text_with_bot }}
- 当前用户 query: {{ current_user_query }}
- 当轮改写后 query: {{ current_rewritten_query }}
- bot 自报本轮意图: {{ current_intent_type }}
- bot 自报本轮回复(节选): {{ current_bot_response }}

# 领域语言校准
- 输入数据来自电商导购真实对话；小众品牌/专业属性词若在 user_query 或 bot 回复中出现过即视为已知。

# 评估流程

## Step 1：识别 query 的边界类型
首先**参考 bot 自报的 intent_type**做初判，然后独立验证：
- normal_shopping：正常导购意图（本维度跳过，applicable=false）
- non_shopping：非导购话题（天气、闲聊、新闻、直播、政策等）
- correction：用户纠正系统理解
- emotion_negative：情绪发泄（"滚"、"闭嘴"、"累了"、辱骂）
- meaningless：无意义输入（单字、错别字、键盘乱按）
- option_selection：在 bot 给出的选项中做点选（如"我选 X"、"第N个"），本维度跳过 applicable=false
  （指代/重复请求由 dim4/dim5 负责评估）

如果 bot 的 intent_type 是「选项点选」或「商品检索」，且你也认为不属于上述边界类型，applicable=false。

## Step 2：评估改写处理合理性

### non_shopping
- 合理：改写保持 query 原样，或仅对当前非导购意图做轻量补全
- 不合理：改写中拼接了上轮的导购品类

### correction
- 合理：改写反映纠正后的意图，且不残留被纠正的错误内容
- 不合理：改写既保留了被纠正的错误词，又叠加了新方向

### emotion_negative
- 合理：改写原样或几乎原样输出，不补任何商品意图
- 不合理：把情绪词理解成商品意图，或拼接历史品类

### meaningless
- 合理：改写原样输出，或谨慎拼接最近主题尝试理解
- 不合理：改写引入大量与短输入无关的属性

## Step 3：评分
处理合理 → 1，处理不合理 → 0。

# 输出格式（严格 JSON，不要输出其他内容）
{
  "applicable": true 或 false,
  "boundary_type": "normal_shopping/non_shopping/correction/emotion_negative/meaningless/option_selection",
  "bot_intent_type_for_reference": "{{ current_intent_type }}",
  "processing_appropriate": 0 或 1,
  "issue": "若处理不当则描述具体问题；否则空字符串",
  "score": <0 或 1（按 Step 3 评分规则填写）>
}"""


DIM4_V5 = """你是一个指代消解能力评估专家。你需要判断系统是否正确将用户的指代词解析为具体商品。

# 输入
- 历史对话（含 bot 回复中提到的商品）:
{{ history_text_with_bot }}
- 当前用户 query: {{ current_user_query }}
- 系统改写后 query: {{ current_rewritten_query }}
- bot 自报本轮意图: {{ current_intent_type }}
- bot 自报本轮回复(节选): {{ current_bot_response }}

# 领域语言校准
- 小众品牌/专业属性词若在 user_query 或 bot 回复中出现过即视为已知，不算幻觉。

# 评估流程

## Step 1：识别指代触发词
判断 query 中是否含以下指代信号：
- 序数指代："第N个"、"第N款"、"最后那个"
- 单品指代："它"、"这款"、"这个"、"那个"、"这双"、"这件"
- 回溯指代："之前那个 X"、"刚才的 Y"
- 选项点选："我选 X"、"我要 Y"（用户在 bot 提供的选项中点选）

如无指代触发词，本维度跳过（输出 applicable=false）。

## Step 2：确定真实指向
**优先参照 bot 上一轮回复中提到的商品/选项**（指代源最常来自 bot 推荐内容），其次参照 user_query 历史。
- 若 bot 上轮回复列出了多个商品，用户说"第N个"则按列出顺序确定指向
- 若 bot 上轮回复列出选项 A/B/C，用户说"我选 A"则指向 A
- 若 user_query 历史中 X 曾被反复讨论，用户说"那个 X"指向最近一次的 X

## Step 3：验证改写结果
检查系统改写后 query：
- 是否包含目标商品/选项的全名或可识别名称
- 是否未指向错误商品
- 是否未将指代词原样保留

## Step 4：评分
- 正确消解 → 1
- 错误消解（指向了错误商品/选项） → 0
- 未消解（保留指代词如"它/这个"） → 0
- 部分消解（包含部分关键词但属性不全） → 0.5

# 输出格式（严格 JSON，不要输出其他内容）
{
  "applicable": true 或 false,
  "anaphora_type": "ordinal/single/backtrack/option_selection/none",
  "expected_referent": "应当指向的商品/对象（结合 bot 回复推导）",
  "actual_referent_in_rewrite": "改写中实际包含的指向",
  "score": <0 / 0.5 / 1 之一，按 Step 4 评分规则填写>,
  "explanation": "100字内说明，注明指代源是 bot 回复还是 user 历史"
}"""


DIM5_V5 = """你是一个重复搜索处理能力评估专家。你需要判断系统在用户发出"重复请求"时是否做出了正确处理。

# 输入
- 历史对话（含 bot 回复中推荐过的内容）:
{{ history_text_with_bot }}
- 当前用户 query: {{ current_user_query }}
- 系统改写后 query: {{ current_rewritten_query }}
- bot 自报本轮意图: {{ current_intent_type }}
- bot 自报本轮回复(节选): {{ current_bot_response }}

# 领域语言校准
- 小众品牌/专业属性词若在 user_query 或 bot 回复中出现过即视为已知，不算幻觉。

# 评估流程

## Step 1：判断是否为重复请求
检查 query 是否匹配以下模式：
- "更多" / "我要更多" / "再来更多"
- "还有吗" / "还有别的吗" / "其他的呢" / "其它的呢"
- "换一批" / "再来一批" / "再推荐"
- "看看别的" / "有没有别的"

如不属于，本维度跳过（applicable=false）。

## Step 2：识别"应当复述的主题"
**优先看 bot 上一轮推荐了什么核心品类/商品**，这是用户"要更多"时想要的同类内容。
若 bot 上一轮回复没有明确推荐，则倒序找最近的用户主题 query。

## Step 3：验证改写结果
合理处理：
- 改写应当复述该主题（来自 bot 上轮推荐 或 用户历史主题）
- 改写长度应控制在原始主题 query 长度的 1.5 倍以内
- 改写不应包含用户未在历史中明确说过、bot 未推荐过的具体属性

不合理表现：
- 改写长度爆炸（>40字 或 引入大量新属性）
- 引入了用户未明说且 bot 未推荐的属性
- 改写完全是 query 原文（"更多"）没有补充主题

## Step 4：评分
- 改写包含主题且长度受控且无幻觉 → 1
- 改写部分正确 → 0.5
- 改写长度爆炸或幻觉严重 → 0
- 改写完全没补主题 → 0

# 输出格式（严格 JSON，不要输出其他内容）
{
  "applicable": true 或 false,
  "expected_theme_source": "bot_reply 或 user_history",
  "expected_theme_query": "应当复述的主题（精炼成一句话）",
  "rewrite_length": <改写后 query 的字符数>,
  "hallucinated_words": [],
  "score": <0 / 0.5 / 1 之一，按 Step 4 评分规则填写>,
  "explanation": "100字内说明"
}"""


_V5_PROMPTS = {
    "dim1": DIM1_V5,
    "dim3": DIM3_V5,
    "dim4": DIM4_V5,
    "dim5": DIM5_V5,
}

_DIM_WEIGHTS = {
    "dim1": 0.30,
    "dim3": 0.10,
    "dim4": 0.10,
    "dim5": 0.10,
}


def upgrade() -> None:
    conn = op.get_bind()
    # 先插入 v5；冲突（已存在 v5）走 ON CONFLICT DO NOTHING 兜底
    for dim_code, template in _V5_PROMPTS.items():
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
                "w": _DIM_WEIGHTS[dim_code],
                "notes": "A.4 v5：利用线上 bot 自报元信息 + 领域语言校准",
            },
        )
        # 同 dim 下 v4 改为 inactive（dim2/6 v4 不动，因为 v5 还没就位）
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
    for dim_code in _V5_PROMPTS.keys():
        # 删 v5（如果没在用）；若被 run 引用则保留 + 标 inactive
        conn.execute(
            sa.text(
                "DELETE FROM judge_prompt_version "
                "WHERE dimension_code = :dim AND version_tag = 'v5'"
            ),
            {"dim": dim_code},
        )
        # 恢复 v4 active
        conn.execute(
            sa.text(
                "UPDATE judge_prompt_version "
                "SET is_active = true "
                "WHERE dimension_code = :dim AND version_tag = 'v4'"
            ),
            {"dim": dim_code},
        )
