"""FastAPI 应用入口。"""
import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(title="多轮对话机评平台 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-API-Key"],
)


@app.get("/api/health")
def health():
    """Health endpoint 永远不需要鉴权（探活用）"""
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
