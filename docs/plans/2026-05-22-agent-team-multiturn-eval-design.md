# Agent Team 多轮评测平台设计

日期：2026-05-22
状态：已确认采用方案二：Agent Team 分工评审

## 目标

平台需要从 session 维度评判「多轮评测平台」能力，并支持两类核心评分粒度：

- 维度一「改写忠实性」：输入完整 session，每个非首轮 query 输出一个分数，首轮只作为上下文。
- 维度二「跨轮记忆保留」：输入完整 session，每个 session 只输出一个分数，不提供 query 粒度评分。

最终输出以 session 为核心：展示 session 加权总分、每个维度的 session 粒度分数、分析概览和 badcase。维度一可下钻到 query 级分数与 badcase 分析；维度二不可展开到 query 级分数，只展示 session 级约束保留证据。

## 推荐方案

采用「Agent Team 分工评审 + 审计/聚合层」。

不采用单 Judge 的原因：

- 单 Judge 难以同时保证 session 级排序、turn 级评分、维度粒度差异和 badcase 证据链。
- 维度一和维度二的评分对象不同，强行合并会让 UI、导出和统计口径变模糊。
- 平台需要可追责结果，而不是只输出一个总分。

不优先采用多模型辩论委员会的原因：

- 可信度更高，但成本和延迟明显上升。
- 当前阶段更需要先把数据粒度、评分口径和产品下钻能力固定下来。

## Agent Team

### 1. Session Builder Agent

职责：

- 将同一个 `meta_id` 聚合为一个 session。
- 同一 `meta_id` 内按 `gmt_create` 升序排列。
- 若 `gmt_create` 相同，用原始行号作为稳定 tie-breaker。
- 派生连续 `turn_index = 1..N`。
- 保留原始 `meta_id`、`gmt_create`、原始行号，便于审计。

输出 `SessionPacket`：

```json
{
  "meta_id": "session_xxx",
  "turns": [
    {
      "turn_index": 1,
      "gmt_create": "2026-05-22 10:00:00",
      "user_query": "...",
      "rewritten_query": null,
      "source_row": 12
    }
  ]
}
```

### 2. Data Quality Agent

职责：

- 检查 `meta_id`、`gmt_create`、`user_query`、`rewritten_query` 必要字段。
- 检查首轮无改写是否符合预期。
- 检查同一 session 内是否有重复轮次、异常时间倒序、空 query、rewrite 错位。
- 标记 `data_quality_flags`，但非致命问题不阻断评测。

典型输出：

```json
{
  "is_passable": true,
  "flags": [
    {"level": "info", "code": "first_turn_no_rewrite", "turn_index": 1},
    {"level": "warning", "code": "same_timestamp", "turn_index": 3}
  ]
}
```

### 3. Dim1 Rewrite Fidelity Agent

职责：

- 评估维度一「改写忠实性」。
- 输入完整 session 和 `target_turn`。
- 首轮不评分，只作为上下文。
- 每个非首轮输出一个 query 级分数和 badcase 解释。

评分口径：

- A：用户原话保留完整性。
- B：是否无幻觉。
- C：上下文补全合理性。
- `overall_score = A * B * C`。

注意：这里必须使用乘法门槛。任一子项失败，当前 query 的维度一得分为 0，避免平均分掩盖严重错误。

输出：

```json
{
  "turn_index": 3,
  "A_completeness": 1,
  "B_no_hallucination": 0,
  "B_hallucinated_words": ["FAS级", "8年质保"],
  "C_reasonable_completion": 1,
  "overall_score": 0,
  "explanation": "改写加入用户未表达的材质认证和质保信息"
}
```

### 4. Dim2 Memory Retention Agent

职责：

- 评估维度二「跨轮记忆保留」。
- 输入完整 session。
- 只输出一个 session 级分数。
- 抽取持续生效约束，并检查后续 rewrite 是否保留。

评分口径：

- 识别品类、品牌、价格、人群、场景、硬属性等持续约束。
- 仅当用户明确撤回或显式覆盖时，约束失效。
- 对每个约束计算 `N_actual / N_should`。
- `overall_score = 所有约束 recall 的均值`。

输出：

```json
{
  "extracted_constraints": [
    {"type": "brand", "value": "优衣库", "from_turn": 1, "should_persist_until": 4}
  ],
  "constraint_retention": [
    {
      "constraint": "优衣库",
      "should_appear_in_turns": [2, 3, 4],
      "actually_appeared_in": [2, 4],
      "recall": 0.6667
    }
  ],
  "overall_score": 0.6667,
  "explanation": "第3轮裤子查询未继承优衣库品牌"
}
```

### 5. Evidence Audit Agent

职责：

- 复查 Dim1 和 Dim2 的证据链。
- 检查幻觉词是否真的无法从当前 query、历史 query 或合理行业表达中推出。
- 检查约束是否真的应持续保留，避免把合理主题切换误判为记忆丢失。
- 标记 `needs_review`、`audit_confidence` 和冲突原因。

该 Agent 不直接改分，除非平台启用「审计覆盖」策略。默认只作为低置信复审队列依据。

### 6. Scoring Aggregator Agent

职责：

- 汇总 turn 级和 session 级评分。
- 生成 session 加权总分。
- 生成 run 级总览。

聚合规则：

- 维度一 session 分 = 所有非首轮 query 的维度一分数均值。
- 维度二 session 分 = Dim2 Memory Retention Agent 的 `overall_score`。
- session 加权总分：

```text
sum(valid_dim_score * dim_weight) / sum(valid_dim_weight)
```

- run 加权总分 = 所有有效 session 加权总分均值。
- run 通过率 = session 加权总分大于等于准出阈值的比例。

### 7. Badcase Analyst Agent

职责：

- 对低分结果生成可读归因。
- 维度一生成 query 级 badcase。
- 维度二生成 session 级 badcase。
- 将 badcase 归类为漏补、幻觉、品牌未继承、约束遗失、过度补全、非导购拼接历史等。

输出示例：

```json
{
  "scope": "turn",
  "dimension_code": "dim1",
  "turn_index": 3,
  "issue_type": "hallucination",
  "summary": "改写加入用户从未表达的具体认证和质保信息",
  "evidence": ["FAS级", "8年质保"]
}
```

### 8. Calibration Agent

职责：

- 用 golden set 对比人工标注。
- 监控 prompt 版本变化带来的分数漂移。
- 监控重复评测稳定性。
- 产出平台可信度指标。

核心指标：

- 人机一致率。
- 维度一 query 级准确率。
- 维度二 session 级准确率。
- 同一输入重复评测的分数方差。
- 低置信样本占比。

## 结果模型

### SessionResult

```json
{
  "meta_id": "session_xxx",
  "weighted_score": 0.82,
  "lowest_dim_code": "dim1",
  "dimension_scores": {
    "dim1": 0.75,
    "dim2": 0.90
  },
  "dimension_weights": {
    "dim1": 0.5,
    "dim2": 0.5
  },
  "dim1_turn_scores": [
    {
      "turn_index": 2,
      "score": 1,
      "badcase": null
    },
    {
      "turn_index": 3,
      "score": 0,
      "badcase": "品牌约束未保留"
    }
  ],
  "dim2_session_detail": {
    "score": 0.90,
    "explanation": "价格约束保留完整，品牌在第4轮丢失一次"
  }
}
```

### Dimension Metadata

平台应显式维护维度粒度元数据：

```json
{
  "dim1": {
    "name": "改写忠实性",
    "granularity": "turn",
    "first_turn_scored": false,
    "drilldown": true
  },
  "dim2": {
    "name": "跨轮记忆保留",
    "granularity": "session",
    "first_turn_scored": null,
    "drilldown": false
  }
}
```

前端、导出、API 都应依赖这份元数据，而不是在页面里硬编码特殊逻辑。

## 产品形态

### Run 总览

展示：

- run 加权总分。
- session 通过率。
- session 数、失败数、低分数。
- 维度一 session 均分。
- 维度二 session 均分。
- 分数分布。
- Top badcase。

### Session 列表

每行展示：

- `meta_id`。
- session 加权总分。
- 维度一分数。
- 维度二分数。
- 最低维度。
- badcase 摘要。
- 数据质量 flags。

### Session 详情

顶部展示：

- session 加权总分。
- 维度一/二维度分。
- 维度权重。
- `meta_id` 和轮次数。

维度一交互：

- 可展开。
- 展示每个非首轮 query 的分数。
- 展示 A/B/C 子项。
- 展示 badcase 归因、证据词、用户 query、改写 query。
- 首轮展示为「上下文轮，不参与维度一评分」。

维度二交互：

- 不提供 query 级展开。
- 展示 session 级约束抽取、约束保留表、整体解释。
- 可查看证据，但不展示每轮分数。

## 导出

至少提供三张表：

1. `Session Overview`
   - `meta_id`
   - `weighted_score`
   - `dim1_score`
   - `dim2_score`
   - `lowest_dim_code`
   - `badcase_summary`

2. `Dim1 Per Query`
   - `meta_id`
   - `turn_index`
   - `gmt_create`
   - `user_query`
   - `rewritten_query`
   - `A_completeness`
   - `B_no_hallucination`
   - `C_reasonable_completion`
   - `overall_score`
   - `badcase_analysis`

3. `Dim2 Session Memory`
   - `meta_id`
   - `overall_score`
   - `extracted_constraints`
   - `constraint_retention`
   - `explanation`

## 平台优化项

### P0：评测口径正确性

- 将 `meta_id` 明确映射为 session id。
- 同一 `meta_id` 内按 `gmt_create` 派生轮次。
- 首轮不参与维度一评分。
- 维度一使用 `A * B * C` 的乘法口径。
- 维度二保持 session-only，不生成 query 分数。

### P1：数据结构和 API

- 区分 session 级结果和 turn 级结果。
- 维度一同时写入 session 均分和 turn 明细。
- 维度二只写入 session 级结果。
- API 返回维度粒度元数据，供 UI 控制下钻行为。

### P2：前端分析体验

- Run 总览以 session 加权分为主。
- Session 详情中维度一可下钻，维度二不可下钻。
- Badcase 分为 query badcase 和 session badcase。
- 维度二 badcase 加入回归集时应加入整个 session。

### P3：可信度和回归

- 建立 50 到 100 个 session 的 golden set。
- 引入 Evidence Audit Agent 标记低置信样本。
- 监控 prompt 版本漂移和重复评测稳定性。
- 增加人机一致率看板。

## 验收标准

- 上传包含 `meta_id` 和 `gmt_create` 的多轮数据后，平台按 session 聚合并按时间排序。
- 每个 session 有加权总分和维度一/二维度分。
- 维度一首轮无分，后续每轮有分数与 badcase 分析。
- 维度一 session 分等于非首轮 query 分数均值。
- 维度二每个 session 只输出一个分数。
- 维度二页面无法展开 query 级分数。
- Run 总览、Session 详情、导出三处口径一致。
- 低分 session 可进入 badcase 和回归集流程。
