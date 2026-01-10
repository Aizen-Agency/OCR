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
        if self._redis_service is None or not self._redis_initialized:
            with self._lock:
                if self._redis_service is None or not self._redis_initialized:
                    try:
                        from services.redis_service import RedisService
                        self._redis_service = RedisService()
                        if self._redis_service.is_connected():
                            logger.info("Redis service initialized via ServiceManager")
                        else:
                            logger.warning("Redis service initialized but not connected")
                        self._redis_initialized = True
                    except Exception as e:
                        logger.warning(f"Failed to initialize Redis service: {str(e)}. Will work without caching.")
                        self._redis_service = None
                        self._redis_initialized = True  # Mark as initialized to avoid retry loops
        
        # Verify connection is still active
        if self._redis_service and not self._redis_service.is_connected():
            logger.warning("Redis connection lost, attempting to reconnect...")
            try:
                self._redis_service._connect()
            except Exception as e:
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
        if self._resource_monitor is None or not self._resource_monitor_initialized:
            with self._lock:
                if self._resource_monitor is None or not self._resource_monitor_initialized:
                    try:
                        from services.resource_monitor import ResourceMonitor
                        redis_service = self.get_redis_service()
                        self._resource_monitor = ResourceMonitor(redis_service=redis_service)
                        self._resource_monitor_initialized = True
                        logger.info("ResourceMonitor initialized via ServiceManager")
                    except Exception as e:
                        logger.warning(f"Failed to initialize ResourceMonitor: {str(e)}")
                        # Create without Redis if Redis unavailable
                        from services.resource_monitor import ResourceMonitor
                        self._resource_monitor = ResourceMonitor(redis_service=None)
                        self._resource_monitor_initialized = True
        return self._resource_monitor
    
    def get_queue_service(self):
        """
        Get or initialize QueueService instance.
        
        Returns:
            QueueService instance
        """
        if self._queue_service is None or not self._queue_service_initialized:
            with self._lock:
                if self._queue_service is None or not self._queue_service_initialized:
                    try:
                        from services.queue_service import QueueService
                        redis_service = self.get_redis_service()
                        resource_monitor = self.get_resource_monitor()
                        self._queue_service = QueueService(
                            redis_service=redis_service,
                            resource_monitor=resource_monitor
                        )
                        self._queue_service_initialized = True
                        logger.info("QueueService initialized via ServiceManager")
                    except Exception as e:
                        logger.warning(f"Failed to initialize QueueService: {str(e)}")
                        # Create without dependencies if unavailable
                        from services.queue_service import QueueService
                        self._queue_service = QueueService(redis_service=None, resource_monitor=None)
                        self._queue_service_initialized = True
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

