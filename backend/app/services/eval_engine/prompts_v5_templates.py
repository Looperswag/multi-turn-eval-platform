"""六维 v5 prompt 模板（A.4 改造）。

v5 相对 v4 的关键改动：
- 利用线上 bot 自报的 intent_type / inherited_constraints / dropped_constraints / bot_response
- 领域语言校准：品牌/品类/属性词在 user_query 或 bot_response 出现过即视为已知，不算幻觉
- dim2 由"judge 抽约束 + 算召回率"改为"验证 bot 声明 + 找漏报"（最大改动）
- dim4/5/6 加 bot 回复历史 → 指代/重复请求/纠错检测更准

注意：v5 模板引用了如下 jinja 变量；evaluator._build_ctx 会在 ctx 里都传：
  通用：current_user_query, current_rewritten_query, current_intent_type,
        current_inherited_constraints, current_dropped_constraints,
        current_bot_response, history_text, history_text_with_bot
  dim2/6 session：turns_text, turns_text_with_meta

PromptRenderer 用 StrictUndefined，因此模板里出现的变量必须都被传入；
若 evaluator 取不到该 turn 的元信息，会传空字符串 / 空 list / "未知"。
"""
from __future__ import annotations


# ============================================================================
# 共享：领域语言校准提示（dim1/2/4/5/6 都用）
# ============================================================================

_DOMAIN_NOTE = """# 领域语言校准（重要）
- 输入数据来自电商导购真实对话，可能含小众品牌（如「谜姬」「飞利浦星空」）、
  专业属性（如「铂金液态硅胶」「阔腿牛仔裤」）、外语品牌（如「ZARA」）。
- 若实词出现在「用户当前 query / 历史 user_query / bot 回复 / 改写 query」任意来源中，
  视为「已被引入的已知词」，不能判定为「用户从未说过」的幻觉。
- 仅当改写中的实词在以上所有来源里都查不到时，才视为幻觉。"""


# ============================================================================
# Dim1 改写忠实性 (turn-level)
# ============================================================================

DIM1_TEMPLATE_V5 = """你是一个 query 改写质量评估专家。你需要判断"改写后的 query"是否忠实地反映了用户的真实意图。

# 输入
- 历史对话（含 bot 回复与意图分类）:
{{ history_text_with_bot }}
- 当前用户 query: {{ current_user_query }}
- 改写后的 query: {{ current_rewritten_query }}
- bot 自报本轮意图: {{ current_intent_type }}
- bot 自报本轮回复(节选): {{ current_bot_response }}

""" + _DOMAIN_NOTE + """

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


# ============================================================================
# Dim3 意图边界识别 (turn-level)
# ============================================================================

DIM3_TEMPLATE_V5 = """你是一个对话边界处理能力评估专家。你需要判断系统当轮的改写 query 在面对边界输入时是否做出了合理处理。

# 输入
- 历史对话上下文（含 bot 回复）:
{{ history_text_with_bot }}
- 当前用户 query: {{ current_user_query }}
- 当轮改写后 query: {{ current_rewritten_query }}
- bot 自报本轮意图: {{ current_intent_type }}
- bot 自报本轮回复(节选): {{ current_bot_response }}

""" + _DOMAIN_NOTE + """

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


# ============================================================================
# Dim4 指代消解准确性 (turn-level)
# ============================================================================

DIM4_TEMPLATE_V5 = """你是一个指代消解能力评估专家。你需要判断系统是否正确将用户的指代词解析为具体商品。

# 输入
- 历史对话（含 bot 回复中提到的商品）:
{{ history_text_with_bot }}
- 当前用户 query: {{ current_user_query }}
- 系统改写后 query: {{ current_rewritten_query }}
- bot 自报本轮意图: {{ current_intent_type }}
- bot 自报本轮回复(节选): {{ current_bot_response }}

""" + _DOMAIN_NOTE + """

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


# ============================================================================
# Dim5 重复请求处理 (turn-level)
# ============================================================================

DIM5_TEMPLATE_V5 = """你是一个重复搜索处理能力评估专家。你需要判断系统在用户发出"重复请求"时是否做出了正确处理。

# 输入
- 历史对话（含 bot 回复中推荐过的内容）:
{{ history_text_with_bot }}
- 当前用户 query: {{ current_user_query }}
- 系统改写后 query: {{ current_rewritten_query }}
- bot 自报本轮意图: {{ current_intent_type }}
- bot 自报本轮回复(节选): {{ current_bot_response }}

""" + _DOMAIN_NOTE + """

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


# ============================================================================
# Dim2 跨轮记忆保留 (session-level) — 最大改动
# ============================================================================

DIM2_TEMPLATE_V5 = """你是一个多轮对话记忆保留能力评估专家。本评估的输入包含 bot 自己声明在每轮"继承/丢弃"的约束清单。\
你的任务是验证 bot 的声明是否真实可信，并发现 bot 漏报的应当保留的约束。

# 输入
完整对话序列（含 user_query、bot 改写、bot 自报继承/丢弃约束、bot 回复）：
{{ turns_text_with_meta }}

""" + _DOMAIN_NOTE + """

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


# ============================================================================
# Dim6 用户纠错响应 (session-level)
# ============================================================================

DIM6_TEMPLATE_V5 = """你是一个用户纠错响应评估专家。你需要判断 bot 后续改写是否吸收了用户的纠错信号，\
并对照 bot 自报的 `dropped_constraints` 验证错误项是否真的被剔除。

# 输入
完整对话序列（含 user_query、bot 改写、bot 自报继承/丢弃约束、bot 回复）：
{{ turns_text_with_meta }}

""" + _DOMAIN_NOTE + """

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


ALL_V5_TEMPLATES: dict[str, str] = {
    "dim1": DIM1_TEMPLATE_V5,
    "dim2": DIM2_TEMPLATE_V5,
    "dim3": DIM3_TEMPLATE_V5,
    "dim4": DIM4_TEMPLATE_V5,
    "dim5": DIM5_TEMPLATE_V5,
    "dim6": DIM6_TEMPLATE_V5,
}
