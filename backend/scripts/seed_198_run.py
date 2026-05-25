"""一次性种子：为「198 条线上多轮 Excel」评测准备配置。

幂等：每个对象按唯一键查找，存在则跳过、不存在则插入。

产出：
- JudgeModel(deepseek, deepseek-chat)
- JudgePromptVersion(dim1, version_tag="line_198_v1", session-level, 用户 prompt)
- JudgePromptVersion(dim2, version_tag="line_198_v1", session-level, 用户 prompt)
- BotVersion(name="online-baseline-198", version_tag="online-198-v1")

运行：
  docker compose exec api python -m scripts.seed_198_run
"""
from __future__ import annotations

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.bot import BotVersion
from app.models.judge import JudgeModel, JudgePromptVersion


# ---------------------------------------------------------------------------
# 用户提供的 prompt 文本（原样保留，仅在前后追加 jinja 输入段，让评估器能注入对话）
# ---------------------------------------------------------------------------

# Dim1 是会话级一次性评估：模型看完整 session，按 turn 输出 evaluations[]
# 模板里出现 turns_text / meta_id 这两个关键字，Dim1Dispatcher 会路由到 session 评估器。
DIM1_PROMPT_TEMPLATE = """# role
你是一个 query 改写质量评估专家。你需要判断"改写后的 query"是否忠实地反映了
用户的真实意图,不引入幻觉,并对上下文做出合理处理。


# Step 1: 判定当前轮的导购语境状态

判断 user_query 属于以下 7 类中的哪一类,并输出对应的 boundary_type 与
in_shopping_context 布尔值;

## boundary_type 定义

【in_shopping_context = true】用户当前处于"导购搜索"语境

- normal_shopping: 正常导购意图。query 含品类词、属性词、购买动词或对商品的
  搜索/咨询表达
  典型表达: "推荐一个 1000 以内的吹风机" / "戴森 V12 多少钱" / "买个空气炸锅"

- shopping_resume: 从非导购话题主动恢复购物意图。判定依据:**上一轮为非导购话题**,
  且当前 query **含商品词/品类词/购买动词**
  典型表达: 上一轮"今天天气怎样" → 当轮"那穿什么外套好"

- correction: 用户纠正系统先前的理解。判定依据:含明确否定或纠正表达
  典型表达: "我说的是 X 不是 Y" / "不,我要的是 X" / "你理解错了" / "再用点心"

【in_shopping_context = false】用户当前脱离"导购搜索"语境

- non_shopping: 与导购完全无关的话题(天气、闲聊、新闻、直播、政策、个人状态等)
  典型表达: "今天天气怎么样" / "直播什么时候开" / "最近股市怎么样"

- info_query: 与商品/平台相关,但属于信息获取而非搜索商品的 query
  (活动规则、流程查询、平台政策、客服问题等)
  典型表达: "双十一什么时候开始" / "退货流程是什么" / "运费险怎么用" /
  "我的订单到哪了"

- emotion_negative: 情绪发泄、辱骂、抗拒表达。判定依据:含负面情绪指向,
  非中性词汇
  典型表达: "滚" / "闭嘴" / "累了" / "你真笨" / 辱骂内容

- meaningless: 无意义输入,无法识别意图。判定依据:单字/字符乱组/无完整语义
  典型表达: "?" / "asdf" / "嗯" / "。。。" / 键盘乱按

## 关键消歧规则

⚠️ shopping_resume vs normal_shopping: 看**上一轮**是否为非导购话题。
   如果是,且当轮含商品词 → shopping_resume;否则 → normal_shopping

⚠️ emotion_negative vs meaningless: 看是否有明确负面情绪指向。
   "滚""闭嘴" 有情绪指向 → emotion_negative;
   "?""asdf" 纯无意义 → meaningless

⚠️ correction vs normal_shopping: 看是否含明确否定/纠正词
   ("不是""不要""我说的是""不对") → correction;否则 → normal_shopping

⚠️ "滚""闭嘴" 等词在情绪语境下不要按字面理解为商品词
   (例: "滚" ≠ "滚筒洗衣机";"闭嘴" 不是商品)

⚠️ info_query vs non_shopping: 涉及商品/订单/平台规则但用户在问信息 → info_query
   (例:"双十一什么时候开始" 是 info_query 不是 non_shopping)

# Step 2:维度 A —— 用户原话保留完整性

判定"改写是否如实表达了用户当前轮的真实意图":

A=1 的条件(全部满足):
- 核心语义单元(品类词、品牌名、数字、硬属性)在改写中保留
- 用户明确否定的内容("不是 X""不要 X")在改写中已排除

A=0:核心语义缺失,或用户明确否定的词仍出现在改写中

允许的合理省略(不扣分):
① 语气/冗余词省略("那种""一点的""好"作语气助词)
② 语义等价压缩("通量大不用等" → "大通量")
③ 属性词被材质/型号隐含("不锈钢材质" → "不锈钢饮水机")
④ 格式标准化("尺码 S" → "S 码";"200 块" → "200 元")
⑤ 合理品类名整合("能拖地的" → "扫拖一体")
⑥ 选择连词替代("旋转式还是平板的好" → "旋转式和平板式对比")
⑦ 度量词被具体数值隐含("容量 300L" → "300L";"预算 500 以内" → "500 以内")

# Step 3:维度 B —— 是否引入幻觉

改写中的每个实词,必须能在以下来源找到证据:

证据来源:
1. 当前 user_query 原文
2. 历史对话中用户曾说过的内容 —— ⚠️ 仅当 in_shopping_context=true 时可作为依据
3. 从用户表述可直接推导的行业标准表达(如"扫拖一体"由"扫地机器人 + 能拖地"推导)
4. 性别/人群等价形态("女" ↔ "女士" ↔ "女款";"儿童" ↔ "童" ↔ "宝宝")
5. 语序重组的表面新词("瑜伽裤女" → "女士瑜伽裤")

B=0 的情况:
- 引入用户从未表达、也无法推导的具体属性(材质参数、认证标准、保修年限)
- in_shopping_context=false 时,改写却拼接了历史中的商品词/品类词
  例:"今天上海天气" → "今天上海天气 牛仔裤" / "滚" → "滚筒洗衣机"
- 改写中残留用户已明确否定的项
  例:用户说"我说的是吊顶不是地板",改写仍含"地板灯"

# Step 4:维度 C —— 上下文补全合理性

【in_shopping_context = true】
C1 - 补全方向:
- 补语型 query(如"海尔或美的""200 以内") → 应补历史核心品类和关键约束
- shopping_resume(如"那穿什么外套好") → 应补全历史上下文
- 完整 query → 不应过度扩展无关属性

C2 - 跨轮品牌/品类保留(重点):
- 用户历史明确指定品牌,本轮未显式切换品类/品牌 → 应保留品牌
- "品类切换"判定:用户说了与原品类无关的完整新品类词
  * "优衣库男士衬衫" → "看看裤子":品牌跨品类适用,应保留 → 未保留 = C=0
  * "兰蔻小黑瓶" → "50ml 多少钱":仍在同一产品,必须保留 → 未保留 = C=0

C1 与 C2 任一不合理 → C=0

【in_shopping_context = false】
C=1:改写未补全历史导购上下文
C=0:改写拼接了历史品类/品牌

# Step 5:综合得分

overall_score = A × B × C(乘积,三项均 1 才能拿满分)

# 输入数据
meta_id: {{ meta_id }}
total_turns: {{ total_turns }}
完整对话序列(按 turn_index 升序):
{{ turns_text }}

# 输出格式
严格输出 JSON，不要输出 Markdown，不要解释 JSON 之外的内容。

{
    "meta_id": "string",
    "total_turns": n,
    "total_score": 0.75,
    "evaluations": [{
        "record_id": "string",
        "turn_index": 1,
        "boundary_type": "...",
        "timestamp": "YYYY-MM-DD HH:MM:SS",
        "user_query": "string",
        "rewritten_query": "string",
        "in_shopping_context": true,
        "A_completeness": 0,
        "A_reasoning": "50字内",
        "B_no_hallucination": 0,
        "B_引入的幻觉词": [],
        "C_reasonable_completion": 0,
        "C_reasoning": "50字内,明确说明品牌是否应保留",
        "overall_score": 0,
        "overall_explanation": "100字内简要说明",
        "confidence": "high"
    }]
}

要求：
- evaluations 数组长度必须等于 total_turns。
- evaluations 中每个元素对应输入 turns 中的一个轮次。
- overall_score = A_completeness × B_no_hallucination × C_reasonable_completion，只能是 0 或 1。
- total_score = 所有 evaluations.overall_score 的平均分。
- total_score 必须输出在顶层，与 meta_id、total_turns 同级。
- total_score 必须是数字类型，不要输出字符串。
- confidence 只能是 high、medium、low。
- 理由要简短、具体，不要复述规则。


# 评估要求：
- 输入中的 turns 是同一个 meta_id 下的完整多轮对话。
- 你需要按照 turn_index 从小到大，逐轮评估每一轮。
- 对第 N 轮进行评估时，只能使用：
  1. 当前轮 user_query
  2. 当前轮 rewritten_query
  3. 当前轮之前的历史 user_query
  4. 可由用户表述直接推导的行业标准表达
- 严禁使用当前轮之后的未来轮次作为判断依据。
- 历史 rewritten_query 不作为事实证据，避免历史错误改写污染后续判断。
- 输出结果数量必须等于 total_turns。

# 特殊规则：首轮无改写
- 当 turn_index = 1 时，rewritten_query = null/(无改写)/(首轮无改写) 符合预期。
- 对首轮数据：
  - 若 rewritten_query 为空，则直接视为通过。
  - A_completeness = 1，A_reasoning = "首轮无需改写"。
  - B_no_hallucination = 1，B_引入的幻觉词 = []。
  - C_reasonable_completion = 1，C_reasoning = "首轮无上下文"。
  - overall_score = 1。
  - confidence = "high"。
- 当 turn_index > 1 时，rewritten_query 为空不能直接视为通过；需根据当前 query 是否完整、是否依赖历史上下文判断。
"""


DIM2_PROMPT_TEMPLATE = """# role
你是一个多轮对话改写质量评估专家，专门评估"用户约束在多轮改写中的保留情况"。


# 评估流程

## Step 1：识别约束（输出 reasoning_step1）

从所有 user_query 中抽取约束。约束分三类：

【核心约束 / 权重 2】
- 品类名（"笔记本电脑"、"洗发水"）
- 品牌名（"欧莱雅"、"戴森"）
- 价格范围（"5000 以内"、"预算 8000"）
- 硬属性规格（"16GB 内存"、"50 寸"、"无线"）

【辅助约束 / 权重 1】
- 使用场景（"办公"、"户外"）
- 目标人群（"70 岁爸爸"、"女朋友"）
- 功能偏好（"控油"、"轻薄"、"续航长"）

【叙事性 / 权重 0，不纳入评分】
- 情绪表达（"想给爸爸惊喜"、"很纠结"）
- 购买原因（"因为旧的坏了"）
- 问题描述（"不知道选哪个好"）

⚠️ 粒度规则：品类取**用户实际说出的粒度**。例如说"控油洗发水"则 category="控油洗发水"，soft_pref 不再单列"控油"；说"洗发水...要控油"则拆为 category="洗发水" + soft_pref="控油"。

在 reasoning_step1 里逐条解释：为什么是这个 importance，粒度怎么定的。

## Step 2：判定每个约束的生命周期（输出 reasoning_step2）

对每个约束输出：
- introduced_at: 引入轮次
- invalidated_at: 失效轮次（null 表示一直生效到最后一轮）
- invalidation_reason: "replaced" / "category_switch" / "user_revoked" / null

判定依据：
- **替换 (replaced)**：用户在后续轮明确给出同类型的新值。例：T1 说"预算 5000"，T3 说"我可以加到 8000"→ T1 price 在 T3 被 replaced。
- **品类切换 (category_switch)**：用户从一个独立品类转向另一个独立品类（非关联购）。判定标准：新品类与旧品类**不构成搭配关系**（"笔记本→鼠标" 是搭配，不算切换；"笔记本→洗发水" 是切换）。品类切换会让旧品类的所有附属约束（price/scene/hard_spec/soft_pref）同时失效。
- **用户撤回 (user_revoked)**：用户显式撤回，如"算了不限价格了"。

在 reasoning_step2 里对每个约束的生命周期给出判定依据（引用具体哪一句用户原话）。

## Step 3：检查改写保留情况（输出 reasoning_step3）

对每个约束，should_appear_in_turns = [introduced_at+1, ..., invalidated_at-1]（或到最后一轮）。

逐轮检查 rewritten_query 是否保留该约束。允许的保留形式：
- 字面包含
- 同义词替代（"笔记本电脑" ↔ "笔记本"）
- 数值隐含上位词（"5000 以内" 隐含了"预算"约束）
- **仅辅助约束**允许上位词泛化保留："外公"→"老人"、"在家办公"→"家用" 视同保留

不允许的形式（算丢失）：
- 核心约束的上位词泛化："欧莱雅"→"大牌"、"16GB 内存"→"高配置" 算丢失
- 品类约束被完全省略，即使保留了修饰词："设计 8000 左右"（丢失了"笔记本电脑"）

在 reasoning_step3 里对每轮每个约束说明：保留 / 丢失 / 合理省略，并给出判定依据。

## Step 4：评分

per_constraint_recall = |actually_appeared ∩ should_appear| / |should_appear|
若 |should_appear| == 0：该约束不纳入评分
total_score = Σ(weight_i × recall_i) / Σ(weight_i)，仅对纳入评分的约束求和

## 输出 confidence
- high: 所有约束的识别、生命周期、保留判定都无歧义
- medium: 有 1-2 个约束的生命周期或保留判定存在模糊
- low: 涉及品类是否切换、上位词是否算保留等关键判定无法确定

# Few-shot 示例

【示例 1：价格替换】
输入：
  T1: "想买个降噪耳机，5000 以内" → 改写"5000 以内降噪耳机"
  T2: "加到 8000 也行" → 改写"8000 以内降噪耳机"
约束识别：category="降噪耳机"（权重2，T1引入），price="5000 以内"（权重2，T1引入，T2 replaced），price="8000 以内"（权重2，T2引入）
生命周期：T1 的 price 在 T2 被 replaced，should_appear_in_turns=[]，不纳入评分
total_score = (2×1.0 + 2×1.0) / 4 = 1.0

【示例 2：品类切换冲刷】
输入：
  T1: "笔记本电脑做设计，8000 左右" → "8000 设计笔记本"
  T2: "再推荐个鼠标吧" → "鼠标"
约束识别：category="笔记本电脑"（权重2），scene="做设计"（权重1），price="8000 左右"（权重2）
生命周期：T2 发生 category_switch（鼠标与笔记本可视为搭配但用户用"再推荐个"明确切换主品类），笔记本的所有约束在 T2 失效
should_appear_in_turns 都为空 → 该 case 不扣分

【示例 3：核心约束的上位词丢失】
输入：
  T1: "欧莱雅控油洗发水" → "欧莱雅控油洗发水"
  T2: "适合油头吗" → "控油洗发水"
约束识别：brand="欧莱雅"（权重2），category="控油洗发水"（权重2）
T2 改写丢失了 brand。brand_recall = 0/1 = 0
total_score = (2×0 + 2×1.0) / 4 = 0.5

# 输入数据
meta_id: {{ meta_id }}
完整对话序列（含 user_query / 改写 / bot 元信息）：
{{ turns_text_with_meta }}

# 输出格式（严格 JSON，reasoning 字段在前，结论在后）
{
  "meta_id": "string",
  "reasoning_step1": "50字以内",
  "reasoning_step2": "50字以内",
  "reasoning_step3": "50字以内",
  "extracted_constraints": [
    {"id": "c1", "type": "品类名", "value": "...", "importance": "核心",
     "weight": 2, "introduced_at": 1, "invalidated_at": null, "invalidation_reason": null}
  ],
  "constraint_retention": [
    {"id": "c1", "should_appear_in_turns": [2,3], "actually_appeared_in": [2],
     "recall": 0.5, "missed_at_turns": [3]}
  ],
  "total_score": 0.5,
  "overall_score": 0.5,
  "explanation": "100 字内：哪些核心约束在哪轮丢失"
}

⚠️ 注意：请同时输出 total_score 和 overall_score（两者数值相同），用于和平台 dim2 评估器兼容。
"""


def _get_or_create_judge_model(db) -> JudgeModel:
    obj = (
        db.query(JudgeModel)
        .filter(JudgeModel.provider == "deepseek", JudgeModel.model_id == "deepseek-chat")
        .first()
    )
    if obj:
        print(f"[skip] JudgeModel id={obj.id} deepseek/deepseek-chat already exists")
        return obj
    obj = JudgeModel(
        name="DeepSeek Chat (V3)",
        provider="deepseek",
        model_id="deepseek-chat",
        temperature=0.1,
        is_default=False,
    )
    db.add(obj)
    db.flush()
    print(f"[new ] JudgeModel id={obj.id} deepseek/deepseek-chat created")
    return obj


def _get_or_create_prompt_version(
    db,
    dim_code: str,
    version_tag: str,
    template: str,
    notes: str,
    dimension_strategy: str = "per_turn",
) -> JudgePromptVersion:
    obj = (
        db.query(JudgePromptVersion)
        .filter(
            JudgePromptVersion.dimension_code == dim_code,
            JudgePromptVersion.version_tag == version_tag,
        )
        .first()
    )
    if obj:
        # 模板内容可能在迭代中调整，覆盖一下（幂等）
        obj.prompt_template = template
        obj.notes = notes
        obj.weight = 0.5
        obj.dimension_strategy = dimension_strategy
        db.flush()
        print(f"[upd ] JudgePromptVersion id={obj.id} {dim_code}/{version_tag} (template refreshed)")
        return obj
    obj = JudgePromptVersion(
        dimension_code=dim_code,
        version_tag=version_tag,
        prompt_template=template,
        weight=0.5,
        notes=notes,
        is_active=False,
        dimension_strategy=dimension_strategy,
    )
    db.add(obj)
    db.flush()
    print(f"[new ] JudgePromptVersion id={obj.id} {dim_code}/{version_tag} created")
    return obj


def _get_or_create_bot_version(db) -> BotVersion:
    obj = (
        db.query(BotVersion)
        .filter(BotVersion.version_tag == "online-198-v1")
        .first()
    )
    if obj:
        print(f"[skip] BotVersion id={obj.id} online-198-v1 already exists")
        return obj
    obj = BotVersion(
        name="online-baseline-198",
        version_tag="online-198-v1",
        description="198 条线上多轮 Excel 自带的 rewritten_query 基线",
    )
    db.add(obj)
    db.flush()
    print(f"[new ] BotVersion id={obj.id} online-baseline-198 created")
    return obj


def main():
    db = SessionLocal()
    try:
        jm = _get_or_create_judge_model(db)
        pv1 = _get_or_create_prompt_version(
            db, "dim1", "line_198_v1", DIM1_PROMPT_TEMPLATE,
            "session-level dim1: 用户提供的改写质量评估专家 prompt，一次调用看完整 session 输出 evaluations[]",
            dimension_strategy="session_returns_per_turn",
        )
        pv2 = _get_or_create_prompt_version(
            db, "dim2", "line_198_v1", DIM2_PROMPT_TEMPLATE,
            "session-level dim2: 用户提供的约束保留评估 prompt，权重 2/1/0 三档约束识别",
            dimension_strategy="session_single_score",
        )
        bv = _get_or_create_bot_version(db)
        db.commit()
        print("\n--- ids ---")
        print(f"judge_model_id        = {jm.id}")
        print(f"dim1_prompt_version_id= {pv1.id}")
        print(f"dim2_prompt_version_id= {pv2.id}")
        print(f"bot_version_id        = {bv.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
