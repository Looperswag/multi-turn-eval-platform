"""评测任务编排：execute_eval_run → evaluate_conversation_task × N → finalize_run。

W1 简化：在 execute_eval_run 内顺序遍历 conversation，每条调用一次同步 evaluator。
P0-1：把顺序遍历换成 ThreadPoolExecutor，并发度由 EvalRun.concurrency 控制。
评估器/judge client/PromptRenderer 都是 thread-safe（jinja2 渲染 + httpx 请求），
每个 worker 线程开独立 SQLAlchemy session 写 case；主线程聚合进度 + 取消检查。
"""
from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import redis as redis_sync

from app.core.config import DIMENSION_NAMES, settings
from app.tasks.celery_app import celery_app
from app.core.db import SessionLocal
from app.models import (
    BotRewrite,
    BotVersion,
    Conversation,
    EvalCallCost,
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
    set_cost_sink,
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
    """把 ORM conversation + bot_rewrite join 成 evaluator 期待的 dict 结构。

    A.4：payload 同时携带 BotRewrite 上的"线上 bot 元信息"五个字段，供 v5 prompts 使用。
    老数据这些字段全 NULL，v4 prompts 不引用所以无影响。
    """
    rows = (
        db.query(
            Turn,
            BotRewrite.rewritten_query,
            BotRewrite.bot_response,
            BotRewrite.intent_type,
            BotRewrite.inherited_constraints,
            BotRewrite.dropped_constraints,
            BotRewrite.needs_rewrite,
        )
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
                "bot_response": bot_resp,
                "intent_type": intent,
                "inherited_constraints": inh,
                "dropped_constraints": drop,
                "needs_rewrite": needs_rw,
            }
            for t, rewrite, bot_resp, intent, inh, drop, needs_rw in rows
        ],
    }


def _evaluate_one_conversation(
    eval_run_id: int,
    conv_id: int,
    bot_version_id: int,
    evaluators: dict,
    run_weights: dict | None,
) -> dict:
    """P0-1 worker：在独立 DB session 中评估一个 conversation，返回结果摘要。

    线程安全保证：
    - 不复用主线程的 db；走 SessionLocal() 自带 thread-local
    - evaluators / judge_client / prompt_renderer 都是 stateless 读端，跨线程共享 OK
    - case + turn_results 在本线程的事务里写完再 commit；如果失败回滚后再尝试写 error
    """
    db = SessionLocal()
    # M1.5: 本线程的成本回收袋；evaluator 调用 judge 时按 dim_code 累积
    cost_sink: list[dict] = []
    set_cost_sink(cost_sink)
    try:
        conv = db.get(Conversation, conv_id)
        if not conv:
            return {
                "conv_id": conv_id,
                "status": "error",
                "error": "conversation not found",
                "case_id": None,
            }

        case_id: int | None = None
        try:
            payload = _load_conversation_payload(db, conv, bot_version_id)
            dim_scores: dict[str, float | None] = {}
            full_results: dict[str, dict] = {}
            case = EvalCaseResult(eval_run_id=eval_run_id, conversation_id=conv.id)
            db.add(case)
            db.flush()
            case_id = case.id

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

            # M1.5: 把本 case 累积的成本写入 eval_call_cost
            for cost in cost_sink:
                db.add(
                    EvalCallCost(
                        eval_case_result_id=case.id,
                        dimension_code=cost["dimension_code"],
                        model_id=cost["model_id"],
                        prompt_tokens=cost["prompt_tokens"],
                        completion_tokens=cost["completion_tokens"],
                        cost_usd=cost["cost_usd"],
                        cost_cny=cost["cost_cny"],
                    )
                )

            weighted, lowest = conversation_weighted_score(dim_scores, weights=run_weights)
            case.weighted_score = weighted
            case.lowest_dim_code = lowest
            case.dim_results_full = full_results
            db.commit()
            return {
                "conv_id": conv_id,
                "status": "success",
                "case_id": case_id,
                "weighted_score": weighted,
                "dim_scores": dim_scores,
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("case eval failed: conv_id=%s", conv_id)
            db.rollback()
            # 尝试以新事务写入 error 标记（之前的 case 行因 rollback 已丢失）
            try:
                err_case = EvalCaseResult(
                    eval_run_id=eval_run_id,
                    conversation_id=conv_id,
                    error=str(exc)[:1000],
                )
                db.add(err_case)
                db.commit()
                case_id = err_case.id
            except Exception:
                db.rollback()
            return {
                "conv_id": conv_id,
                "status": "error",
                "case_id": case_id,
                "error": str(exc),
            }
    finally:
        set_cost_sink(None)
        db.close()


# ====================================================================
# M2.5: DRY 提取 — execute_eval_run 与 retry_failed_cases 共享的两段
# ====================================================================


def _build_eval_components(db: Session, run: EvalRun):
    """构建 (judge_client, renderer, evaluators) 三件套。

    返回 None 表示 judge_model 缺失（caller 负责打 failed + publish）。
    PromptRenderer 模板语法错误会抛出，caller 用 try/except 处理。
    """
    judge_model = db.get(JudgeModel, run.judge_model_id)
    if not judge_model:
        return None
    judge_client = build_judge_client(
        judge_model.provider,
        model_id=judge_model.model_id,
        temperature=judge_model.temperature,
    )
    prompt_version_ids = run.judge_prompt_version_ids or {}
    templates: dict[str, str] = {}
    strategies: dict[str, str] = {}
    for code in run.dimensions_selected:
        pv_id = prompt_version_ids.get(code)
        if pv_id is None:
            continue
        pv = db.get(JudgePromptVersion, pv_id)
        if pv and pv.prompt_template:
            templates[code] = pv.prompt_template
            strategies[code] = pv.dimension_strategy or "per_turn"
    renderer = PromptRenderer(templates, strategies=strategies)  # may raise
    evaluators = {
        code: ALL_EVALUATOR_CLASSES[code](judge_client, renderer)
        for code in run.dimensions_selected
        if code in ALL_EVALUATOR_CLASSES and code in templates
    }
    return judge_client, renderer, evaluators


def _run_conversations_parallel(
    *,
    eval_run_id: int,
    conversations: list,
    evaluators: dict,
    run_weights: dict | None,
    bot_version_id: int,
    db: Session,
    run: EvalRun,
    is_retry: bool = False,
    completed_initial: int = 0,
) -> dict:
    """ThreadPoolExecutor 并行执行 _evaluate_one_conversation，
    带 cancel 检测 + 增量 publish。

    Returns: {"completed", "failed", "weighted_scores", "cancelled"}.
    """
    completed = completed_initial
    failed = 0
    weighted_scores: list[float | None] = []
    if not conversations:
        return {
            "completed": completed,
            "failed": failed,
            "weighted_scores": weighted_scores,
            "cancelled": False,
        }

    cancel_event = threading.Event()
    publish_lock = threading.Lock()
    start_time = time.monotonic()
    max_workers = min(
        max(int(getattr(run, "concurrency", 5) or 5), 1), len(conversations)
    )

    def _check_cancelled() -> bool:
        db.refresh(run)
        return run.status == "cancelled"

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_conv = {
            pool.submit(
                _evaluate_one_conversation,
                eval_run_id,
                conv.id,
                bot_version_id,
                evaluators,
                run_weights,
            ): conv
            for conv in conversations
        }
        for fut in as_completed(future_to_conv):
            conv = future_to_conv[fut]
            if cancel_event.is_set() or _check_cancelled():
                cancel_event.set()
                continue
            try:
                result = fut.result()
            except Exception as exc:  # noqa: BLE001
                logger.exception("future error for conv_id=%s", conv.id)
                result = {
                    "conv_id": conv.id,
                    "status": "error",
                    "case_id": None,
                    "error": str(exc),
                }
            with publish_lock:
                is_success = result["status"] == "success"
                if is_success:
                    completed += 1
                    weighted_scores.append(result["weighted_score"])
                else:
                    failed += 1
                run.completed = completed
                run.failed = failed
                db.commit()
                elapsed = time.monotonic() - start_time
                processed = completed + failed
                avg = elapsed / max(processed, 1)
                eta_seconds = round(avg * max(run.total - processed, 0))
                payload = {
                    "event": "case_completed" if is_success else "case_failed",
                    "completed": completed,
                    "failed": failed,
                    "total": run.total,
                    "eta_seconds": eta_seconds,
                    "conversation_id": conv.id,
                    "case_id": result.get("case_id"),
                }
                if is_success:
                    payload["dim_scores"] = result.get("dim_scores")
                else:
                    payload["error_message"] = result.get("error")
                if is_retry:
                    payload["retry"] = True
                _publish(eval_run_id, payload)

    return {
        "completed": completed,
        "failed": failed,
        "weighted_scores": weighted_scores,
        "cancelled": cancel_event.is_set(),
    }


# ====================================================================
# Celery tasks
# ====================================================================


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

        try:
            components = _build_eval_components(db, run)
        except Exception as exc:  # noqa: BLE001 — Jinja2 模板语法错误
            logger.exception("PromptRenderer init failed for run %s", eval_run_id)
            run.status = "failed"
            run.finished_at = datetime.utcnow()
            db.commit()
            _publish(
                eval_run_id,
                {"event": "run_failed", "reason": f"prompt template error: {exc}"},
            )
            return {"error": "prompt template syntax error", "detail": str(exc)}
        if components is None:
            run.status = "failed"
            db.commit()
            _publish(eval_run_id, {"event": "run_failed", "reason": "judge_model not found"})
            return {"error": "judge_model not found"}
        _, _, evaluators = components

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
        _publish(
            eval_run_id,
            {"event": "run_started", "total": run.total, "resume_from": len(existing_conv_ids)},
        )

        stats = _run_conversations_parallel(
            eval_run_id=eval_run_id,
            conversations=conversations,
            evaluators=evaluators,
            run_weights=run.dimension_weights or None,
            bot_version_id=run.bot_version_id,
            db=db,
            run=run,
            is_retry=False,
            completed_initial=len(existing_conv_ids),
        )
        completed = stats["completed"]
        failed = stats["failed"]

        if stats["cancelled"]:
            _publish(eval_run_id, {"event": "run_cancelled"})
            return {"status": "cancelled", "completed": completed}

        # finalize
        run.weighted_score = run_overall_score(stats["weighted_scores"])
        run.pass_rate = run_pass_rate(stats["weighted_scores"])
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

        # M2.5: 通过共享 helper 构建组件（templates 校验、judge_client 等）
        try:
            components = _build_eval_components(db, run)
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
        if components is None:
            run.status = "failed"
            db.commit()
            _publish(eval_run_id, {"event": "run_failed", "reason": "judge_model not found"})
            return {"error": "judge_model not found"}
        _, _, evaluators = components

        # 拉取要重跑的 conversations
        conversations = (
            db.query(Conversation)
            .filter(Conversation.id.in_(conv_ids))
            .order_by(Conversation.id)
            .all()
        )
        _publish(
            eval_run_id,
            {
                "event": "run_started",
                "total": run.total,
                "retry": True,
                "retry_count": len(conversations),
            },
        )

        # M2.5: 重试路径加 ThreadPoolExecutor — 与主路径性能对齐
        completed_before = run.completed or 0
        stats = _run_conversations_parallel(
            eval_run_id=eval_run_id,
            conversations=conversations,
            evaluators=evaluators,
            run_weights=run.dimension_weights or None,
            bot_version_id=run.bot_version_id,
            db=db,
            run=run,
            is_retry=True,
            completed_initial=completed_before,
        )

        if stats["cancelled"]:
            _publish(eval_run_id, {"event": "run_cancelled"})
            return {"status": "cancelled"}

        # 重新计算整个 run 的总分（基于所有 success cases，含未重试的历史）
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
        run.status = (
            "success" if (run.failed or 0) == 0
            else ("partial" if (run.completed or 0) > 0 else "failed")
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
        succeeded = stats["completed"] - completed_before
        still_failed = stats["failed"]
        return {
            "status": run.status,
            "retried": len(conversations),
            "succeeded": succeeded,
            "still_failed": still_failed,
        }
    finally:
        db.close()
