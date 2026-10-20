"""Celery worker entrypoint for asynchronous TalentOS tasks."""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "talentos",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks", "app.automation"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=90,
    task_time_limit=120,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "talentos-recruitment-automation-every-15-minutes": {
            "task": "app.automation.run_recruitment_automation",
            "schedule": 900.0,
        },
    },
)
