"""SSE 端点：订阅一次 run 的实时进度。"""
import asyncio
import json
import logging

import redis.asyncio as redis_async
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.config import settings

router = APIRouter(prefix="/api/eval-runs", tags=["sse"])

logger = logging.getLogger(__name__)


@router.get("/{run_id}/stream")
async def stream_run_progress(run_id: int):
    async def event_generator():
        client = redis_async.from_url(settings.redis_url, decode_responses=True)
        pubsub = client.pubsub()
        channel = f"eval_run:{run_id}:progress"
        await pubsub.subscribe(channel)
        try:
            yield "event: connected\ndata: {}\n\n"
            async for msg in pubsub.listen():
                if msg["type"] != "message":
                    continue
                try:
                    data = msg["data"]
                    payload = json.loads(data) if isinstance(data, str) else data
                except (TypeError, json.JSONDecodeError):
                    payload = {"raw": str(msg["data"])}
                yield f"event: progress\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                if payload.get("event") in ("run_finished", "run_failed", "run_cancelled"):
                    break
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            await client.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
