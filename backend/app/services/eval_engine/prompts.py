"""六大维度判官 Prompt 模板。

W1 阶段从原 multi_turn_eval/prompts.py 平迁。
W2/W3 将改造为 PromptRenderer：从 DB judge_prompt_version 读 template + jinja2 替换。
"""


def build_dim1_prompt(history_turns, current_turn):
    """维度一：改写准确性（逐轮评估）"""
    history_text = ""
    for t in history_turns:
        history_text += f"  第{t['turn_index']}轮 用户query: {t['user_query']}\n"
        if t["rewritten_query"]:
            history_text += f"  第{t['turn_index']}轮 改写query: {t['rewritten_query']}\n"

    prompt = f"""你是一个 query 改写质量评估专家。你需要判断"改写后的 query"是否忠实地反映了用户的真实意图。

# 输入
- 历史对话:
{history_text}
- 当前用户 query: {current_turn['user_query']}
- 改写后的 query: {current_turn['rewritten_query']}

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
2. 历史对话中用户曾经说过的内容
3. 用户明确确认过的 AI 推荐（如"我选 X"中的 X）

如果改写中出现了用户从未说过、也未确认过的具体属性（如材质细节、规格参数、品牌型号），则视为幻觉。
- 无幻觉 → B=1
- 引入了 1 个或多个用户未说过的实词 → B=0
- 同时给出引入的具体词

## 维度 C：上下文补全合理性
判断改写是否合理地补全了上下文主题：
- 如果当前 query 是补语型（"给外公的""杭州哪里有""我要更多"），改写应当补上历史轮次的核心主题
- 如果当前 query 已是完整 query，改写不应过度扩展
- 如果当前 query 是非导购话题（如"今天天气"），改写应保持原样不补任何条件

合理 → C=1，不合理 → C=0

# 输出格式（严格 JSON，不要输出其他内容）
{{
  "A_completeness": 0 或 1,
  "B_no_hallucination": 0 或 1,
  "B_hallucinated_words": [],
  "C_reasonable_completion": 0 或 1,
  "overall_score": 0 或 1,
  "explanation": "50字内简要说明"
}}"""

    return [{"role": "user", "content": prompt}]


def build_dim2_prompt(all_turns):
    """维度二：跨轮记忆保留（会话级评估）"""
    turns_text = ""
    for t in all_turns:
        turns_text += f"  第{t['turn_index']}轮 用户query: {t['user_query']}\n"
        rq = t['rewritten_query'] if t['rewritten_query'] else "(首轮无改写)"
        turns_text += f"  第{t['turn_index']}轮 改写query: {rq}\n\n"

    prompt = f"""你是一个多轮对话记忆保留能力评估专家。你需要判断系统的改写结果是否在多轮中正确保留了用户的关键约束。

# 输入
完整对话序列：
{turns_text}

# 评估流程

## Step 1：识别"持续生效约束"
从用户的全部 query 中提取以下类别的约束：
- 品类约束：用户明确指定的品类名
- 品牌约束：用户明确提及的品牌名
- 价格约束：用户明确表达的价格上下限或范围
- 人群约束：用户明确指定的目标人群
- 场景约束：用户明确表达的使用场景
- 硬属性：用户的自我陈述

注意：仅在用户明确撤回或显式覆盖时，约束才失效。

## Step 2：检查每轮改写中约束的保留情况
对每一轮改写后 query，检查上述约束是否被字面包含或语义合理省略。

## Step 3：评分
对每个约束，统计"应当保留"的轮数和"实际保留"的轮数，计算召回率均值。

# 输出格式（严格 JSON，不要输出其他内容）
{{
  "extracted_constraints": [
    {{"type": "category/brand/price/person/scene/attribute", "value": "约束值", "from_turn": 1, "should_persist_until": 5}}
  ],
  "constraint_retention": [
    {{"constraint": "约束值", "should_appear_in_turns": [2,3,4], "actually_appeared_in": [2,3], "recall": 0.67}}
  ],
  "overall_score": 0.0,
  "explanation": "100字内说明哪些约束丢失"
}}"""

    return [{"role": "user", "content": prompt}]


def build_dim3_prompt(history_turns, current_turn):
    """维度三：意图边界识别（逐轮评估）"""
    history_text = ""
    for t in history_turns[-5:]:
        history_text += f"  第{t['turn_index']}轮 用户query: {t['user_query']}\n"
        if t["rewritten_query"]:
            history_text += f"  第{t['turn_index']}轮 改写query: {t['rewritten_query']}\n"

    prompt = f"""你是一个对话边界处理能力评估专家。你需要判断系统当轮的改写 query 在面对边界输入时是否做出了合理处理。

# 输入
- 历史对话上下文:
{history_text}
- 当前用户 query: {current_turn['user_query']}
- 当轮改写后 query: {current_turn['rewritten_query']}

# 评估流程

## Step 1：识别 query 的边界类型
判断当前 query 属于以下哪一类：
- normal_shopping：正常导购意图（本维度跳过，applicable=false）
- non_shopping：非导购话题（天气、闲聊、新闻、直播、政策等）
- correction：用户纠正系统理解
- emotion_negative：情绪发泄（"滚"、"闭嘴"、"累了"、辱骂）
- meaningless：无意义输入（单字、错别字、键盘乱按）

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
{{
  "applicable": true 或 false,
  "boundary_type": "normal_shopping/non_shopping/correction/emotion_negative/meaningless",
  "processing_appropriate": 0 或 1,
  "issue": "若处理不当则描述具体问题",
  "score": 0 或 1
}}"""

    return [{"role": "user", "content": prompt}]


def build_dim4_prompt(history_turns, current_turn):
    """维度四：指代消解准确性（逐轮评估）"""
    history_text = ""
    for t in history_turns:
        history_text += f"  第{t['turn_index']}轮 用户query: {t['user_query']}\n"
        if t["rewritten_query"]:
            history_text += f"  第{t['turn_index']}轮 改写query: {t['rewritten_query']}\n"

    prompt = f"""你是一个指代消解能力评估专家。你需要判断系统是否正确将用户的指代词解析为具体商品。

# 输入
- 历史对话:
{history_text}
- 当前用户 query: {current_turn['user_query']}
- 系统改写后 query: {current_turn['rewritten_query']}

# 评估流程

## Step 1：识别指代触发词
判断 query 中是否含以下指代信号：
- 序数指代："第N个"、"第N款"、"最后那个"
- 单品指代："它"、"这款"、"这个"、"那个"、"这双"、"这件"
- 回溯指代："之前那个 X"、"刚才的 Y"

如无指代触发词，本维度跳过（输出 applicable=false）。

## Step 2：确定真实指向
根据指代类型确定应当指向的商品。

## Step 3：验证改写结果
检查系统改写后 query：
- 是否包含目标商品的全名或可识别名称
- 是否未指向错误商品
- 是否未将指代词原样保留

## Step 4：评分
- 正确消解 → 1
- 错误消解 → 0
- 未消解（保留指代词）→ 0
- 部分消解 → 0.5

# 输出格式（严格 JSON，不要输出其他内容）
{{
  "applicable": true 或 false,
  "anaphora_type": "ordinal/single/backtrack/none",
  "expected_referent": "应当指向的商品/对象",
  "actual_referent_in_rewrite": "改写中实际包含的指向",
  "score": 0,
  "explanation": "100字内说明"
}}"""

    return [{"role": "user", "content": prompt}]


def build_dim5_prompt(history_turns, current_turn):
    """维度五：重复请求处理（逐轮评估）"""
    history_text = ""
    for t in history_turns:
        history_text += f"  第{t['turn_index']}轮 用户query: {t['user_query']}\n"

    prompt = f"""你是一个重复搜索处理能力评估专家。你需要判断系统在用户发出"重复请求"时是否做出了正确处理。

# 输入
- 历史对话:
{history_text}
- 当前用户 query: {current_turn['user_query']}
- 系统改写后 query: {current_turn['rewritten_query']}

# 评估流程

## Step 1：判断是否为重复请求
检查 query 是否匹配以下模式：
- "更多" / "我要更多" / "再来更多"
- "还有吗" / "还有别的吗" / "其他的呢" / "其它的呢"
- "换一批" / "再来一批" / "再推荐"
- "看看别的" / "有没有别的"

如不属于，本维度跳过（applicable=false）。

## Step 2：识别历史最近的"完整主题"轮次
从历史 query 中倒序找最近一次用户表达完整购物主题的 query。

## Step 3：验证改写结果
合理处理：
- 改写应当复述该轮主题 query 的核心内容
- 改写长度应控制在原始主题 query 长度的 1.2 倍以内
- 改写不应包含用户未在历史中明确说过的具体属性

不合理表现：
- 改写长度爆炸（>30字）
- 引入了大量用户未明说的属性
- 改写完全是 query 原文没有补充主题

## Step 4：评分
- 改写包含主题且长度受控且无幻觉 → 1
- 改写部分正确 → 0.5
- 改写长度爆炸或幻觉严重 → 0
- 改写完全没补主题 → 0

# 输出格式（严格 JSON，不要输出其他内容）
{{
  "applicable": true 或 false,
  "expected_theme_query": "应当复述的历史主题 query",
  "rewrite_length": 0,
  "hallucinated_words": [],
  "score": 0,
  "explanation": "100字内说明"
}}"""

    return [{"role": "user", "content": prompt}]


def build_dim6_prompt(all_turns):
    """维度六：用户纠错响应（跨轮评估）"""
    turns_text = ""
    for t in all_turns:
        turns_text += f"  第{t['turn_index']}轮 用户query: {t['user_query']}\n"
        rq = t['rewritten_query'] if t['rewritten_query'] else "(首轮无改写)"
        turns_text += f"  第{t['turn_index']}轮 改写query: {rq}\n\n"

    prompt = f"""你是一个用户纠错响应评估专家。你需要判断系统的后续改写是否吸收了用户的纠错信号。

# 输入
完整对话序列：
{turns_text}

# 评估流程

## Step 1：识别纠错信号轮次
扫描所有用户 query，标记纠错轮次 T_correct，并提取：
- 显式纠错："我说的是 X 不是 Y" → 错误项=Y，新方向=X
- 隐式纠错："上面推的不好" / "怎么老是推 X" / "再用点心" → 错误项=X
- 否定追加："不要 X" → 错误项=X，新方向隐含为"非 X"

如果未识别到纠错信号，本维度跳过（applicable=false）。

## Step 2：检查后续改写
对 T_correct + 1 到 T_end 的每一轮改写 query 检查：
- 是否还包含错误项？
- 新方向是否被反映？

## Step 3：评分
- 错误项被清除 + 新方向被采纳 → 1
- 错误项被清除但新方向未采纳，或反之 → 0.5
- 错误项继续出现 → 0
- 若纠错信号在最后一轮（无后续可观察） → applicable=false

# 输出格式（严格 JSON，不要输出其他内容）
{{
  "applicable": true 或 false,
  "correction_signals": [
    {{
      "turn": 0,
      "type": "explicit/implicit/negation",
      "wrong_item": "错误项",
      "new_direction": "新方向"
    }}
  ],
  "subsequent_rewrites_check": [
    {{
      "turn": 0,
      "still_contains_wrong": true,
      "reflects_new": false,
      "evidence": "改写片段"
    }}
  ],
  "score": 0,
  "explanation": "100字内总结"
}}"""

    return [{"role": "user", "content": prompt}]
