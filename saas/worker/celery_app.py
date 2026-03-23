"""
saas/worker/celery_app.py
Celery application configuration with Redis broker.
"""
import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "shortforge",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["saas.worker.tasks", "saas.worker.callbacks", "saas.worker.beat"],
)

app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Reliability
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Timeouts
    task_soft_time_limit=int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "1800")),
    task_time_limit=int(os.getenv("CELERY_TASK_TIME_LIMIT", "2100")),
    # Retry
    task_default_retry_delay=30,
    task_max_retries=3,
    # Routing
    task_routes={
        "saas.worker.tasks.*": {"queue": "pipeline"},
        "saas.worker.callbacks.*": {"queue": "callbacks"},
    },
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Beat schedule
    beat_schedule={
        "check-schedules": {
            "task": "saas.worker.beat.check_schedules",
            "schedule": 60.0,
        },
    },
)
