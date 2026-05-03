"""
backend/tasks/celery_app.py
────────────────────────────
Celery application configuration for FlowVest AI.

Usage:
  # Start worker:
  celery -A backend.tasks.celery_app worker --loglevel=info --concurrency=4

  # Start Flower (monitoring UI):
  celery -A backend.tasks.celery_app flower --port=5555

  # Inspect workers:
  celery -A backend.tasks.celery_app inspect ping

Configuration:
  - Broker: Redis (for task queue)
  - Backend: Redis (for task results)
  - Serialization: JSON
  - Timezone: UTC
  - Task acknowledgements: late (after task completes)
"""
from __future__ import annotations

import logging
from celery import Celery
from celery.schedules import crontab

from backend.config import settings

logger = logging.getLogger(__name__)

# ── Celery Application ─────────────────────────────────────────────────────────
celery_app = Celery(
    "flowvest",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "backend.tasks.portfolio_tasks",
        # Add more task modules here as the system grows:
        # "backend.tasks.notification_tasks",
        # "backend.tasks.analytics_tasks",
    ],
)

# ── Configuration ──────────────────────────────────────────────────────────────
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_acks_late=True,              # Acknowledge after task completes (not before)
    task_reject_on_worker_lost=True,  # Re-queue task if worker dies
    task_track_started=True,          # Track task state (STARTED, SUCCESS, FAILURE)
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,

    # Result backend
    result_expires=3600,              # Expire results after 1 hour
    result_persistent=True,           # Store results in backend

    # Rate limiting
    worker_prefetch_multiplier=1,     # Fetch 1 task at a time (fair scheduling)
    worker_max_tasks_per_child=1000,  # Recycle worker after 1000 tasks (memory leak prevention)

    # Retries
    task_autoretry_for=(Exception,),
    task_retry_backoff=2,             # Exponential backoff: 2s, 4s, 8s...
    task_retry_backoff_max=600,       # Max 10 minutes between retries
    task_max_retries=3,

    # Monitoring
    worker_send_task_events=True,     # Send events for Flower monitoring
    task_send_sent_event=True,

    # Broker connection
    broker_heartbeat=30,              # Keep connection alive
    broker_connection_retry_on_startup=True,
)

# ── Periodic Tasks (Optional) ──────────────────────────────────────────────────
# Uncomment to enable scheduled tasks (requires Celery Beat)
# celery_app.conf.beat_schedule = {
#     "cleanup-old-executions": {
#         "task": "backend.tasks.cleanup_tasks.cleanup_old_executions",
#         "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM UTC
#         "args": (30,),  # Delete executions older than 30 days
#     },
#     "aggregate-daily-metrics": {
#         "task": "backend.tasks.analytics_tasks.aggregate_daily_metrics",
#         "schedule": crontab(hour=0, minute=0),  # Daily at midnight UTC
#     },
# }

# ── Task Routing (Optional) ────────────────────────────────────────────────────
# Uncomment to enable task routing (multiple queues)
# celery_app.conf.task_routes = {
#     "backend.tasks.portfolio_tasks.*": {"queue": "portfolio"},
#     "backend.tasks.notification_tasks.*": {"queue": "notifications"},
# }

# ── Auto-Discover Tasks ────────────────────────────────────────────────────────
# Celery will auto-discover tasks in modules listed in `include` above.
# For more control, use:
# celery_app.autodiscover_tasks(["backend.tasks"])

# ── Logging Configuration ──────────────────────────────────────────────────────
# Structured logging for Celery tasks
try:
    import structlog

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
except ImportError:
    pass  # structlog not installed, use default logging

logger.info(
    "Celery app initialized",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    time_limit=settings.CELERY_TASK_TIME_LIMIT,
)
