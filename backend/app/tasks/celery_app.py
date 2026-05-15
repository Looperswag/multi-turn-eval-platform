"""Celery 应用入口。worker 启动命令：celery -A app.tasks.celery_app worker。"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "eval_platform",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,  # 长任务不预取，避免饿死
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
)

# 触发 task 模块导入，注册到 celery
from app.tasks import eval_tasks  # noqa: E402,F401
