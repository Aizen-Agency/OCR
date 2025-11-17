"""
Celery Application Configuration with Redis Resilience
"""

import os
import logging
import time
from celery import Celery
from celery.signals import worker_ready, worker_shutting_down
import redis
from redis.exceptions import ResponseError, ConnectionError, AuthenticationError
from config import get_config
from utils.encoding import mask_redis_url

logger = logging.getLogger(__name__)

# Get configuration
config = get_config()

# Log the actual URLs being used for debugging (with masked password)
safe_broker_url = mask_redis_url(config.CELERY_BROKER_URL)
safe_backend_url = mask_redis_url(config.CELERY_RESULT_BACKEND)
logger.info(f"Initializing Celery with broker: {safe_broker_url}")
logger.info(f"Initializing Celery with backend: {safe_backend_url}")

# Create Celery app instance
celery_app = Celery(
    'ocr_tasks',
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND,
    include=['tasks.ocr_tasks', 'tasks.pdf_hybrid_tasks']
)

# Celery configuration - explicitly set broker and backend URLs with resilience
celery_app.conf.update(
    broker_url=config.CELERY_BROKER_URL,  # Explicit broker URL
    result_backend=config.CELERY_RESULT_BACKEND,  # Explicit result backend
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
    broker_connection_retry_on_startup=True,  # Retry connection on startup
    broker_connection_retry=True,  # Enable connection retries
    broker_connection_max_retries=100,  # Maximum retry attempts
    broker_connection_retry_delay=1.0,  # Initial retry delay
    broker_pool_limit=10,  # Connection pool limit
    broker_heartbeat=30,  # Heartbeat interval
    broker_transport_options={
        'visibility_timeout': 3600,
        'retry_policy': {
            'timeout': 5.0
        },
        'master_name': 'mymaster',  # For sentinel mode (not used, but helps with resilience)
    },
    # Result backend connection configuration - ensure Redis connection is maintained
    # These options are passed to the underlying Redis client to maintain connections
    result_backend_transport_options={
        'retry_policy': {
            'timeout': 5.0
        },
        'master_name': 'mymaster',
        'socket_connect_timeout': 5,
        'socket_keepalive': True,
        'health_check_interval': 30,
    },
    # Handle Redis connection errors gracefully
    task_acks_late=True,  # Acknowledge tasks after completion
    task_reject_on_worker_lost=True,  # Reject tasks if worker is lost
)

# Custom connection error handler
def handle_redis_error(exception, retry_count=0, max_retries=3):
    """
    Handle Redis connection errors with retry logic.
    
    Args:
        exception: The exception that occurred
        retry_count: Current retry attempt
        max_retries: Maximum number of retries
        
    Returns:
        bool: True if should retry, False otherwise
    """
    error_msg = str(exception).lower()
    
    # Handle Redis state changes (master -> replica)
    if isinstance(exception, ResponseError):
        if 'unblocked' in error_msg or 'instance state changed' in error_msg:
            if retry_count < max_retries:
                wait_time = 2 ** retry_count
                logger.warning(f"Redis state change detected, retrying in {wait_time}s (attempt {retry_count + 1}/{max_retries + 1})")
                time.sleep(wait_time)
                return True
            else:
                logger.error(f"Redis state change persisted after {max_retries + 1} attempts")
                return False
    
    # Handle connection errors
    if isinstance(exception, (ConnectionError, AuthenticationError)):
        if retry_count < max_retries:
            wait_time = 2 ** retry_count
            logger.warning(f"Redis connection error, retrying in {wait_time}s (attempt {retry_count + 1}/{max_retries + 1}): {str(exception)}")
            time.sleep(wait_time)
            return True
        else:
            logger.error(f"Redis connection failed after {max_retries + 1} attempts: {str(exception)}")
            return False
    
    return False

# Signal handlers for worker lifecycle
@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Handle worker ready signal - verify Redis connection."""
    logger.info("Worker ready - verifying Redis connection...")
    try:
        # Test broker connection
        with celery_app.connection() as conn:
            conn.ensure_connection(max_retries=3)
        logger.info("Redis broker connection verified")
    except Exception as e:
        logger.warning(f"Redis connection check failed (will retry): {str(e)}")

@worker_shutting_down.connect
def worker_shutting_down_handler(sender=None, **kwargs):
    """Handle worker shutdown signal."""
    logger.info("Worker shutting down - cleaning up connections...")

# Ensure result backend connection is established and maintained
def ensure_result_backend_connection():
    """Ensure Celery result backend connection is established."""
    try:
        backend = celery_app.backend
        if hasattr(backend, 'client'):
            # Force connection establishment by pinging
            backend.client.ping()
            logger.debug("Result backend connection verified")
            return True
    except Exception as e:
        logger.warning(f"Result backend connection check failed: {str(e)}")
        # Try to reconnect by resetting the connection pool
        try:
            if hasattr(backend, 'client') and hasattr(backend.client, 'connection_pool'):
                backend.client.connection_pool.disconnect()
                # Force a new connection
                backend.client.connection_pool.reset()
        except Exception as reset_error:
            logger.debug(f"Connection pool reset failed: {str(reset_error)}")
        return False
    return False

# Note: Connection errors are now handled in JobService._ensure_backend_connection()
# which is called before creating tasks. This ensures the connection is alive when needed.

logger.info(f"Celery app configured successfully")
logger.info(f"  Broker URL: {safe_broker_url}")
logger.info(f"  Result Backend: {safe_backend_url}")
logger.info("  Redis resilience: Enabled (retry on state changes, connection pooling)")
