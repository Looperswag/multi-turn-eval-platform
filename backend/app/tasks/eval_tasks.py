"""评测任务编排：execute_eval_run → evaluate_conversation_task × N → finalize_run。

W1 简化：在 execute_eval_run 内顺序遍历 conversation，每条调用一次同步 evaluator。
W2 会拆分为 group + chord 真正的 fan-out / fan-in（见方案 §4.2）。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

import redis as redis_sync

from app.core.config import DIMENSION_NAMES, settings
from app.tasks.celery_app import celery_app
from app.core.db import SessionLocal
from app.models import (
    BotRewrite,
    BotVersion,
    Conversation,
    EvalCaseResult,
    EvalRun,
    EvalTurnResult,
    JudgeModel,
    JudgePromptVersion,
    Turn,
)
from app.services.eval_engine import (
    ALL_EVALUATOR_CLASSES,
    PromptRenderer,
    build_judge_client,
)
from app.services.scoring import (
    conversation_weighted_score,
    run_overall_score,
    run_pass_rate,
)

logger = logging.getLogger(__name__)
_redis = redis_sync.Redis.from_url(settings.redis_url, decode_responses=True)


def _publish(run_id: int, payload: dict) -> None:
    try:
        _redis.publish(f"eval_run:{run_id}:progress", json.dumps(payload, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        logger.warning("publish progress failed: %s", exc)


def _load_conversation_payload(db, conv: Conversation, bot_version_id: int) -> dict:
    """把 ORM conversation + bot_rewrite join 成 evaluator 期待的 dict 结构。"""
    rows = (
        db.query(Turn, BotRewrite.rewritten_query)
        .outerjoin(
            BotRewrite,
            (BotRewrite.turn_id == Turn.id) & (BotRewrite.bot_version_id == bot_version_id),
        )
        .filter(Turn.conversation_id == conv.id)
        .order_by(Turn.turn_index)
        .all()
    )
    return {
        "conversation_id": conv.conversation_id_src,
        "total_turns": conv.total_turns,
        "turns": [
            {
                "query_id": f"{conv.conversation_id_src}_q{t.turn_index}",
                "turn_index": t.turn_index,
                "user_query": t.user_query,
                "rewritten_query": rewrite,
                "timestamp": t.timestamp,
            }
            for t, rewrite in rows
        ],
    }


@celery_app.task(bind=True, name="execute_eval_run")
def execute_eval_run(self, eval_run_id: int) -> dict:
    db = SessionLocal()
    try:
        run = db.get(EvalRun, eval_run_id)
        if not run:
            return {"error": "run not found"}
        run.status = "running"
        run.started_at = datetime.utcnow()
        db.commit()

        judge_model = db.get(JudgeModel, run.judge_model_id)
        if not judge_model:
            run.status = "failed"
            db.commit()
            _publish(eval_run_id, {"event": "run_failed", "reason": "judge_model not found"})
            return {"error": "judge_model not found"}

        judge_client = build_judge_client(
            judge_model.provider,
            model_id=judge_model.model_id,
            temperature=judge_model.temperature,
        )

        # A.3 改造：从 DB JudgePromptVersion 读模板（jinja2），交给 PromptRenderer。
        # run.judge_prompt_version_ids 形如 {"dim1": 1, "dim2": 2, ...}
        prompt_version_ids = run.judge_prompt_version_ids or {}
        templates: dict[str, str] = {}
        for code in run.dimensions_selected:
            pv_id = prompt_version_ids.get(code)
            if pv_id is None:
                continue
            pv = db.get(JudgePromptVersion, pv_id)
            if pv and pv.prompt_template:
                templates[code] = pv.prompt_template
        # P0: PromptRenderer 构造时编译所有模板（eager），语法错误会抛 TemplateSyntaxError。
        # 必须把 run 标 failed 后再抛，否则会卡在 running。
        try:
            renderer = PromptRenderer(templates)
        except Exception as exc:  # noqa: BLE001
            logger.exception("PromptRenderer init failed for run %s", eval_run_id)
            run.status = "failed"
            run.finished_at = datetime.utcnow()
            db.commit()
            _publish(
                eval_run_id,
                {"event": "run_failed", "reason": f"prompt template error: {exc}"},
            )
            return {"error": "prompt template syntax error", "detail": str(exc)}

        evaluators = {
            code: ALL_EVALUATOR_CLASSES[code](judge_client, renderer)
            for code in run.dimensions_selected
            if code in ALL_EVALUATOR_CLASSES and code in templates
        }

        conv_q = (
            db.query(Conversation)
            .filter(Conversation.dataset_id == run.dataset_id)
            .order_by(Conversation.id)
        )
        if run.sampling_count:
            conv_q = conv_q.limit(run.sampling_count)
        conversations = conv_q.all()

        run.total = len(conversations)
        db.commit()
        _publish(eval_run_id, {"event": "run_started", "total": run.total})

        completed = 0
        failed = 0
        weighted_scores: list[float | None] = []

        for conv in conversations:
            # 取消检查
            db.refresh(run)
            if run.status == "cancelled":
                _publish(eval_run_id, {"event": "run_cancelled"})
                return {"status": "cancelled", "completed": completed}

            try:
                payload = _load_conversation_payload(db, conv, run.bot_version_id)
                dim_scores: dict[str, float | None] = {}
                full_results: dict[str, dict] = {}
                case = EvalCaseResult(eval_run_id=eval_run_id, conversation_id=conv.id)
                db.add(case)
                db.flush()

                for code, evaluator in evaluators.items():
                    result = evaluator.evaluate(payload)
                    score = result.get("score")
                    dim_scores[code] = score
                    setattr(case, f"{code}_score", score)
                    full_results[code] = result

                    # 写 turn 级（若维度提供 turn_scores）
                    for ts in result.get("turn_scores", []) or []:
                        db.add(
                            EvalTurnResult(
                                eval_case_result_id=case.id,
                                turn_index=ts.get("turn_index", 0),
                                dimension_code=code,
                                score=ts.get("score"),
                                applicable=ts.get("applicable"),
                                judge_raw_response=ts.get("detail"),
                            )
                        )

                weighted, lowest = conversation_weighted_score(dim_scores)
                case.weighted_score = weighted
                case.lowest_dim_code = lowest
                case.dim_results_full = full_results

                weighted_scores.append(weighted)
                completed += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("case eval failed: conv_id=%s", conv.id)
                failed += 1
                # case 已加入 session，标记 error
                case.error = str(exc)
            finally:
                run.completed = completed
                run.failed = failed
                db.commit()
                _publish(
                    eval_run_id,
                    {
                        "event": "case_completed",
                        "completed": completed,
                        "failed": failed,
                        "total": run.total,
                    },
                )

        # finalize
        run.weighted_score = run_overall_score(weighted_scores)
        run.pass_rate = run_pass_rate(weighted_scores)
        run.status = "success" if failed == 0 else ("partial" if completed > 0 else "failed")
        run.finished_at = datetime.utcnow()
        db.commit()

        _publish(
            eval_run_id,
            {
                "event": "run_finished",
                "status": run.status,
                "weighted_score": run.weighted_score,
                "pass_rate": run.pass_rate,
            },
        )
        return {
            "status": run.status,
            "completed": completed,
            "failed": failed,
            "weighted_score": run.weighted_score,
        }
    finally:
        db.close()
