"""Scalable async processing.

Python equivalent of Sidekiq:
  - Celery (worker) -> async jobs (transcription, dispatch planning, evaluation).
  - Celery Beat     -> scheduled/recurring jobs.
  - Flower          -> listing/monitoring UI (see docker-compose).

Broker and result backend on Redis. Ships with queues split by load type, so
workers can scale independently.
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "certai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_acks_late=True,           # only acks after completing -> resilience
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # fair sharing for long (AI) tasks
    task_default_queue="default",
    task_routes={
        "app.workers.tasks.transcribe_audio": {"queue": "transcription"},
        "app.workers.tasks.plan_dispatch": {"queue": "whatsapp"},
        "app.workers.tasks.process_whatsapp_inbound": {"queue": "whatsapp"},
        "app.workers.tasks.evaluate_cohort_gaps": {"queue": "evaluation"},
        "app.workers.tasks.ingest_lesson_completion": {"queue": "evaluation"},
        "app.workers.tasks.ingest_track_material": {"queue": "evaluation"},
    },
)

# Scheduled jobs.
celery_app.conf.beat_schedule = {
    "nightly-gap-evaluation": {
        "task": "app.workers.tasks.sweep_evaluations",
        "schedule": crontab(hour=3, minute=0),  # every day at 03:00
    },
}

# Registers worker_process_init/shutdown for the persistent asyncio loop.
import app.workers.async_runner  # noqa: E402, F401
