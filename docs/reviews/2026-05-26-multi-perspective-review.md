# Multi-Turn Eval Platform · 多视角综合评审与 12 个月迭代规划

> **评审日期**：2026-05-26
> **评审对象**：`Looperswag/multi-turn-eval-platform` @ commit `7e9dc90`（4 阶段交付：W1/A → B → C → D2）
> **评审形式**：6 persona agent team 透镜 + Playwright 实测 5 关键流程 + 代码审计 + 竞品矩阵 + 12 个月可执行 roadmap

---

## TL;DR

平台已是一个**功能完整、设计有品味、并发安全可验证**的多轮对话评测系统，在「电商对话改写场景」垂直深度上**显著领先所有通用 LLM eval 工具**（LangSmith / Braintrust / Phoenix / Promptfoo）。**三个真正差异化的能力**：(1) session 三策略可切换的判官调度、(2) judge raw 响应的结构化推理卡（dim1 `evaluations[]` + dim2 `constraint_retention[]`）、(3) 人机一致率作为一等产品（Cohen's weighted κ on 4-level ordinal）。

但三大短板必须 90 天内补齐才能从「内审平台」演化为「行业级 dialog QA infrastructure」：

1. **统计可信度**：所有分数都是点估计、无 CI / bootstrap，198 条样本在低 applicable 维度（dim3/5）下统计效力不足；run-vs-run 对比错用 Cohen's κ。
2. **生产化基线**：API key timing-safe 比较 + rate limit + 文件上传 size/MIME 校验 + 多用户 RBAC + 审计日志 + token 成本 dashboard 全缺。
3. **核心工作流 UX 摩擦**：标注队列无 priority bucket 分组（198 个等权按钮长滚动）、新建评测无 inline 校验、看板雷达对仅跑两维的 run 不解释残缺。

**战略定位建议**：聚焦「中文电商 / LLM 搜索导购 改写质量 QA 平台」垂直市场，不要正面打 LangSmith 通用 observability 红海。12 个月路线图围绕「可信度（S1）→ 可生产化（S2）→ 工作流深度（S3）→ 行业纵深（S4）」四步走，详见末节。

**总体评分**（10 分制）：

| 维度 | 评分 | 简评 |
|---|---|---|
| 设计合理性（架构 + 评测科学） | **7.5 / 10** | 并发模型、SessionLocal、applicable 全链路保护扎实；6 维有概念重叠、无 CI |
| 创新性 | **8 / 10** | 3 个真护城河能力 + 中文 first-class；落后于成本追踪 / RBAC |
| 交互先进性 | **7 / 10** | 结构化 reasoning 卡 + 维度 tab inline 分数是同类最佳；annotation 队列短板 |
| 易用性（首次用户） | **6 / 10** | 默认值预选好；inline 校验、empty-state、错误恢复有 3 处明显卡点 |
| 生产可部署性 | **5.5 / 10** | docker-compose 单机够用；缺 RBAC / 审计 / 成本 / 可观测 |

---

## 平台快照（评审上下文）

- **代码体量**：Python 508 KB + TypeScript 370 KB，15 alembic migrations，11 backend routers，7 个测试文件
- **核心能力**：6 维 × 3 prompt 策略 LLM judge、ThreadPoolExecutor concurrency（验证 5.9× 加速、0 race condition）、4 类对比、人机一致率、回归集、SSE 实时进度、多格式导出
- **设计语言**：Hallmark 系统（米色 #f4ecd8 + 森林绿 + 警示 tomato/amber），tokens / 字体 / 间距三层架构
- **生产基线**：docker-compose 5 容器（postgres / redis / api / worker / web），单机可达，X-API-Key 全局鉴权可选

---

## Persona 1 · 产品体验官（UX Director）

> 我的工作是从一个完全没见过这个平台的算法 QA 工程师角度，按真实路径走一遍，记录每一处 friction。我用 Playwright 跑了 5 个核心流程，给出 **friction score 4/10**（整体顺畅但有 3 处明显卡点）。

### 核心观察

平台的**信息层级感受是高品质的**——badcase drawer 与维度详情 tab 是我见过中文 eval 工具里信息密度最高、视觉负担最低的组件。新建评测页把 5 个下拉的默认值都预选成「最新 dataset → 对应 bot → DeepSeek → line_198_v1 prompts」，首次用户 2 click 就能跑出第一个 run，这是大多数 eval 工具做不到的。

但**核心工作流的标注页是反高潮**：左侧队列把 198 个 case 渲染成 198 个等权 button 长滚动列表，文案承诺"按机评分（0 → 0.5 → 1 → N/A）优先级"但 UI 上没有任何分组、分隔、标题，annotator 完全看不出该先抓哪一批；button 上只有 19 位 conv_id + 分数，**看不到 case query 文字**，必须先点开中心面板才知道在标什么——这是核心工作流的第一卡点。

### 3 个亮点（带证据）

1. **Badcase Drawer 结构化 reasoning 卡**（`flow-4-badcase-drawer-expanded.png`）：dim1 展开后看到 T1/T2/T3 每轮 A/B/C 子分 + 中文 reason，dim2 看到 step1/2/3 推理 + c1-c4 约束 lifecycle（"T1 → T2 (category_switch)"）。让 judge 输出从黑盒分数变成可审计推理链，是平台最有差异化价值的组件。
2. **维度 tab 分数 inline 显示**（`flow-3-dimensions-dim1.png` e62-e85）：顶部六维 tab 各自显示均分 "0.885 / 0.890 / — / — / — / —"，一眼看出哪些维有数据，比传统 tab+翻页快得多。
3. **默认值预选 + FTU 路径压缩**（`flow-1-eval-runs-new.png`）：5 个下拉都已预选 sensible default，2 click 出第一个 run。

### 3 个痛点（带影响）

1. **标注队列无 priority bucket 分组**（`flow-5-annotations.png` e119）：核心工作流第一卡点，影响标注效率与 annotator 信任。
2. **新建评测无 inline 校验**（`flow-1-eval-runs-new.png` e60）：空名称提交时按钮无响应，只靠浏览器原生 focus；权重总和 1.4≠1 也只有小字解释，无视觉警示态。首次用户摸不着头脑。
3. **看板雷达图残缺无说明**（`flow-2-eval-runs-30.png` e90）：run 只跑 dim1+dim2 时雷达只两条轴像残缺三角，无 empty-state 注释，用户怀疑系统故障。

### 3 个改进建议

| 优先级 | 建议 | 工作量 |
|---|---|---|
| **P0** | 标注队列重构：按 priority bucket 分组（0/0.5/1/N/A 四段），每段带标题与计数，case 卡片显示 query 首 30 字 + 维度评分 chip | 5 人天 |
| **P0** | 全平台 form inline 校验：空字段 / 权重和异常 / Annotator 未填 → 红色边框 + 行内文案；保存按钮 disabled+原因 tooltip | 3 人天 |
| **P1** | Empty-state 图形系统：维度 tab、雷达图、badcase 表、kw 频次表统一 empty-state copy（"本次评测未启用此维度" / "judge 未输出此字段"），不要让残缺看起来像 bug | 2 人天 |

---

## Persona 2 · 评测方法论科学家（Eval Scientist）

> 我的工作是用 measurement-science 标准审计这个平台「能不能信」。3 个亮点是真正做对了的 eval 决策，3 个 blind spot 是会让基于评测做版本选择的人系统性踩坑的。

### 核心观察

**`applicable=False` / NA 的全链路保护是同类系统里做得最干净的一处**：`_SingleTurnApplicableEvaluator` 只把有效分入 `scores[]`（`evaluators.py:374-399`），`conversation_weighted_score` 剔除 `None` 分母（`scoring.py:24-35`），`agreement.categorize` 把 `is_applicable=False` 归为 `NA` 而非 `ZERO`（`agreement.py:23-46`）。这条链路没有 silent-zero 漏洞，是非常正确的工程决策。

但**6 维存在结构性语义重叠 + run-vs-run kappa 概念错位 + 全平台无 CI 三大方法论债**，会让"基于评测数据做版本决策"系统性偏倚。

### 3 个亮点

1. **dim2 v4→v5 范式转变**（`prompts_v5_templates.py:273-320`）：v4 让 judge 从头抽约束再算召回，judge 自身识别噪声进入分母；v5 改为以 bot 自报的 `inherited_constraints` 为锚，judge 只做 Precision（伪声明核查）+ Recall（漏报核查）。把 judge 职责收窄为"验证而非替代"，测量噪声减半。
2. **JSON 解析三重回退 + exponential retry**（`judge_client.py:23-85`）：` ```json ` 代码块 → 裸 JSON → 正则提取，覆盖 DeepSeek 高并发下三类常见输出偏差；`_pick_score` 对非数值类型记 warning 返回 `None` 而不是强转 0。两层防护后 judge 失败不污染分数分布。
3. **StrictUndefined 模板渲染**：缺变量直接报错而非静默渲染为 "None" 字符串。这是大多数 Jinja2 应用忽略的陷阱。

### 3 个痛点

1. **dim1 与 dim3/dim6 双重惩罚**（`seed_198_run.py:50-52, 141-144` vs `prompts_v4_templates.py:119-151`）：dim1 维度 C 已经判 `in_shopping_context=false` 时改写拼接历史品类应得 0；dim3 又评估边界识别正确性；dim6 又评估纠错路径。一条"今天天气 → 拼接牛仔裤"的 session 在最终 weighted_score 中被双重甚至三重惩罚。
2. **Run-vs-run 对比错用 Cohen's κ**（`comparison.py:521-534`）：kappa 的语义前提是"独立 rater 对同一对象给评级"。run_a/run_b 用不同 judge 模型（正是被测变量），把"被测变量输出差异"当作"rater 一致性"计算 kappa 是概念错位；3 档量化阈值（≥0.6=1, <0.3=0）硬编码，权重变化会让 kappa 漂移。
3. **全平台无 CI / bootstrap，低 applicable 维度统计效力不足**：dim3/5 实际 applicable 命中率 10-20%，198 sessions 中有效样本可能仅 20-40 条，单 run 的 dim3 pass_rate 95% CI 宽达 ±20 个百分点，但 UI 只显示点估计与 `delta`，没有显著性标注或样本不足警示。`chi_square_dim` 在 n<30 返回 None 是正确的，但前端是否明确展示"样本不足"未确认。

### 3 个改进建议

| 优先级 | 建议 | 工作量 |
|---|---|---|
| **P0** | dim3/dim5 加 effective N 警示 badge + comparison 显示 `chi_square_pvalue=None` 为"N/A（样本不足）"；`sample_count` 字段已存在于 `scoring.aggregate_dimension_summary`，前端逻辑+badge 即可 | 3 人天 |
| **P1** | 修复 dim1/dim3 语义边界：dim1 prompt 在 `boundary_type ∈ {non_shopping, correction, emotion_negative, meaningless}` 时把 C 维度标 `C_applicable=false`，由 dim3/dim6 各自专责；同步更新 seed_198_run.py + prompts_v5_templates.py + Dim1SessionEvaluator | 5 人天 |
| **P2** | Run-vs-run 加 bootstrap 95% CI（1000 次重采样均值差的 2.5/97.5 分位），移除 kappa 在该路径的使用，重命名为 `score_distribution_overlap`（改用 Cohen's d 或 Mann-Whitney U 效应量）；前端 comparison 页加 CI 区间条 | 4 人天 |

---

## Persona 3 · 平台架构师（Chief Architect）

> 我的工作是从「这个系统能不能扩展到 10x 用户 / 100x 数据 / 跨团队协作」角度看代码组织。整体分层清晰，但 router 承载了不该有的业务逻辑、JSON 列过度使用、安全缺口三处必须 90 天内补。

### 核心观察

`comparisons.py` 是教科书级薄路由（180 行，全部委托 `services/comparison.py`），证明团队懂得正确分层。但 `judge_config.py` 是反例——`_runs_referencing_prompt` 全量拉 EvalRun 做 Python 端枚举、`_next_version_tag` 版本号推断、`_validate_jinja2_template` Jinja2 校验器、`/prompts/preview` sample context 全挤在 router 里，形成 300+ 行 god router。`eval_runs.py` 居中：`_validate_dimension_weights`、bucket 分桶、`list_badcases` 的全量内存过滤都应该下沉。

**15 条迁移呈现稳健的特性增量节奏**，但 6 处 JSON 列里有 3 处（`EvalRun.judge_prompt_version_ids`、`EvalRun.dimension_weights`、`Comparison.result_payload`）属于"本可用关联表或专用列替代"的妥协设计，会在跨表查询/索引时埋债。

### 3 个亮点

1. **per-worker SessionLocal 模式**（`eval_tasks.py:115-188`）：`_evaluate_one_conversation` 每次独立 `db = SessionLocal()`，`finally` 中 `db.close()`，stateless 跨线程对象（evaluators / judge_client / renderer）共享；主线程仅写 EvalRun 元数据；幂等恢复（`existing_conv_ids` 去重）防 Celery acks_late 重投。这是近期 P0-1 重构后最正确的并发设计。
2. **SSE Redis pubsub 解耦**（`sse.py:17-42` + `eval_tasks.py:49-53`）：HTTP 层订阅 `eval_run:{id}:progress` channel，任务侧只 publish，无共享状态；terminal event 后主动 break 防订阅泄漏。
3. **comparison router 委托模式**：缓存键设计（`build_cache_key`）+ GET 时失效重算（lines 161-169）是轻量级 ETag 替代，思路清晰。

### 3 个痛点

1. **`deps.py:21` API Key 用 `!=` 比较 + 无 rate limit**（安全）：Python `==/!=` 是 short-circuit，理论上可 timing side-channel 推断 key；FastAPI 层无任何 rate-limit middleware。`REQUIRE_API_KEY=true` 暴露公网时 key 爆破窗口完全开放。
2. **datasets 文件上传无 size / MIME 白名单**（`datasets.py:202-246, 359-363`）：`UploadFile` 直接 `await file.read()` 无 size 检查、无 `content_type` 白名单，仅靠 `json.loads` 判格式。攻击者可上传超大文件 OOM；恶意 xlsx 有已知 zip-bomb / XXE 风险。
3. **`retry_failed_cases` DRY 债 + 顺序执行**（`eval_tasks.py:428-651`）：完整复制 `execute_eval_run` 的 evaluator 构建 + 写入 + publish 三段逻辑，且无 ThreadPoolExecutor，大规模重试时性能远差于主路径。同时 `_check_cancelled` 在主循环 `as_completed` 中访问 ORM 与 `publish_lock` 存在锁外/锁内 db 操作的逻辑竞争。

### 3 个改进建议

| 优先级 | 建议 | 工作量 |
|---|---|---|
| **P0** | `deps.py` 改 `secrets.compare_digest`；`main.py` 集成 `slowapi`，`/api/` 全局 300 req/min/IP；扫一遍所有 router 类似比较场景 | 0.5 人天 |
| **P0** | 文件上传 size 限制（50 MB）+ MIME 白名单 + `defusedxml`（xlsx 解析层）；nginx/ingress 加 `client_max_body_size` | 1 人天 |
| **P1** | 抽取 `_build_eval_components(db, run)` 和 `_run_conversations_parallel(...)` 私有函数，`execute_eval_run` 与 `retry_failed_cases` 都调用之；retry 加 ThreadPoolExecutor。把两 task 核心代码从 ~400 行压到 ~150 行 | 3 人天 |
| **P1** | god router 拆分：`judge_config.py` 抽 `services/prompt_lifecycle.py`；`eval_runs.py` 抽 `services/badcase.py` 与 `services/dashboard.py` | 5 人天 |

---

## Persona 4 · 创新评审（Innovation Reviewer）

> 我的工作是横向对比 8 家市场存量（LangSmith / Braintrust / Phoenix / Helicone / Weave / PromptLayer / Promptfoo / Anthropic Console），告诉你哪些能力是真护城河、哪些是必须补的市场标配。

### 核心观察

**25 项能力矩阵显示平台在 3 个维度上没有任何竞品对手，但在 3 个市场标配上落后**：

| 类别 | 平台地位 | 关键能力 |
|---|---|---|
| **真护城河（3 项）** | 全市场独有或最强 | session 三策略可切换 / 结构化 judge raw 解析 / 人机一致率 dashboard |
| **市场标配（追赶项）** | 落后 6-12 个月 | 成本 token dashboard / 统计 CI 显著性 / RBAC + 审计 + dataset diff |
| **领域纵深（独门）** | 无竞品 | 电商对话改写 dim1-6 schema + badcase→回归集闭环 |

### 3 个亮点

1. **Session 三策略 + 结构化 judge 解析是市场孤品**：LangSmith / Braintrust 都把 multi-turn 当 trace 看，eval 仍按 single record；本平台 `per_turn / session_returns_per_turn / session_single_score` 三策略 + `evaluations[]` / `constraint_retention[]` 结构化字段，是把"judge 怎么想的"做成一等公民。
2. **人机一致率 Cohen's weighted κ dashboard**：LangSmith / Braintrust 都有标注队列，但 κ / α / 人机对比要自己 SQL 算。本平台把它做成 4-way Comparison 中的一等场景，**回答了 eval 平台最该回答但没人答的核心问题——"你的 LLM judge 到底有多准"**。
3. **垂直领域产品化 schema**：dim1-6 是基于电商对话改写沉淀的领域知识，配合 badcase drawer 一键加入 regression set，形成"发现→标记→沉淀→回归"闭环。Promptfoo 最接近但纯 CLI，无标注/回归集概念。

### 3 个痛点（市场落后项）

1. **成本 / token observability 完全缺失**：Helicone 整个产品就是成本追踪，LangSmith / Braintrust 默认显示每次 eval 花了多少钱。本平台跑 1000 条 × 6 维 × 多 judge 无 token / 金额 dashboard，对企业采购是硬伤。
2. **统计严谨性（CI / bootstrap / significance）落后**：Braintrust 核心卖点之一是"score A vs B 差异是否显著"，给 p-value + bootstrap CI。本平台 4-way Comparison 缺少显著性标注，容易让用户得出"A 比 B 好 0.03 分"的伪结论。
3. **RBAC + 审计日志 + dataset diff 全缺**：LangSmith / Braintrust / Phoenix 都有 workspace、role、API key scope、dataset commit history。本平台 dataset 上传是覆盖式无 diff / 回滚；audit log 完全缺失。这三项决定能否进入大客户采购清单。

### 3 个改进建议（战略层）

| 优先级 | 建议 | 工作量 |
|---|---|---|
| **P0** | 战略定位：**聚焦「中文电商 / LLM 搜索导购改写质量 QA 平台」**，README + landing 全部重写为目标客户场景（淘宝/京东/拼多多/小红书 类对话搜索的 rewrite QA），不要正面打 LangSmith 通用 observability 红海 | 2 人天文档+设计 |
| **P1** | 90 天补市场标配：(a) token 成本 dashboard、(b) bootstrap CI 显著性标注、(c) dataset commit / diff。三项加起来约 15-20 人天，是垂直定位立得住的前提 | 见 S1 roadmap |
| **P2** | 长尾扩展：dim1-6 schema 抽象为可插拔 "domain pack"（电商导购 / 客服多轮 / 旅游导购 / 在线教育），让平台可向其他垂直行业横向复制 | S4 工作 |

---

## Persona 5 · 行业代言人（电商对话改写 QA 团队 视角）

> 我代表一个真实场景：在某电商平台做对话搜索 / 导购改写算法的 QA 团队 lead。我的痛点是「改写改了一版，怎么知道整体变好还是变坏」。我评估这个平台能否成为我的日常工作工具。

### 核心观察

**这是我目前看过最贴近真实业务问题的中文对话评测平台**——dim1 改写忠实性 / dim2 跨轮记忆 / dim3 意图边界 / dim4 指代消解 / dim5 重复请求 / dim6 用户纠错，这六维不是从论文抽象出来的玩具维度，是 QA 团队 daily review 真实会列出的问题清单。"花知晓彩妆 vs 纽芝兰宝宝"那个 badcase（run 30 case#1190）从 drawer 直接看出 "用户当前轮明确指定新品牌'纽芝兰宝宝'，改写错误地保留了历史品牌'花知晓彩妆'"——这个洞察的清晰度，是任何通用工具都给不出来的。

**但要让我团队用它当日常工具，3 个场景缺得明显**：(1) 算法迭代后想跑全量历史 badcase 看是否回归——目前 regression set 是手工加入，缺"自动从过去 6 个月 ≤0.5 分的 case 拉一个回归集"；(2) 我想知道这次改动让 token / 调用费涨了多少——无成本视图；(3) 我标完 50 个，想看 annotator 之间是否一致——agreement 页只有 human-vs-judge，没有 human-vs-human 一致率。

### 3 个亮点

1. **领域产品化深度**：6 维 schema、3 种 prompt 策略、dim2 v5 验证范式（以 bot 自报约束为锚）——这是只有真做过电商对话改写的人才能设计出来的。`boundary_type` 的 7 分类（normal_shopping / shopping_resume / correction / non_shopping / info_query / emotion_negative / meaningless）覆盖了我团队在 daily review 里讨论的所有场景。
2. **Badcase drawer 是 reviewer 工作台**：3 轮对话 + 6 维 bar + 结构化 reasoning + tag / 回归集一键加入。一个 case 从打开到决策（加 tag + 加回归集）≤4 click。
3. **Live progress + retry-failed**：跑 1000 条不会盯着等，错了的 case 一键重试不重跑全量。这是真实生产环境的关键。

### 3 个痛点（业务视角）

1. **缺"自动回归集"**：每次算法迭代我都要重跑历史 badcase。目前 regression set 是手工从 drawer 加，没有"按维度 + 时间窗 + 阈值"自动构建集合的能力。
2. **缺成本视图**：跑 1000 条 × 6 维 = 6000 次 judge 调用。CFO 要的是「这次 review 花了 ¥X，对比上个月省/超 Y%」，平台目前给不出。
3. **缺 human-vs-human agreement**：我团队 4 个 annotator 平行标，需要知道是否一致才能信任标注结果。目前只有 human-vs-judge，没有标注员之间 κ。

### 3 个改进建议

| 优先级 | 建议 | 工作量 |
|---|---|---|
| **P0** | 自动回归集：从 badcase 列表加"按规则保存为回归集"，规则可配（维度 ≤ 阈值 + 时间窗 + 数据集）；定时任务每周自动从过去 N 天拉新 badcase 入集合 | 4 人天 |
| **P1** | Token 成本 dashboard：judge_client 层埋点记录 `prompt_tokens / completion_tokens / cost_usd`（按 model price table），run 详情页加成本卡片，comparisons 加成本 delta | 5 人天 |
| **P1** | Annotator 一致率：annotations/agreement 页面增加 human-vs-human 矩阵（每对 annotator 的 κ + 案例分歧最多的 top 10 case） | 3 人天 |

---

## Persona 6 · 落地工程师（Deployment Operator / SRE）

> 我的工作是从「凌晨 3 点 pager 响起来怎么办」角度看这个平台。docker-compose 单机部署够用，但生产化基线缺得太多——可观测、SLO、灾备、灰度全没。

### 核心观察

`docker-compose` 5 容器（postgres / redis / api / worker / web）+ `make migrate` + `make judge-check`，**FTU operator 半小时能拉起一个 dev 环境**，这是优点。但 README 里"单机生产部署"那一节本质上是 dev 部署贴在生产，无监控、无日志收集、无 SLO、无备份策略、无灰度路径。`REQUIRE_API_KEY=true` 还有一个尴尬副作用——浏览器 `<a href>` 直跳的导出不带 header 会失败（README 里坦诚说明，待 D 阶段修），但这个 disconnect 暴露了认证设计只考虑了 API 调用没考虑 SSR/file download。

### 3 个亮点

1. **Alembic 迁移序列稳健**：0001-0015 节奏清晰、无回滚风险 DDL 较多、`make migrate` 一键到 head；这是 ops 最在意的 schema 演进基线。
2. **`make judge-check` 自检脚本**：本地一键验 ARK/DeepSeek 联通 + 单轮渲染 + 单轮调用，是真做过 dogfood 的人才会写的脚本。
3. **SSE Redis pubsub 解耦**：HTTP 层无状态、终态事件主动 break、channel 按 run_id 隔离，多客户端订阅同一 run 不冲突。

### 3 个痛点（生产化缺口）

1. **零可观测**：无 structured logging（看代码全是 `print`/`logger.info` 散落），无 prometheus metrics，无 tracing，无 SSE 心跳/重连。run 卡 30 分钟没人知道。
2. **无备份 / 灾备策略**：README 提了"docker volume 持久化"但没说备份频率、灾难恢复 RTO/RPO；`pg_dump` 脚本无；judge_raw_response 大量 JSON 数据丢了无法重建（重跑判官成本不低）。
3. **无灰度 / feature flag**：dim1 v4→v5 升级是直接覆盖 prompt 模板（迁移 0011 / 0013 / 0014）；想 A/B 灰度只能靠多 prompt 版本手工选——无系统级灰度开关、无金丝雀发布概念。

### 3 个改进建议

| 优先级 | 建议 | 工作量 |
|---|---|---|
| **P0** | 接 OpenTelemetry：structured logging（structlog）+ FastAPI Instrumentator + Celery integration；docker-compose 加 grafana + loki 可选 profile | 3 人天 |
| **P1** | 备份 cron：`pg_dump` 每日全备 + 每小时 WAL，存到 docker volume 或可选 S3；README 加 RTO/RPO 表格与 restore drill 步骤 | 2 人天 |
| **P2** | Feature flag 框架：引入 `unleash` / 自建简易 flag 表，prompt version、prompt strategy、并发数、判官模型都可灰度（按 user / run id mod 灰度） | 5 人天 |

---

## 共识热图（≥3 个 persona 同时指出）

| 共识主题 | 指出的 persona | 紧迫度 |
|---|---|---|
| **缺统计 CI / 显著性 / 成本视图** | Eval Scientist · Innovation · Domain Expert | **P0** |
| **生产化基线缺（安全 + 可观测 + RBAC + 审计）** | Architect · Innovation · Deployment Operator | **P0** |
| **dim1/dim3 双重惩罚 + 维度边界不清** | Eval Scientist · Domain Expert · Innovation | **P1** |
| **关键工作流 UX 摩擦（标注队列 / 新建评测 / 看板雷达）** | UX · Domain Expert · Deployment（首次部署后看演示场景） | **P1** |
| **自动回归集 + dataset diff** | Domain Expert · Innovation · Architect（JSON 妥协与此相关） | **P2** |

这 5 个主题的信号同时来自 ≥3 个独立视角，是平台下一阶段的真问题。

---

## 12 个月迭代路线图（S1–S4）

每季度 3-5 个里程碑，每个里程碑可拆 ≤2 周任务，含 acceptance criteria。

### S1（M1–M3）· 「可信度补足 + 安全基线」 · Theme: Trustworthy & Defensible

| 里程碑 | Acceptance Criteria | 工作量 | 共识来源 |
|---|---|---|---|
| **M1.1 统计 CI 与显著性** | `aggregate_dimension_summary` 输出 `mean_ci_low/high`（bootstrap 1000×）；comparison 页 dim_delta 显示 `delta_ci_low/high`；`chi_square_pvalue=None` 渲染为"N/A（n<30）" badge | 5 天 | Eval Scientist · Innovation |
| **M1.2 安全基线** | `deps.py` `secrets.compare_digest`；`/api/` 全局 300 req/min/IP；文件上传 50 MB + MIME 白名单 + defusedxml；CI 加 bandit 静态扫 | 3 天 | Architect |
| **M1.3 dim1/dim3 边界修复** | `boundary_type ∈ {non_shopping, correction, ...}` 时 dim1 C 自动标 `C_applicable=false`；migration 0016 加列；回归测试覆盖前后分布差异 | 5 天 | Eval Scientist · Domain |
| **M1.4 Empty-state 系统化** | 维度页 / 雷达 / badcase 表 / kw 频次 统一 empty-state copy + 图形；维度 tab 未启用维度显示"本次未启用"badge | 2 天 | UX |
| **M1.5 Token 成本埋点** | `judge_client` 层记录 prompt / completion tokens；DB 加 `eval_call_cost` 表；run 详情页加成本卡片（人民币 + USD 双显） | 5 天 | Innovation · Domain |

**S1 验收**：跑一次新 run，前端看到「dim2 0.89 ± 0.04（95% CI）·成本 ¥3.14」；REQUIRE_API_KEY 上线公网无被爆破风险。

### S2（M4–M6）· 「核心工作流 UX 重做 + 生产化运维」 · Theme: Daily-Driver

| 里程碑 | Acceptance Criteria | 工作量 |
|---|---|---|
| **M2.1 标注队列重构** | 4 段 priority bucket（0/0.5/1/N/A）分组 + 段标题 + 计数；case 卡片显示 query 首 30 字 + 维度评分 chip；键盘 j/k 上下导航 + Space 提交 | 5 天 |
| **M2.2 新建评测 inline 校验** | 所有 form 字段错误态有可见红框 + 行内文案；权重和 ≠1 显眼 warning + "归一化"按钮变 primary；Annotator 名空显示 placeholder + 红字提示 | 3 天 |
| **M2.3 可观测基线** | OpenTelemetry + Prometheus + structlog；docker-compose 加 optional grafana profile；3 个核心 dashboard：API 延迟 / Celery 队列深度 / SSE 连接数 | 5 天 |
| **M2.4 备份 + 灾备文档** | `pg_dump` 每日 + WAL hourly 脚本；README 加 RTO/RPO 表与 restore drill；docker volume 监控告警 | 3 天 |
| **M2.5 retry_failed_cases DRY 重构** | 抽 `_build_eval_components` + `_run_conversations_parallel`；retry 加 ThreadPoolExecutor；执行行数从 400 → ~150；性能 ≥ 主路径 80% | 3 天 |

**S2 验收**：annotation 工作台日均标注 throughput 提升 ≥2×；grafana 看到所有关键指标；retry 200 个 failed case ≤ 主路径 1.2× 时间。

### S3（M7–M9）· 「行业纵深 + RBAC + Dataset 版本化」 · Theme: Enterprise-Ready

| 里程碑 | Acceptance Criteria | 工作量 |
|---|---|---|
| **M3.1 RBAC + 审计日志** | 引入 `user` / `org` / `role` 三表；JWT 替代 X-API-Key；API key scope 按 org/permission；audit_log 表记录所有 mutation；OWASP top10 review pass | 10 天 |
| **M3.2 Dataset 版本化** | Dataset 上传产生 commit；UI 加 diff 视图（新增/删除/修改 conversation）；regression set 关联 dataset commit hash | 7 天 |
| **M3.3 自动回归集** | 规则引擎：按"维度 ≤ 阈值 + 时间窗 + 数据集"自动从 badcase 池构建；定时任务（Celery beat）每周拉新 | 4 天 |
| **M3.4 Annotator vs Annotator 一致率** | `agreement` 页加 human-vs-human 矩阵（每对 annotator 的 κ + 分歧 top 10 case）；管理员可调"合并 majority vote 阈值" | 4 天 |
| **M3.5 god router 拆分** | `judge_config.py` 抽 `services/prompt_lifecycle.py`；`eval_runs.py` 抽 `services/badcase.py` + `services/dashboard.py`；router 全部 ≤ 100 行 | 5 天 |

**S3 验收**：B 端客户可以多用户分角色协作；dataset 改一行可见 diff；自动回归集每周自动拉 ≥5 个 case。

### S4（M10–M12）· 「多 Judge Ensemble + Domain Pack + 公开发布」 · Theme: Industry-Grade

| 里程碑 | Acceptance Criteria | 工作量 |
|---|---|---|
| **M4.1 多 judge ensemble** | run config 可选多 judge（DeepSeek + GPT-4o + Claude），结果支持「均值 / 多数投票 / 加权」三种聚合；UI 显示每 judge 单分 + 聚合分 + judge 间一致率 | 8 天 |
| **M4.2 LLM-as-Judge bias 缓解** | 位置扰动（session turns 随机重排再跑）+ 长度归一化（短/长 query 加正则化项）；comparison 页可看 bias-adjusted vs raw 差异 | 6 天 |
| **M4.3 Domain Pack 抽象** | dim 配置 + prompt 模板 + boundary_type schema 打包为 "domain pack"；内置「电商导购改写」+「客服多轮」+「旅游导购」三个 pack；用户可自定义 | 8 天 |
| **M4.4 公开 v1.0 release** | OSS（Apache 2.0）；GitHub README 重写为 vertical-positioned 营销页；3 个 case study（电商 / 客服 / 旅游）；blog 发布 | 5 天 |
| **M4.5 Feature flag + 灰度** | unleash / 自建 flag 表；prompt version、并发、judge model 可按 user / run id mod 灰度；A/B 实验框架 | 5 天 |

**S4 验收**：v1.0 OSS release；3 家外部用户在生产；公开 ranking benchmark（中文多轮改写）；月活 ≥500。

---

## 24-36 个月长期愿景

### 演进路径：内审平台 →「中文 Dialog QA Infrastructure」

**Year 2（M13-M24）**：
- **SaaS 化**：基于 v1.0 OSS 内核推出 hosted 版（按 token 计费 + 企业版年费），目标年 ARR 500 万人民币
- **行业基准**：发布「中文多轮对话改写公开 benchmark」（类似 MMLU 之于通用 NLP），收 100+ 开源 / 商业模型评分，平台成为评测协议标准
- **横向 domain pack**：扩到 10 个垂直行业（医疗咨询 / 法律咨询 / 教育辅导 / 心理咨询 / B2B 销售…）
- **平台化 API**：第三方可以贡献 dimension + prompt + evaluator 插件市场

**Year 3（M25-M36）**：
- **闭环改进**：从「评测平台」演化为「改写质量改进平台」——基于 badcase 自动生成训练数据 → fine-tune bot model → 回归验证 → 上线灰度
- **多模态扩展**：支持「文本 + 图片 + 语音」多模态多轮对话评测（小红书 / 抖音搜索场景）
- **国际化**：英文 + 日文 + 韩文版本，进入东亚电商市场

### OSS vs SaaS vs 商业 fork 路径权衡（不替用户做决策，给三条路）

- **Path A · 纯 OSS**：完全 Apache 2.0，靠 GitHub stars / 社区影响力 → 卖咨询 / 培训。优点：心智成本低、社区粘性强；缺点：现金流弱，依赖外部融资。
- **Path B · Open core + SaaS**：OSS 内核 + 商业 SaaS 托管（RBAC / 审计 / SLA / 团队协作收费）。优点：现金流强、估值高；缺点：要做销售团队、OSS 与 SaaS 边界纠结。
- **Path C · 内审工具 + 卖咨询**：保持 private repo，作为咨询业务的差异化武器卖给电商客户。优点：聚焦、收入快；缺点：规模化天花板低、被竞品复制风险高。

**评审建议倾向 Path B**：定位垂直但留好 OSS 入口拓展水池，SaaS 收企业 RBAC/审计/SLA 价值。

---

## 风险地图

### 技术风险

| 风险 | 触发条件 | 影响 | 缓解 |
|---|---|---|---|
| **LLM judge bias 系统性偏差** | 长 session、位置敏感、风格偏好 | 评测结论失真，下游算法迭代踩坑 | S4 M4.2（位置扰动 + 长度归一化）+ 多 judge ensemble |
| **Postgres JSON 列查询性能崩塌** | 数据量 > 100k runs 后 `judge_prompt_version_ids::jsonb` 类查询慢 | 看板加载 > 5s，用户流失 | S3 M3.5 拆 router 时同步把 JSON 列下沉为关联表 |
| **Celery 重投导致重复评测** | acks_late + 网络抖动 | 同一 case 被多次判官，成本翻倍 | 已有 existing_conv_ids 去重，加强 unique 约束 + 监控 |
| **Race condition 死灰复燃** | 并发数 > 10 或 worker 数 > 单容器 | 数据不一致、判官浪费 | 保留 `parity_28_vs_30.sql` 模板，每次并发调整跑一次 |

### 产品风险

| 风险 | 触发条件 | 影响 | 缓解 |
|---|---|---|---|
| **垂直定位过窄** | 电商客户拓展乏力 | 12 个月收入未达目标 | S4 Domain Pack 留好抽象，可平移 |
| **维度 schema 锁死** | dim1-6 名称写进数据库主键 | 行业扩展时改 schema 风险大 | S3 中重构为 `dimension_definition` 表，名称不再是主键 |
| **annotator 流失** | 标注体验差 / 无激励 | 人机一致率数据匮乏 | S2 M2.1 队列重构 + 后续加标注质量积分 / 排行榜 |

### 商业风险

| 风险 | 触发条件 | 影响 | 缓解 |
|---|---|---|---|
| **OSS 推出后被竞品快速复制** | release 后 6 个月内 LangSmith 加 session 三策略 | 差异化优势侵蚀 | 持续做 domain pack 纵深 + 中文护城河；保护好 dim 设计 IP |
| **大客户索要源码授权** | 商务谈判中要 self-host 商业版 | 收入兑现路径变复杂 | 准备好 dual-licensing 策略（AGPL OSS + commercial） |
| **DeepSeek / ARK 政策变化** | 国内 LLM API 价格 / 监管波动 | judge 成本/合规 | S4 M4.1 多 judge ensemble 提供 vendor 切换能力 |

---

## 附录 · 评审证据索引

- 截图：`flow-1-eval-runs-new.png`, `flow-2-eval-runs-30.png`, `flow-3-dimensions-dim1.png`, `flow-4-badcase-drawer.png`, `flow-4-badcase-drawer-expanded.png`, `flow-5-annotations.png`（均位于仓库根目录，建议移入 `docs/reviews/screenshots/`）
- 评测方法论核心证据：`backend/app/services/eval_engine/evaluators.py:374-399`, `backend/app/services/scoring.py:24-35,58`, `backend/app/services/agreement.py:23-46`, `backend/app/services/comparison.py:521-534`, `backend/scripts/seed_198_run.py:50-52,141-144`
- 架构核心证据：`backend/app/tasks/eval_tasks.py:115-188,312-396,428-651`, `backend/app/api/deps.py:21`, `backend/app/api/datasets.py:202-246,359-363`, `backend/app/api/sse.py:17-42`
- 并发安全验证：`backend/scripts/parity_28_vs_30.sql`（run 28 vs run 30，5.9× 加速，0 race condition）
- 竞品矩阵：本文第「Persona 4」节，25 项能力 × 9 列对标

---

**评审撰写**：6-persona agent team（UX Director + Eval Scientist + Chief Architect + Innovation Reviewer + Domain Expert + Deployment Operator），主线程综合
**评审基线 commit**：`7e9dc90 feat(D2): structured judge reasoning card + live prompt preview`
**下一步**：S1 启动会，依本文 M1.1-M1.5 拆 5 个 issue，预计 M3 月底交付
