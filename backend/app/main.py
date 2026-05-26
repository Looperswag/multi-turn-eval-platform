"""FastAPI 应用入口。"""
import logging

import defusedxml
import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.core.config import settings
from app.api import (
    datasets,
    bots,
    judge_config,
    eval_runs,
    sse,
    comparisons,
    annotations,
    badcases,
    regression_sets,
)
from app.api.deps import require_api_key

# M2.3: structlog JSON 日志（统一 timestamp / level / event / 上下文 key/value）
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    cache_logger_on_first_use=True,
)
logging.basicConfig(level=logging.INFO, format="%(message)s")

# 防御 xlsx / xml 解析的 XXE / billion-laughs / quadratic-blowup 攻击。
# openpyxl 走 stdlib 的 xml.etree，defuse_stdlib() 会 monkey-patch 让其默认安全。
defusedxml.defuse_stdlib()

limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])

app = FastAPI(title="多轮对话机评平台 API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# M2.3: prometheus 指标 — Instrumentator 自带 http_requests_total +
# http_request_duration_seconds (含 p50/p95/p99) 等；mount /metrics 端点
Instrumentator(
    should_group_status_codes=False,
    excluded_handlers=["/metrics", "/api/health"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# 自定义 gauge：SSE active connections + Celery queue depth（由 sse.py 与
# celery_app.py 在事件回调里更新）
sse_active_connections = Gauge(
    "eval_platform_sse_active_connections",
    "Number of currently active SSE long-poll connections.",
)
celery_queue_depth = Gauge(
    "eval_platform_celery_queue_depth",
    "Pending tasks in the default Celery queue (sampled from Redis LLEN).",
)


@app.on_event("startup")
async def _start_queue_depth_poller() -> None:
    """每 10 秒查 Redis LLEN celery 队列，更新 gauge。

    单进程一份后台任务足够；多 worker 部署时由 prometheus 端做去重。
    """
    import asyncio
    import redis.asyncio as redis_async

    redis_client = redis_async.from_url(settings.redis_url, decode_responses=True)

    async def _poll():
        while True:
            try:
                depth = await redis_client.llen("celery")
                celery_queue_depth.set(depth)
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(10)

    asyncio.create_task(_poll())

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-API-Key"],
)


@app.get("/api/health")
@limiter.exempt
def health(request: Request):
    """Health endpoint 永远不需要鉴权 + 不计入 rate-limit（探活用）"""
    return {"status": "ok"}


# C.4：所有业务路由统一加 X-API-Key 鉴权（受 settings.require_api_key 开关控制）
_authed = [Depends(require_api_key)]
app.include_router(datasets.router, dependencies=_authed)
app.include_router(bots.router, dependencies=_authed)
app.include_router(judge_config.router, dependencies=_authed)
app.include_router(eval_runs.router, dependencies=_authed)
app.include_router(sse.router, dependencies=_authed)
app.include_router(comparisons.router, dependencies=_authed)
app.include_router(annotations.router, dependencies=_authed)
app.include_router(badcases.router, dependencies=_authed)
app.include_router(regression_sets.router, dependencies=_authed)
