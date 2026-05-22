# Agent Team Multiturn Eval Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the approved Agent Team design so the platform evaluates multi-turn sessions by `meta_id`, orders turns by `gmt_create`, scores dim1 at query level, scores dim2 at session level, and exposes the correct drill-down behavior.

**Architecture:** Keep the existing FastAPI + SQLAlchemy + Celery + Next.js architecture. Add a thin Agent Team orchestration layer through explicit data contracts, dimension metadata, prompt/evaluator changes, and UI/export behavior. Preserve existing `Conversation` as the session record and `EvalCaseResult` as the session result; use `EvalTurnResult` only for turn-level dimensions such as dim1.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, Celery, Redis, PostgreSQL, Next.js 14 App Router, Tailwind, pytest.

---

## Task 1: Support `meta_id` + `gmt_create` Session Import

**Files:**
- Modify: `backend/app/services/dataset_parser.py`
- Test: `backend/tests/test_meta_id_gmt_create_parser.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_meta_id_gmt_create_parser.py`:

```python
from app.services.dataset_parser import infer_field_mapping, transform


def test_infers_meta_id_as_conversation_and_gmt_create_as_timestamp():
    mapping = infer_field_mapping(["meta_id", "gmt_create", "query", "rewrite"])

    assert mapping.conversation_id == "meta_id"
    assert mapping.turn_index == "gmt_create"
    assert mapping.turn_index_source == "timestamp"
    assert mapping.user_query == "query"
    assert mapping.rewritten_query == "rewrite"


def test_transform_groups_by_meta_id_and_orders_by_gmt_create():
    rows = [
        {
            "meta_id": "s1",
            "gmt_create": "2026-05-22 10:02:00",
            "query": "200以内",
            "rewrite": "优衣库男士衬衫 200元以内",
        },
        {
            "meta_id": "s1",
            "gmt_create": "2026-05-22 10:00:00",
            "query": "优衣库男士衬衫",
            "rewrite": "",
        },
        {
            "meta_id": "s1",
            "gmt_create": "2026-05-22 10:01:00",
            "query": "看看短袖",
            "rewrite": "优衣库男士短袖",
        },
    ]
    mapping = infer_field_mapping(["meta_id", "gmt_create", "query", "rewrite"])

    [conv] = transform(rows, mapping)

    assert conv["conversation_id"] == "s1"
    assert [t["turn_index"] for t in conv["turns"]] == [1, 2, 3]
    assert [t["user_query"] for t in conv["turns"]] == [
        "优衣库男士衬衫",
        "看看短袖",
        "200以内",
    ]
    assert conv["turns"][0]["rewritten_query"] is None
    assert conv["turns"][0]["timestamp"] == "2026-05-22 10:00:00"
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
pytest tests/test_meta_id_gmt_create_parser.py -v
```

Expected: FAIL because `meta_id` is not mapped as `conversation_id` or `rewrite` is not mapped as `rewritten_query`.

**Step 3: Implement minimal parser updates**

In `backend/app/services/dataset_parser.py`, update `_FIELD_ALIASES`:

```python
"conversation_id": [
    "conversation_id", "conv_id", "conversationid", "convid",
    "meta_id", "metaid", "meta_conversation_id", "metaconversationid",
    "session_id", "sessionid", "dialogue_id", "dialog_id",
    "会话id", "对话id", "session", "conversation",
],
```

Ensure `_timestamp` already contains `gmt_create`. If missing, add:

```python
"_timestamp": [
    "gmt_create", "gmtcreate", "created_at", "createdat", "create_time",
    ...
],
```

Add concise rewrite aliases if missing:

```python
"rewritten_query": [
    "rewritten_query", "rewrittenquery", "rewrite", "rewrite_query",
    "rewritten", "bot_rewrite", "bot_query", "expanded_query",
    "改写query", "改写", "改写后", "重写query",
],
```

**Step 4: Run parser tests**

Run:

```bash
cd backend
pytest tests/test_meta_id_gmt_create_parser.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/dataset_parser.py backend/tests/test_meta_id_gmt_create_parser.py
git commit -m "feat: import sessions by meta id and create time"
```

## Task 2: Add Dimension Granularity Metadata

**Files:**
- Create: `backend/app/services/eval_engine/dimension_metadata.py`
- Modify: `backend/app/schemas/eval_run.py`
- Modify: `backend/app/api/eval_runs.py`
- Modify: `frontend/lib/api.ts`
- Test: `backend/tests/test_dimension_metadata.py`

**Step 1: Write the failing backend test**

Create `backend/tests/test_dimension_metadata.py`:

```python
from app.services.eval_engine.dimension_metadata import DIMENSION_METADATA


def test_dim1_is_turn_level_and_dim2_is_session_level():
    assert DIMENSION_METADATA["dim1"]["granularity"] == "turn"
    assert DIMENSION_METADATA["dim1"]["first_turn_scored"] is False
    assert DIMENSION_METADATA["dim1"]["drilldown"] is True

    assert DIMENSION_METADATA["dim2"]["granularity"] == "session"
    assert DIMENSION_METADATA["dim2"]["first_turn_scored"] is None
    assert DIMENSION_METADATA["dim2"]["drilldown"] is False
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
pytest tests/test_dimension_metadata.py -v
```

Expected: FAIL because `dimension_metadata.py` does not exist.

**Step 3: Add metadata module**

Create `backend/app/services/eval_engine/dimension_metadata.py`:

```python
from __future__ import annotations

DIMENSION_METADATA: dict[str, dict] = {
    "dim1": {
        "name": "改写忠实性",
        "granularity": "turn",
        "first_turn_scored": False,
        "drilldown": True,
    },
    "dim2": {
        "name": "跨轮记忆保留",
        "granularity": "session",
        "first_turn_scored": None,
        "drilldown": False,
    },
    "dim3": {
        "name": "意图边界识别",
        "granularity": "turn",
        "first_turn_scored": False,
        "drilldown": True,
    },
    "dim4": {
        "name": "指代消解准确性",
        "granularity": "turn",
        "first_turn_scored": False,
        "drilldown": True,
    },
    "dim5": {
        "name": "重复请求处理",
        "granularity": "turn",
        "first_turn_scored": False,
        "drilldown": True,
    },
    "dim6": {
        "name": "用户纠错响应",
        "granularity": "session",
        "first_turn_scored": None,
        "drilldown": False,
    },
}
```

**Step 4: Expose metadata in dashboard response**

In `backend/app/schemas/eval_run.py`, add:

```python
class DimensionMeta(BaseModel):
    name: str
    granularity: str
    first_turn_scored: bool | None
    drilldown: bool
```

Add to `EvalRunDashboard`:

```python
dimension_metadata: dict[str, DimensionMeta]
```

In `backend/app/api/eval_runs.py`, import metadata and include it in `get_dashboard`:

```python
from app.services.eval_engine.dimension_metadata import DIMENSION_METADATA
...
return EvalRunDashboard(
    run=run,
    dimension_summary=summary,
    score_distribution=buckets,
    dimension_metadata=DIMENSION_METADATA,
)
```

Update `frontend/lib/api.ts` `EvalRunDashboard` type to include `dimension_metadata`.

**Step 5: Run tests**

Run:

```bash
cd backend
pytest tests/test_dimension_metadata.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/app/services/eval_engine/dimension_metadata.py backend/app/schemas/eval_run.py backend/app/api/eval_runs.py frontend/lib/api.ts backend/tests/test_dimension_metadata.py
git commit -m "feat: expose dimension granularity metadata"
```

## Task 3: Align Dim1 Prompt With Multiplicative Scoring

**Files:**
- Modify: `backend/app/services/eval_engine/prompts.py`
- Modify: `backend/app/services/eval_engine/prompts_v4_templates.py`
- Modify: `backend/app/services/eval_engine/prompts_v5_templates.py`
- Add migration if DB prompt seed is active: `backend/alembic/versions/0015_dim1_multiplicative_score.py`
- Test: `backend/tests/test_dim1_prompt_scoring_contract.py`

**Step 1: Write failing contract test**

Create `backend/tests/test_dim1_prompt_scoring_contract.py`:

```python
from app.services.eval_engine.prompts_v5_templates import DIM1_TEMPLATE_V5


def test_dim1_prompt_requires_multiplicative_score():
    assert "overall_score" in DIM1_TEMPLATE_V5
    assert "A * B * C" in DIM1_TEMPLATE_V5 or "A_completeness * B_no_hallucination * C_reasonable_completion" in DIM1_TEMPLATE_V5
    assert "(A+B+C)/3" not in DIM1_TEMPLATE_V5.replace(" ", "")
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
pytest tests/test_dim1_prompt_scoring_contract.py -v
```

Expected: FAIL if v5 still says `(A+B+C)/3`.

**Step 3: Update dim1 templates**

In all active dim1 prompt templates, replace average scoring text with:

```text
"overall_score": A_completeness * B_no_hallucination * C_reasonable_completion
```

Keep JSON output fields unchanged:

```json
{
  "A_completeness": 0,
  "B_no_hallucination": 0,
  "B_hallucinated_words": [],
  "C_reasonable_completion": 0,
  "overall_score": 0,
  "explanation": "..."
}
```

If prompt rows are seeded through Alembic, add `0015_dim1_multiplicative_score.py` to update the active dim1 prompt row.

**Step 4: Run prompt tests**

Run:

```bash
cd backend
pytest tests/test_dim1_prompt_scoring_contract.py tests/test_v5_prompt_render.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/eval_engine/prompts.py backend/app/services/eval_engine/prompts_v4_templates.py backend/app/services/eval_engine/prompts_v5_templates.py backend/alembic/versions/0015_dim1_multiplicative_score.py backend/tests/test_dim1_prompt_scoring_contract.py
git commit -m "fix: enforce multiplicative dim1 scoring"
```

## Task 4: Make Dim1 Evaluator Explicitly Session-In, Turn-Out

**Files:**
- Modify: `backend/app/services/eval_engine/evaluators.py`
- Test: `backend/tests/test_dim1_session_turn_contract.py`

**Step 1: Write failing evaluator test**

Create `backend/tests/test_dim1_session_turn_contract.py`:

```python
from app.services.eval_engine.evaluators import Dim1Evaluator


class FakeJudge:
    def __init__(self):
        self.messages = []

    def call(self, messages):
        self.messages.append(messages)
        return {
            "A_completeness": 1,
            "B_no_hallucination": 1,
            "B_hallucinated_words": [],
            "C_reasonable_completion": 1,
            "overall_score": 1,
            "explanation": "ok",
        }


class FakeRenderer:
    def render(self, code, **ctx):
        assert code == "dim1"
        assert "turns_text_full_session" in ctx
        assert "target_turn_index" in ctx
        return [{"role": "user", "content": ctx["turns_text_full_session"]}]


def test_dim1_skips_first_turn_and_scores_each_rewritten_turn():
    evaluator = Dim1Evaluator(FakeJudge(), FakeRenderer())
    evaluator.request_interval_sec = 0
    conversation = {
        "conversation_id": "s1",
        "turns": [
            {"turn_index": 1, "user_query": "优衣库男士衬衫", "rewritten_query": None},
            {"turn_index": 2, "user_query": "看看短袖", "rewritten_query": "优衣库男士短袖"},
            {"turn_index": 3, "user_query": "200以内", "rewritten_query": "优衣库男士短袖 200以内"},
        ],
    }

    result = evaluator.evaluate(conversation)

    assert result["score"] == 1
    assert [t["turn_index"] for t in result["turn_scores"]] == [2, 3]
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
pytest tests/test_dim1_session_turn_contract.py -v
```

Expected: FAIL because the renderer context does not yet include `turns_text_full_session` or `target_turn_index`.

**Step 3: Implement full-session context**

In `backend/app/services/eval_engine/evaluators.py`, add a helper:

```python
def build_turns_text_for_dim1_session(all_turns: list[dict], target_turn_index: int) -> str:
    text = ""
    for t in all_turns:
        marker = " ← target" if t["turn_index"] == target_turn_index else ""
        text += f"  第{t['turn_index']}轮 用户query: {t['user_query']}{marker}\n"
        rq = t.get("rewritten_query") or "(首轮无改写)"
        text += f"  第{t['turn_index']}轮 改写query: {rq}\n"
    return text
```

In `Dim1Evaluator.evaluate`, pass:

```python
turns_text_full_session=build_turns_text_for_dim1_session(turns, turn["turn_index"]),
target_turn_index=turn["turn_index"],
```

Keep existing history fields for backward compatibility with old prompts.

**Step 4: Run evaluator tests**

Run:

```bash
cd backend
pytest tests/test_dim1_session_turn_contract.py tests/test_prompt_renderer_regression.py -v
```

Expected: PASS or update prompt regression snapshots if the new context is additive and does not change old templates.

**Step 5: Commit**

```bash
git add backend/app/services/eval_engine/evaluators.py backend/tests/test_dim1_session_turn_contract.py
git commit -m "feat: pass full session context to dim1 evaluator"
```

## Task 5: Restore Dim2 Session Memory Prompt Contract

**Files:**
- Modify: `backend/app/services/eval_engine/prompts.py`
- Modify: `backend/app/services/eval_engine/prompts_v4_templates.py`
- Modify: `backend/app/services/eval_engine/prompts_v5_templates.py`
- Add migration if active DB prompt must be updated: `backend/alembic/versions/0016_dim2_memory_retention_contract.py`
- Test: `backend/tests/test_dim2_prompt_contract.py`

**Step 1: Write failing prompt contract test**

Create `backend/tests/test_dim2_prompt_contract.py`:

```python
from app.services.eval_engine.prompts_v5_templates import DIM2_TEMPLATE_V5


def test_dim2_prompt_outputs_constraint_retention_contract():
    assert "extracted_constraints" in DIM2_TEMPLATE_V5
    assert "constraint_retention" in DIM2_TEMPLATE_V5
    assert "should_appear_in_turns" in DIM2_TEMPLATE_V5
    assert "actually_appeared_in" in DIM2_TEMPLATE_V5
    assert "false_inherited" not in DIM2_TEMPLATE_V5
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
pytest tests/test_dim2_prompt_contract.py -v
```

Expected: FAIL if active v5 dim2 still uses inherited/dropped self-report validation.

**Step 3: Update dim2 prompt**

Replace dim2 prompt body with the user-approved contract:

- Extract persistent constraints from all user queries.
- Determine when each constraint should persist.
- Check each turn's rewritten query.
- Output `extracted_constraints`, `constraint_retention`, `overall_score`, and `explanation`.

Keep optional bot metadata as supplemental context only. The score must not rely solely on bot self-reported `inherited_constraints`.

**Step 4: Run prompt and evaluator tests**

Run:

```bash
cd backend
pytest tests/test_dim2_prompt_contract.py tests/test_v5_prompt_render.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/eval_engine/prompts.py backend/app/services/eval_engine/prompts_v4_templates.py backend/app/services/eval_engine/prompts_v5_templates.py backend/alembic/versions/0016_dim2_memory_retention_contract.py backend/tests/test_dim2_prompt_contract.py
git commit -m "fix: restore dim2 session memory contract"
```

## Task 6: Enforce Dim2 Session-Only Result Storage

**Files:**
- Modify: `backend/app/tasks/eval_tasks.py`
- Test: `backend/tests/test_dim2_session_only_storage.py`

**Step 1: Write failing storage test**

Create `backend/tests/test_dim2_session_only_storage.py`. Use the existing DB fixtures in `backend/tests/conftest.py` if available. If not, add a service-level test around result handling.

Core assertion:

```python
def test_dim2_does_not_create_turn_results(db_session, completed_eval_case_with_dim2):
    case = completed_eval_case_with_dim2
    dim2_turn_rows = [
        tr for tr in case.turn_results if tr.dimension_code == "dim2"
    ]
    assert dim2_turn_rows == []
    assert case.dim2_score is not None
    assert "dim2" in case.dim_results_full
```

**Step 2: Run test to verify behavior**

Run:

```bash
cd backend
pytest tests/test_dim2_session_only_storage.py -v
```

Expected: PASS if current behavior already stores no dim2 `EvalTurnResult`; otherwise FAIL.

**Step 3: Implement guard if needed**

In `backend/app/tasks/eval_tasks.py`, only create `EvalTurnResult` rows when the evaluator returns `turn_scores`. Ensure dim2 and dim6 session-level evaluators return no `turn_scores`.

No schema change should be needed.

**Step 4: Run related tests**

Run:

```bash
cd backend
pytest tests/test_dim2_session_only_storage.py tests/test_exporter_v2_per_query.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/tasks/eval_tasks.py backend/tests/test_dim2_session_only_storage.py
git commit -m "test: lock dim2 session-only storage"
```

## Task 7: Add Session Detail API for Drill-Down Rules

**Files:**
- Modify: `backend/app/schemas/badcase.py`
- Modify: `backend/app/api/eval_runs.py`
- Test: `backend/tests/test_case_full_dimension_granularity.py`

**Step 1: Write failing API schema test**

Create `backend/tests/test_case_full_dimension_granularity.py`:

```python
def test_case_full_includes_dimension_metadata(client, seeded_completed_run):
    run_id, case_id = seeded_completed_run

    resp = client.get(f"/api/eval-runs/{run_id}/cases/{case_id}/full")

    assert resp.status_code == 200
    body = resp.json()
    assert body["dimension_metadata"]["dim1"]["drilldown"] is True
    assert body["dimension_metadata"]["dim2"]["drilldown"] is False
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
pytest tests/test_case_full_dimension_granularity.py -v
```

Expected: FAIL because case full response does not include `dimension_metadata`.

**Step 3: Add metadata to case detail**

In `backend/app/schemas/badcase.py`, add:

```python
from app.schemas.eval_run import DimensionMeta
...
dimension_metadata: dict[str, DimensionMeta]
```

In `backend/app/api/eval_runs.py`, include `dimension_metadata=DIMENSION_METADATA` in `CaseFullDetail`.

**Step 4: Run API tests**

Run:

```bash
cd backend
pytest tests/test_case_full_dimension_granularity.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/schemas/badcase.py backend/app/api/eval_runs.py backend/tests/test_case_full_dimension_granularity.py
git commit -m "feat: include dimension drilldown metadata in case detail"
```

## Task 8: Update Badcase Drawer Drill-Down UI

**Files:**
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/app/eval-runs/[id]/badcases/page.tsx`
- Test manually with browser after dev server starts.

**Step 1: Update frontend types**

In `frontend/lib/api.ts`, extend `CaseFullDetail`:

```ts
export type DimensionMeta = {
  name: string;
  granularity: "turn" | "session";
  first_turn_scored: boolean | null;
  drilldown: boolean;
};

export type CaseFullDetail = {
  ...
  dimension_metadata: Record<string, DimensionMeta>;
};
```

**Step 2: Render dim1 turn-level drilldown**

In `frontend/app/eval-runs/[id]/badcases/page.tsx`, add a helper:

```ts
function turnResultsByDim(detail: CaseFullDetail, dim: string) {
  return detail.turn_results.filter((tr) => tr.dimension_code === dim);
}
```

For dim1, render a section below full conversation:

- Show first turn as `上下文轮，不参与维度一评分`.
- Show each non-first turn score.
- Show `judge_raw_response.A_completeness`, `B_no_hallucination`, `C_reasonable_completion`.
- Show `judge_raw_response.explanation`.

**Step 3: Render dim2 as session-only**

For dim2, show:

- `dim_results_full.dim2.detail.extracted_constraints`
- `dim_results_full.dim2.detail.constraint_retention`
- `dim_results_full.dim2.detail.explanation`

Do not render per-turn score rows for dim2. If users attempt to expand dim2, show a static note:

```text
维度二为 session 级评分，不提供 query 粒度分数。
```

**Step 4: Start frontend/backend dev stack**

Run the repo's existing command:

```bash
make dev
```

Expected: API at `http://localhost:8000`, frontend at `http://localhost:3000`.

**Step 5: Verify with Browser**

Open:

```text
http://localhost:3000/eval-runs/<run_id>/badcases
```

Expected:

- Drawer opens for a case.
- Dim1 shows query-level scores.
- First turn is labeled as context-only.
- Dim2 shows session-level constraint evidence and no query scores.

**Step 6: Commit**

```bash
git add frontend/lib/api.ts 'frontend/app/eval-runs/[id]/badcases/page.tsx'
git commit -m "feat: show dim1 query drilldown and dim2 session detail"
```

## Task 9: Update Dimension Detail Navigation Rules

**Files:**
- Modify: `frontend/app/eval-runs/[id]/page.tsx`
- Modify: `frontend/app/eval-runs/[id]/dimensions/page.tsx`
- Modify: `frontend/components/dimension-bar.tsx` if links are embedded there.

**Step 1: Use dashboard metadata**

In `frontend/app/eval-runs/[id]/page.tsx`, use `dash.dimension_metadata` to label dimensions:

- Turn-level dimensions: "可下钻至 query".
- Session-level dimensions: "session 级".

**Step 2: Prevent dim2 query-drilldown affordance**

In `frontend/app/eval-runs/[id]/dimensions/page.tsx`, if `slice.dim_code === "dim2"`:

- Keep Top badcase session links.
- Do not copy that suggests query expansion.
- Show caption: `维度二只产生 session 级评分。`

**Step 3: Manual browser check**

Open:

```text
http://localhost:3000/eval-runs/<run_id>
http://localhost:3000/eval-runs/<run_id>/dimensions?dim=dim2
```

Expected:

- Main dashboard communicates dim1 turn-level and dim2 session-level.
- Dim2 page has no query-level wording.

**Step 4: Commit**

```bash
git add 'frontend/app/eval-runs/[id]/page.tsx' 'frontend/app/eval-runs/[id]/dimensions/page.tsx' frontend/components/dimension-bar.tsx
git commit -m "feat: reflect dimension granularity in eval UI"
```

## Task 10: Export Required Three-Sheet Report

**Files:**
- Modify: `backend/app/services/exporter.py`
- Test: `backend/tests/test_exporter_agent_team_sheets.py`

**Step 1: Write failing export test**

Create `backend/tests/test_exporter_agent_team_sheets.py`:

```python
from io import BytesIO

from openpyxl import load_workbook

from app.services.exporter import export_eval_run_xlsx


def test_export_contains_agent_team_required_sheets(db_session, completed_eval_run):
    content = export_eval_run_xlsx(db_session, completed_eval_run.id)
    wb = load_workbook(BytesIO(content), read_only=True)

    assert "Session Overview" in wb.sheetnames
    assert "Dim1 Per Query" in wb.sheetnames
    assert "Dim2 Session Memory" in wb.sheetnames
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
pytest tests/test_exporter_agent_team_sheets.py -v
```

Expected: FAIL if current sheet names differ.

**Step 3: Add or rename sheets**

In `backend/app/services/exporter.py`, ensure xlsx export includes:

- `Session Overview`
- `Dim1 Per Query`
- `Dim2 Session Memory`

Minimum required columns:

`Session Overview`:

```text
meta_id, weighted_score, dim1_score, dim2_score, lowest_dim_code, badcase_summary
```

`Dim1 Per Query`:

```text
meta_id, turn_index, gmt_create, user_query, rewritten_query,
A_completeness, B_no_hallucination, C_reasonable_completion,
overall_score, badcase_analysis
```

`Dim2 Session Memory`:

```text
meta_id, overall_score, extracted_constraints, constraint_retention, explanation
```

**Step 4: Run exporter tests**

Run:

```bash
cd backend
pytest tests/test_exporter_agent_team_sheets.py tests/test_exporter_v2_per_query.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/exporter.py backend/tests/test_exporter_agent_team_sheets.py
git commit -m "feat: export agent team session and query sheets"
```

## Task 11: Add Evidence Audit Placeholder Contract

**Files:**
- Create: `backend/app/services/eval_engine/evidence_audit.py`
- Test: `backend/tests/test_evidence_audit_contract.py`

**Step 1: Write failing contract test**

Create `backend/tests/test_evidence_audit_contract.py`:

```python
from app.services.eval_engine.evidence_audit import audit_dimension_result


def test_audit_marks_low_confidence_hallucination_for_review():
    result = audit_dimension_result(
        dimension_code="dim1",
        session={"turns": [{"turn_index": 2, "user_query": "看看短袖"}]},
        judge_result={
            "B_no_hallucination": 0,
            "B_hallucinated_words": ["8年质保"],
            "explanation": "加入质保",
        },
    )

    assert result["needs_review"] is True
    assert result["audit_confidence"] in {"low", "medium", "high"}
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
pytest tests/test_evidence_audit_contract.py -v
```

Expected: FAIL because module does not exist.

**Step 3: Add simple deterministic audit**

Create `backend/app/services/eval_engine/evidence_audit.py`:

```python
from __future__ import annotations

from typing import Any


def audit_dimension_result(
    dimension_code: str,
    session: dict[str, Any],
    judge_result: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    needs_review = False

    if dimension_code == "dim1" and judge_result.get("B_no_hallucination") == 0:
        words = judge_result.get("B_hallucinated_words") or []
        if words:
            needs_review = True
            reasons.append("hallucination_words_require_evidence_check")

    if dimension_code == "dim2" and judge_result.get("overall_score") is not None:
        if judge_result["overall_score"] < 0.6:
            needs_review = True
            reasons.append("low_memory_retention_score")

    return {
        "needs_review": needs_review,
        "audit_confidence": "medium" if needs_review else "high",
        "reasons": reasons,
    }
```

Do not wire this into score mutation yet. This task only establishes the contract for future review queues.

**Step 4: Run tests**

Run:

```bash
cd backend
pytest tests/test_evidence_audit_contract.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/eval_engine/evidence_audit.py backend/tests/test_evidence_audit_contract.py
git commit -m "feat: add evidence audit contract"
```

## Task 12: Full Verification

**Files:**
- No file edits unless failures require fixes.

**Step 1: Run backend targeted tests**

Run:

```bash
cd backend
pytest \
  tests/test_meta_id_gmt_create_parser.py \
  tests/test_dimension_metadata.py \
  tests/test_dim1_prompt_scoring_contract.py \
  tests/test_dim1_session_turn_contract.py \
  tests/test_dim2_prompt_contract.py \
  tests/test_dim2_session_only_storage.py \
  tests/test_case_full_dimension_granularity.py \
  tests/test_exporter_agent_team_sheets.py \
  tests/test_evidence_audit_contract.py \
  -v
```

Expected: PASS.

**Step 2: Run existing backend regression tests**

Run:

```bash
cd backend
pytest tests -v
```

Expected: PASS.

**Step 3: Run frontend checks**

Run:

```bash
cd frontend
npm run lint
npm run build
```

Expected: PASS.

**Step 4: Manual UI verification**

Start the app:

```bash
make dev
```

Verify:

- Dataset upload maps `meta_id` as session and `gmt_create` as turn order.
- Eval run dashboard shows session weighted score and dimension scores.
- Badcase drawer shows dim1 query-level drilldown.
- Dim1 first turn is context-only.
- Dim2 shows session-level memory evidence and no query-level score expansion.
- XLSX export contains the three required sheets.

**Step 5: Final commit if any verification fixes were needed**

```bash
git add <fixed-files>
git commit -m "fix: complete agent team verification"
```

## Execution Handoff

Plan complete and saved to `docs/plans/2026-05-22-agent-team-multiturn-eval-implementation.md`.

Two execution options:

1. **Subagent-Driven (this session)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Parallel Session (separate)** - Open a new session with `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
