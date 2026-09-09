"""Celery application and beat schedule.

Redis is the broker and result backend. The beat schedule periodically enqueues
the "poll due RSS sources" task; individual source ingests run as separate
tasks so failures are isolated per source.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "ethiotimes",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="ingestion",
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.beat_schedule = {
    "poll-due-rss-sources-every-5-min": {
        "task": "app.workers.tasks.poll_due_sources",
        "schedule": crontab(minute="*/5"),
    },
    "poll-pending-articles-every-2-min": {
        "task": "app.workers.tasks.poll_pending_articles",
        "schedule": crontab(minute="*/2"),
    },
    "poll-pending-verifications-every-2-min": {
        "task": "app.workers.tasks.poll_pending_verifications",
        "schedule": crontab(minute="*/2"),
    },
    "source-health-sweep-hourly": {
        "task": "app.workers.tasks.source_health_sweep",
        "schedule": crontab(minute=0),
    },
}
