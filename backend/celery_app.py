"""Celery factory.

Run the worker with:
    celery -A celery_app worker --loglevel=info

The route handler in `app/routes/runs.py` falls back to a daemon thread when
Redis isn't reachable, so local dev doesn't strictly require the worker.
"""
from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "preflight",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="preflight.run_pipeline")
def run_pipeline_task(run_id: str) -> str:
    from app.tasks import run_pipeline

    run_pipeline(run_id)
    return run_id
