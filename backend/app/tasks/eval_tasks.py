"""评测任务编排：execute_eval_run → evaluate_conversation_task × N → finalize_run。

W1 简化：在 execute_eval_run 内顺序遍历 conversation，每条调用一次同步 evaluator。
W2 会拆分为 group + chord 真正的 fan-out / fan-in（见方案 §4.2）。
"""
from __future__ import annotations

import json
import logging
import time
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
    RegressionSetItem,
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

        # C.2：若关联了 regression_set，则仅评测集合内 conversation（与 dataset 取交集）
        if run.regression_set_id is not None:
            item_subq = (
                db.query(RegressionSetItem.conversation_id)
                .filter(RegressionSetItem.regression_set_id == run.regression_set_id)
                .scalar_subquery()
            )
            conv_q = (
                db.query(Conversation)
                .filter(
                    Conversation.dataset_id == run.dataset_id,
                    Conversation.id.in_(item_subq),
                )
                .order_by(Conversation.id)
            )
            # 回归集模式下忽略 sampling_count（集合已定数）
        else:
            conv_q = (
                db.query(Conversation)
                .filter(Conversation.dataset_id == run.dataset_id)
                .order_by(Conversation.id)
            )
            if run.sampling_count:
                conv_q = conv_q.limit(run.sampling_count)
        conversations = conv_q.all()

        # C.5 dogfooding 发现的幂等性 bug 修复：
        # Celery acks_late=True + worker restart 时 task 会重投递。
        # 若 task 第二次启动，必须跳过已写入的 case，否则触发 UniqueConstraint(eval_run_id, conversation_id)
        # 导致 session 进入 PendingRollbackError 并永久 stuck。
        existing_conv_ids = {
            r.conversation_id
            for r in db.query(EvalCaseResult.conversation_id)
            .filter(EvalCaseResult.eval_run_id == eval_run_id)
            .all()
        }
        if existing_conv_ids:
            logger.info(
                "eval_run %s: resuming, skip %d already-evaluated cases",
                eval_run_id, len(existing_conv_ids),
            )
        conversations = [c for c in conversations if c.id not in existing_conv_ids]

        run.total = len(conversations) + len(existing_conv_ids)
        db.commit()
        _publish(eval_run_id, {"event": "run_started", "total": run.total, "resume_from": len(existing_conv_ids)})

        completed = len(existing_conv_ids)  # 已完成的 case 算入 progress
        failed = 0
        weighted_scores: list[float | None] = []
        # W2：每个 run 可携带自定义 dimension_weights；NULL 时 fallback DEFAULT
        run_weights = run.dimension_weights or None
        start_time = time.monotonic()

        for conv in conversations:
            # 取消检查
            db.refresh(run)
            if run.status == "cancelled":
                _publish(eval_run_id, {"event": "run_cancelled"})
                return {"status": "cancelled", "completed": completed}

            case: EvalCaseResult | None = None
            case_dim_scores: dict[str, float | None] = {}
            case_succeeded = False
            case_error: str | None = None
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

                weighted, lowest = conversation_weighted_score(dim_scores, weights=run_weights)
                case.weighted_score = weighted
                case.lowest_dim_code = lowest
                case.dim_results_full = full_results

                weighted_scores.append(weighted)
                completed += 1
                case_succeeded = True
                case_dim_scores = dim_scores
            except Exception as exc:  # noqa: BLE001
                logger.exception("case eval failed: conv_id=%s", conv.id)
                failed += 1
                case_error = str(exc)
                # case 已加入 session，标记 error
                if case is not None:
                    case.error = case_error
            finally:
                run.completed = completed
                run.failed = failed
                db.commit()

                # ETA 计算：基于平均耗时 × 剩余条数
                elapsed = time.monotonic() - start_time
                processed = completed + failed
                if processed > 0:
                    avg_per_case = elapsed / processed
                    remaining = max(run.total - processed, 0)
                    eta_seconds: int | None = round(avg_per_case * remaining)
                else:
                    eta_seconds = None

                if case_succeeded:
                    _publish(
                        eval_run_id,
                        {
                            "event": "case_completed",
                            "completed": completed,
                            "failed": failed,
                            "total": run.total,
                            "eta_seconds": eta_seconds,
                            "conversation_id": conv.id,
                            "case_id": case.id if case is not None else None,
                            "dim_scores": case_dim_scores,
                        },
                    )
                else:
                    _publish(
                        eval_run_id,
                        {
                            "event": "case_failed",
                            "completed": completed,
                            "failed": failed,
                            "total": run.total,
                            "eta_seconds": eta_seconds,
                            "conversation_id": conv.id,
                            "case_id": case.id if case is not None else None,
                            "error_message": case_error,
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


@celery_app.task(bind=True, name="retry_failed_cases")
def retry_failed_cases(self, eval_run_id: int, conv_ids: list[int]) -> dict:
    """C.3：只重跑指定的失败 conversations。

    复用 execute_eval_run 的核心逻辑（构建 judge / evaluator / renderer），
    但 conv_q 限制在 conv_ids 上。重跑前会把这些 conv 对应的 EvalCaseResult
    （含 error 的）删除，run.failed 减相应数量。
    """
    db = SessionLocal()
    try:
        run = db.get(EvalRun, eval_run_id)
        if not run:
            return {"error": "run not found"}

        # 已经在 running 中的 run 不允许重跑（避免并发写）
        if run.status == "running":
            return {"error": "run is already running"}

        # 找出指定 conv 的失败 case 并删除
        failed_cases = (
            db.query(EvalCaseResult)
            .filter(
                EvalCaseResult.eval_run_id == eval_run_id,
                EvalCaseResult.conversation_id.in_(conv_ids),
                EvalCaseResult.error.is_not(None),
            )
            .all()
        )
        deleted_count = len(failed_cases)
        for fc in failed_cases:
            db.delete(fc)
        run.failed = max((run.failed or 0) - deleted_count, 0)
        run.status = "running"
        run.finished_at = None
        db.commit()

        # 构建评测组件（与 execute_eval_run 同）
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
        prompt_version_ids = run.judge_prompt_version_ids or {}
        templates: dict[str, str] = {}
        for code in run.dimensions_selected:
            pv_id = prompt_version_ids.get(code)
            if pv_id is None:
                continue
            pv = db.get(JudgePromptVersion, pv_id)
            if pv and pv.prompt_template:
                templates[code] = pv.prompt_template
        try:
            renderer = PromptRenderer(templates)
        except Exception as exc:  # noqa: BLE001
            logger.exception("PromptRenderer init failed for retry run %s", eval_run_id)
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

        # 拉取要重跑的 conversations
        conversations = (
            db.query(Conversation)
            .filter(Conversation.id.in_(conv_ids))
            .order_by(Conversation.id)
            .all()
        )
        _publish(
            eval_run_id,
            {"event": "run_started", "total": run.total, "retry": True, "retry_count": len(conversations)},
        )

        completed_delta = 0
        failed_delta = 0
        new_weighted_scores: list[float | None] = []
        # W2：复用 run 的自定义权重；NULL fallback DEFAULT
        run_weights = run.dimension_weights or None
        start_time = time.monotonic()

        for conv in conversations:
            db.refresh(run)
            if run.status == "cancelled":
                _publish(eval_run_id, {"event": "run_cancelled"})
                return {"status": "cancelled"}

            case: EvalCaseResult | None = None
            case_dim_scores: dict[str, float | None] = {}
            case_succeeded = False
            case_error: str | None = None
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
                weighted, lowest = conversation_weighted_score(dim_scores, weights=run_weights)
                case.weighted_score = weighted
                case.lowest_dim_code = lowest
                case.dim_results_full = full_results
                new_weighted_scores.append(weighted)
                completed_delta += 1
                case_succeeded = True
                case_dim_scores = dim_scores
            except Exception as exc:  # noqa: BLE001
                logger.exception("retry case eval failed: conv_id=%s", conv.id)
                failed_delta += 1
                case_error = str(exc)
                if case is not None:
                    case.error = case_error
            finally:
                run.completed = (run.completed or 0) + (1 if case_succeeded else 0)
                run.failed = (run.failed or 0) + (1 if case_error else 0)
                db.commit()

                elapsed = time.monotonic() - start_time
                processed = completed_delta + failed_delta
                if processed > 0:
                    avg_per_case = elapsed / processed
                    remaining = max(len(conversations) - processed, 0)
                    eta_seconds: int | None = round(avg_per_case * remaining)
                else:
                    eta_seconds = None

                if case_succeeded:
                    _publish(
                        eval_run_id,
                        {
                            "event": "case_completed",
                            "completed": run.completed,
                            "failed": run.failed,
                            "total": run.total,
                            "eta_seconds": eta_seconds,
                            "conversation_id": conv.id,
                            "case_id": case.id if case is not None else None,
                            "dim_scores": case_dim_scores,
                            "retry": True,
                        },
                    )
                else:
                    _publish(
                        eval_run_id,
                        {
                            "event": "case_failed",
                            "completed": run.completed,
                            "failed": run.failed,
                            "total": run.total,
                            "eta_seconds": eta_seconds,
                            "conversation_id": conv.id,
                            "case_id": case.id if case is not None else None,
                            "error_message": case_error,
                            "retry": True,
                        },
                    )

        # 重新计算整个 run 的总分（基于所有 success cases）
        all_success = (
            db.query(EvalCaseResult)
            .filter(
                EvalCaseResult.eval_run_id == eval_run_id,
                EvalCaseResult.error.is_(None),
            )
            .all()
        )
        all_scores = [c.weighted_score for c in all_success]
        run.weighted_score = run_overall_score(all_scores)
        run.pass_rate = run_pass_rate(all_scores)
        run.status = "success" if (run.failed or 0) == 0 else (
            "partial" if (run.completed or 0) > 0 else "failed"
        )
        run.finished_at = datetime.utcnow()
        db.commit()
        _publish(
            eval_run_id,
            {
                "event": "run_finished",
                "status": run.status,
                "weighted_score": run.weighted_score,
                "pass_rate": run.pass_rate,
                "retry": True,
            },
        )
        return {
            "status": run.status,
            "retried": len(conversations),
            "succeeded": completed_delta,
            "still_failed": failed_delta,
        }
    finally:
        db.close()
