"""
Celery Application Configuration
"""

import os
import logging
from celery import Celery
from config import get_config

logger = logging.getLogger(__name__)

# Get configuration
config = get_config()

# Create Celery app instance
celery_app = Celery(
    'ocr_tasks',
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND,
    include=['tasks.ocr_tasks']
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes hard limit (reduced - should be enough for most images)
    task_soft_time_limit=540,  # 9 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=10,  # Restart worker after 10 tasks to prevent memory leaks
    worker_concurrency=1,  # Use only 1 worker to avoid multiple model loads (CRITICAL FIX)
    result_expires=3600,  # Results expire after 1 hour
)

logger.info(f"Celery app configured with broker: {config.CELERY_BROKER_URL}")
