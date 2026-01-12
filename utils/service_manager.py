"""
Service Manager - Centralized service instance management

Provides singleton pattern for managing service instances across the application.
Ensures all services use shared instances and proper initialization, eliminating
duplicate service creation and improving resource utilization.
"""

import logging
import threading
from typing import Optional
from config import get_config

logger = logging.getLogger(__name__)


class ServiceManager:
    """
    Singleton service manager for centralized service instance management.
    
    Provides thread-safe access to service instances with lazy initialization.
    All services are initialized once and reused across the application.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    # Service instances
    _ocr_service = None
    _redis_service = None
    _job_service = None
    _resource_monitor = None
    _queue_service = None
    
    # Initialization flags
    _ocr_initialized = False
    _redis_initialized = False
    _job_initialized = False
    _resource_monitor_initialized = False
    _queue_service_initialized = False
    
    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ServiceManager, cls).__new__(cls)
        return cls._instance
    
    def get_ocr_service(self):
        """
        Get or initialize OCR service instance.
        
        Returns:
            OCRService instance
        """
        if self._ocr_service is None or not self._ocr_initialized:
            with self._lock:
                if self._ocr_service is None or not self._ocr_initialized:
                    try:
                        from services.ocr_service.ocr_service import OCRService
                        self._ocr_service = OCRService()
                        config = get_config()
                        self._ocr_service.initialize_ocr(lang=config.OCR_LANG)
                        self._ocr_initialized = True
                        logger.info("OCR service initialized via ServiceManager")
                    except Exception as e:
                        logger.error(f"Failed to initialize OCR service: {str(e)}")
                        raise
        return self._ocr_service
    
    def get_redis_service(self):
        """
        Get or initialize Redis service instance.
        
        Uses centralized Redis connection manager for consistent connection handling.
        
        Returns:
            RedisService instance (may be None if connection fails)
        """
        import sys
        print("ServiceManager.get_redis_service: Starting", file=sys.stderr, flush=True)
        if self._redis_service is None or not self._redis_initialized:
            print("ServiceManager.get_redis_service: Redis service not initialized, creating", file=sys.stderr, flush=True)
            with self._lock:
                if self._redis_service is None or not self._redis_initialized:
                    try:
                        print("ServiceManager.get_redis_service: Importing RedisService", file=sys.stderr, flush=True)
                        from services.redis_service import RedisService
                        print("ServiceManager.get_redis_service: Creating RedisService instance (THIS MAY HANG ON REDIS CONNECTION)", file=sys.stderr, flush=True)
                        self._redis_service = RedisService()
                        print("ServiceManager.get_redis_service: RedisService created, checking connection", file=sys.stderr, flush=True)
                        if self._redis_service.is_connected():
                            print("ServiceManager.get_redis_service: Redis is connected", file=sys.stderr, flush=True)
                            logger.info("Redis service initialized via ServiceManager")
                        else:
                            print("ServiceManager.get_redis_service: Redis is NOT connected", file=sys.stderr, flush=True)
                            logger.warning("Redis service initialized but not connected")
                        self._redis_initialized = True
                    except Exception as e:
                        print(f"ServiceManager.get_redis_service: Failed to initialize: {str(e)}", file=sys.stderr, flush=True)
                        logger.warning(f"Failed to initialize Redis service: {str(e)}. Will work without caching.")
                        self._redis_service = None
                        self._redis_initialized = True  # Mark as initialized to avoid retry loops
        else:
            print("ServiceManager.get_redis_service: Returning existing redis service", file=sys.stderr, flush=True)
        
        # Verify connection is still active
        if self._redis_service and not self._redis_service.is_connected():
            print("ServiceManager.get_redis_service: Redis connection lost, attempting to reconnect (THIS MAY HANG)", file=sys.stderr, flush=True)
            logger.warning("Redis connection lost, attempting to reconnect...")
            try:
                self._redis_service._connect()
                print("ServiceManager.get_redis_service: Redis reconnected", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"ServiceManager.get_redis_service: Redis reconnection failed: {str(e)}", file=sys.stderr, flush=True)
                logger.warning(f"Redis reconnection failed: {str(e)}")
        
        return self._redis_service
    
    def get_job_service(self):
        """
        Get or initialize Job service instance.
        
        Returns:
            JobService instance
        """
        if self._job_service is None or not self._job_initialized:
            with self._lock:
                if self._job_service is None or not self._job_initialized:
                    try:
                        from services.job_service import JobService
                        self._job_service = JobService()
                        self._job_initialized = True
                        logger.info("Job service initialized via ServiceManager")
                    except Exception as e:
                        logger.error(f"Failed to initialize Job service: {str(e)}")
                        raise
        return self._job_service
    
    def get_resource_monitor(self):
        """
        Get or initialize ResourceMonitor instance.
        
        Returns:
            ResourceMonitor instance
        """
        import sys
        print("ServiceManager.get_resource_monitor: Starting", file=sys.stderr, flush=True)
        if self._resource_monitor is None or not self._resource_monitor_initialized:
            print("ServiceManager.get_resource_monitor: ResourceMonitor not initialized, creating", file=sys.stderr, flush=True)
            print("ServiceManager.get_resource_monitor: Acquiring lock...", file=sys.stderr, flush=True)
            with self._lock:
                print("ServiceManager.get_resource_monitor: Lock acquired", file=sys.stderr, flush=True)
                if self._resource_monitor is None or not self._resource_monitor_initialized:
                    try:
                        print("ServiceManager.get_resource_monitor: Importing ResourceMonitor", file=sys.stderr, flush=True)
                        from services.resource_monitor import ResourceMonitor
                        print("ServiceManager.get_resource_monitor: ResourceMonitor imported", file=sys.stderr, flush=True)
                        print("ServiceManager.get_resource_monitor: Getting redis_service (using existing instance to avoid deadlock)", file=sys.stderr, flush=True)
                        # Use existing redis_service if available to avoid deadlock (we already hold the lock)
                        # Don't call get_redis_service() which would try to acquire the lock again
                        redis_service = self._redis_service if self._redis_initialized else None
                        if redis_service is None:
                            print("ServiceManager.get_resource_monitor: No existing redis_service, creating without lock", file=sys.stderr, flush=True)
                            # Release lock temporarily to get redis service
                            # Actually, just create ResourceMonitor without Redis to avoid deadlock
                            redis_service = None
                        print("ServiceManager.get_resource_monitor: redis_service obtained", file=sys.stderr, flush=True)
                        print("ServiceManager.get_resource_monitor: Creating ResourceMonitor instance", file=sys.stderr, flush=True)
                        self._resource_monitor = ResourceMonitor(redis_service=redis_service)
                        print("ServiceManager.get_resource_monitor: ResourceMonitor instance created", file=sys.stderr, flush=True)
                        self._resource_monitor_initialized = True
                        print("ServiceManager.get_resource_monitor: ResourceMonitor initialized", file=sys.stderr, flush=True)
                        logger.info("ResourceMonitor initialized via ServiceManager")
                    except Exception as e:
                        print(f"ServiceManager.get_resource_monitor: Failed to initialize: {str(e)}", file=sys.stderr, flush=True)
                        import traceback
                        print(traceback.format_exc(), file=sys.stderr, flush=True)
                        logger.warning(f"Failed to initialize ResourceMonitor: {str(e)}")
                        # Create without Redis if Redis unavailable
                        from services.resource_monitor import ResourceMonitor
                        self._resource_monitor = ResourceMonitor(redis_service=None)
                        self._resource_monitor_initialized = True
                else:
                    print("ServiceManager.get_resource_monitor: ResourceMonitor already initialized (double-check)", file=sys.stderr, flush=True)
        else:
            print("ServiceManager.get_resource_monitor: Returning existing resource monitor", file=sys.stderr, flush=True)
        return self._resource_monitor
    
    def get_queue_service(self):
        """
        Get or initialize QueueService instance.
        
        Returns:
            QueueService instance
        """
        import sys
        print("ServiceManager.get_queue_service: Starting", file=sys.stderr, flush=True)
        if self._queue_service is None or not self._queue_service_initialized:
            print("ServiceManager.get_queue_service: Queue service not initialized, creating", file=sys.stderr, flush=True)
            with self._lock:
                if self._queue_service is None or not self._queue_service_initialized:
                    try:
                        print("ServiceManager.get_queue_service: Importing QueueService", file=sys.stderr, flush=True)
                        from services.queue_service import QueueService
                        print("ServiceManager.get_queue_service: Getting redis_service (using existing to avoid deadlock)", file=sys.stderr, flush=True)
                        # Use existing redis_service if available to avoid deadlock (we already hold the lock)
                        redis_service = self._redis_service if self._redis_initialized else None
                        if redis_service is None:
                            print("ServiceManager.get_queue_service: No existing redis_service, will create QueueService without Redis", file=sys.stderr, flush=True)
                        print("ServiceManager.get_queue_service: redis_service obtained", file=sys.stderr, flush=True)
                        print("ServiceManager.get_queue_service: Getting resource_monitor (using existing to avoid deadlock)", file=sys.stderr, flush=True)
                        # Use existing resource_monitor if available to avoid deadlock
                        resource_monitor = self._resource_monitor if self._resource_monitor_initialized else None
                        if resource_monitor is None:
                            print("ServiceManager.get_queue_service: No existing resource_monitor, creating without lock", file=sys.stderr, flush=True)
                            # Create ResourceMonitor without Redis to avoid deadlock
                            from services.resource_monitor import ResourceMonitor
                            resource_monitor = ResourceMonitor(redis_service=redis_service)
                        print("ServiceManager.get_queue_service: resource_monitor obtained", file=sys.stderr, flush=True)
                        print("ServiceManager.get_queue_service: Creating QueueService instance", file=sys.stderr, flush=True)
                        self._queue_service = QueueService(
                            redis_service=redis_service,
                            resource_monitor=resource_monitor
                        )
                        self._queue_service_initialized = True
                        print("ServiceManager.get_queue_service: QueueService initialized", file=sys.stderr, flush=True)
                        logger.info("QueueService initialized via ServiceManager")
                    except Exception as e:
                        print(f"ServiceManager.get_queue_service: Failed to initialize: {str(e)}", file=sys.stderr, flush=True)
                        logger.warning(f"Failed to initialize QueueService: {str(e)}")
                        # Create without dependencies if unavailable
                        from services.queue_service import QueueService
                        self._queue_service = QueueService(redis_service=None, resource_monitor=None)
                        self._queue_service_initialized = True
        else:
            print("ServiceManager.get_queue_service: Returning existing queue service", file=sys.stderr, flush=True)
        return self._queue_service
    
    def reset_ocr_service(self):
        """
        Reset OCR service (useful for testing or reinitialization).
        
        Forces reinitialization on next get_ocr_service() call.
        """
        with self._lock:
            self._ocr_service = None
            self._ocr_initialized = False
            logger.info("OCR service reset")
    
    def reset_redis_service(self):
        """
        Reset Redis service (useful for reconnection).
        
        Forces reinitialization on next get_redis_service() call.
        """
        with self._lock:
            self._redis_service = None
            self._redis_initialized = False
            logger.info("Redis service reset")
    
    def cleanup(self):
        """
        Cleanup all services (called on application shutdown).
        """
        with self._lock:
            if self._redis_service:
                try:
                    self._redis_service.close()
                except Exception as e:
                    logger.warning(f"Error closing Redis service: {str(e)}")
            
            # Clear references
            self._ocr_service = None
            self._redis_service = None
            self._job_service = None
            self._resource_monitor = None
            self._queue_service = None
            
            # Reset flags
            self._ocr_initialized = False
            self._redis_initialized = False
            self._job_initialized = False
            self._resource_monitor_initialized = False
            self._queue_service_initialized = False
            
            logger.info("ServiceManager cleanup completed")


# Global singleton instance
_service_manager: Optional[ServiceManager] = None
_service_manager_lock = threading.Lock()


def get_service_manager() -> ServiceManager:
    """
    Get the global ServiceManager singleton instance.
    
    Returns:
        ServiceManager singleton instance
    """
    global _service_manager
    if _service_manager is None:
        with _service_manager_lock:
            if _service_manager is None:
                _service_manager = ServiceManager()
    return _service_manager


# Convenience functions for direct service access
def get_ocr_service():
    """Get OCR service instance via ServiceManager."""
    return get_service_manager().get_ocr_service()


def get_redis_service():
    """Get Redis service instance via ServiceManager."""
    return get_service_manager().get_redis_service()


def get_job_service():
    """Get Job service instance via ServiceManager."""
    return get_service_manager().get_job_service()


def get_resource_monitor():
    """Get ResourceMonitor instance via ServiceManager."""
    return get_service_manager().get_resource_monitor()


def get_queue_service():
    """Get QueueService instance via ServiceManager."""
    return get_service_manager().get_queue_service()

