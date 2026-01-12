"""
Queue Management Service - Monitors and manages Celery queue
"""
import logging
import signal
from typing import Dict, Any, Optional
from celery import current_app as celery_app
from config import get_config
from services.redis_service import RedisService
from services.resource_monitor import ResourceMonitor

logger = logging.getLogger(__name__)


class QueueService:
    """Service for monitoring and managing Celery queue."""
    
    def __init__(self, redis_service: Optional[RedisService] = None, resource_monitor: Optional[ResourceMonitor] = None):
        self.config = get_config()
        self.redis_service = redis_service
        self.resource_monitor = resource_monitor
        self.celery_app = celery_app
        
    def get_queue_size(self) -> int:
        """
        Get current queue size (pending tasks).

        Returns:
            Total number of tasks in queue (active + scheduled + reserved)
        """
        try:
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Queue size check timed out after 5 seconds")
            
            # Set 5 second timeout for Celery inspect
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(5)
            
            try:
                inspect = self.celery_app.control.inspect()
                active = inspect.active() or {}
                scheduled = inspect.scheduled() or {}
                reserved = inspect.reserved() or {}
                
                total = 0
                for worker_tasks in [active, scheduled, reserved]:
                    for tasks in worker_tasks.values():
                        total += len(tasks)
                return total
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        except TimeoutError:
            logger.warning("Queue size check timed out, assuming queue is empty")
            return 0
        except Exception as e:
            logger.error(f"Error getting queue size: {str(e)}")
            return 0
    
    def get_active_jobs_count(self) -> int:
        """
        Get count of active jobs (currently processing).
        
        Returns:
            Number of active tasks
        """
        try:
            inspect = self.celery_app.control.inspect()
            active = inspect.active() or {}
            count = sum(len(tasks) for tasks in active.values())
            return count
        except Exception as e:
            logger.error(f"Error getting active jobs count: {str(e)}")
            return 0
    
    def can_accept_new_job(self, estimated_pdf_size_mb: int = 500) -> Dict[str, Any]:
        """
        Check if system can accept a new job.
        
        Args:
            estimated_pdf_size_mb: Estimated PDF size in MB (default: 500MB for 5000-page PDF)
            
        Returns:
            Dict with capacity check results:
            - can_accept: bool
            - reason: str (if rejected)
            - message: str
            - queue_size: int
            - estimated_wait_time_minutes: int (if accepted)
        """
        # Check queue size if rejection is enabled
        if self.config.QUEUE_REJECTION_ENABLED:
            queue_size = self.get_queue_size()
            max_queue_size = self.config.MAX_QUEUE_SIZE
            
            if queue_size >= max_queue_size:
                return {
                    "can_accept": False,
                    "reason": "queue_full",
                    "message": f"Queue is full ({queue_size}/{max_queue_size} jobs). Please try again later.",
                    "queue_size": queue_size,
                    "max_queue_size": max_queue_size,
                    "estimated_wait_time_minutes": self._estimate_wait_time(queue_size)
                }
        
        # Check Redis capacity if service available
        if self.resource_monitor:
            try:
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("Redis capacity check timed out after 5 seconds")
                
                # Set 5 second timeout for Redis check
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(5)
                
                try:
                    estimated_redis_mb = estimated_pdf_size_mb * 0.07  # ~7% of PDF size for chunk results
                    redis_check = self.resource_monitor.check_redis_capacity(int(estimated_redis_mb * 1024 * 1024))
                    
                    if not redis_check.get("has_capacity", True):
                        return {
                            "can_accept": False,
                            "reason": "redis_full",
                            "message": "Redis memory is full. Please try again later.",
                            "redis_info": redis_check
                        }
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
            except TimeoutError:
                logger.warning("Redis capacity check timed out, allowing job (fail open)")
                # Fail open - allow job if Redis check times out
            except Exception as e:
                logger.warning(f"Redis capacity check failed: {str(e)}, allowing job (fail open)")
                # Fail open - allow job if Redis check fails
        
        # Check disk capacity if service available
        if self.resource_monitor:
            estimated_disk_bytes = estimated_pdf_size_mb * 1024 * 1024 * 2  # 2x for temp files
            disk_check = self.resource_monitor.check_disk_capacity(estimated_disk_bytes)
            
            if not disk_check.get("has_capacity", True):
                return {
                    "can_accept": False,
                    "reason": "disk_full",
                    "message": "Disk space is insufficient. Please try again later.",
                    "disk_info": disk_check
                }
        
        # All checks passed
        queue_size = self.get_queue_size()
        return {
            "can_accept": True,
            "queue_size": queue_size,
            "estimated_wait_time_minutes": self._estimate_wait_time(queue_size)
        }
    
    def _estimate_wait_time(self, queue_size: int) -> int:
        """
        Estimate wait time in minutes based on queue size.
        
        Args:
            queue_size: Current queue size
            
        Returns:
            Estimated wait time in minutes
        """
        # Assume 1 hour per 5000-page PDF with current worker concurrency
        # With 5 workers, can process ~5 PDFs per hour
        jobs_per_hour = self.config.CELERY_WORKER_CONCURRENCY
        if jobs_per_hour == 0:
            jobs_per_hour = 5  # Default fallback
        
        wait_hours = queue_size / jobs_per_hour
        return max(0, int(wait_hours * 60))  # Convert to minutes, ensure non-negative
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get comprehensive queue status.
        
        Returns:
            Dict with queue metrics
        """
        queue_size = self.get_queue_size()
        active_jobs = self.get_active_jobs_count()
        
        return {
            "queue_size": queue_size,
            "active_jobs": active_jobs,
            "max_queue_size": self.config.MAX_QUEUE_SIZE,
            "queue_utilization_percent": round((queue_size / self.config.MAX_QUEUE_SIZE) * 100, 2) if self.config.MAX_QUEUE_SIZE > 0 else 0,
            "estimated_wait_time_minutes": self._estimate_wait_time(queue_size),
            "queue_rejection_enabled": self.config.QUEUE_REJECTION_ENABLED,
            "can_accept_jobs": not self.config.QUEUE_REJECTION_ENABLED or queue_size < self.config.MAX_QUEUE_SIZE
        }
