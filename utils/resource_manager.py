"""
Resource Manager - Centralized resource monitoring, cleanup, and optimization

Provides centralized resource management with automatic cleanup scheduling,
memory optimization, and resource limits enforcement for 24GB RAM VPS.
"""

import gc
import logging
import threading
import time
from typing import Dict, Any, Optional
from utils.service_manager import get_service_manager

logger = logging.getLogger(__name__)


class ResourceManager:
    """
    Centralized resource manager for monitoring, cleanup, and optimization.
    
    Optimized for 24GB RAM VPS with proper resource utilization.
    """
    
    _instance = None
    _lock = threading.Lock()
    _cleanup_thread = None
    _stop_cleanup = False
    
    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ResourceManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize resource manager."""
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        with self._lock:
            if hasattr(self, '_initialized') and self._initialized:
                return
            
            self.service_manager = get_service_manager()
            self._last_cleanup = time.time()
            self._cleanup_interval = 300  # 5 minutes
            self._initialized = True
    
    def cleanup_memory(self, force: bool = False) -> Dict[str, Any]:
        """
        Force garbage collection to free memory.
        
        Args:
            force: If True, force immediate cleanup regardless of last cleanup time
        
        Returns:
            Dictionary with cleanup statistics
        """
        current_time = time.time()
        
        # Skip if cleanup was done recently (unless forced)
        if not force and (current_time - self._last_cleanup) < 60:
            return {
                "skipped": True,
                "reason": "Cleanup performed recently",
                "last_cleanup": self._last_cleanup
            }
        
        try:
            # Get memory before cleanup
            import psutil
            process = psutil.Process()
            memory_before = process.memory_info().rss / (1024 * 1024)  # MB
            
            # Force garbage collection
            collected = gc.collect()
            
            # Get memory after cleanup
            memory_after = process.memory_info().rss / (1024 * 1024)  # MB
            memory_freed = memory_before - memory_after
            
            self._last_cleanup = current_time
            
            result = {
                "success": True,
                "collected_objects": collected,
                "memory_before_mb": round(memory_before, 2),
                "memory_after_mb": round(memory_after, 2),
                "memory_freed_mb": round(memory_freed, 2),
                "timestamp": current_time
            }
            
            logger.debug(f"Memory cleanup: freed {memory_freed:.2f}MB, collected {collected} objects")
            return result
            
        except Exception as e:
            logger.warning(f"Memory cleanup failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": current_time
            }
    
    def cleanup_ocr_service_memory(self) -> Dict[str, Any]:
        """
        Cleanup OCR service memory.
        
        Returns:
            Dictionary with cleanup result
        """
        try:
            ocr_service = self.service_manager.get_ocr_service()
            if ocr_service:
                ocr_service.cleanup_memory()
                return {"success": True, "service": "OCR"}
            return {"success": False, "error": "OCR service not available"}
        except Exception as e:
            logger.warning(f"OCR service cleanup failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """
        Get current memory usage information.
        
        Returns:
            Dictionary with memory statistics
        """
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            # Get system memory
            system_memory = psutil.virtual_memory()
            
            return {
                "process": {
                    "rss_mb": round(memory_info.rss / (1024 * 1024), 2),
                    "vms_mb": round(memory_info.vms / (1024 * 1024), 2),
                    "percent": round(process.memory_percent(), 2)
                },
                "system": {
                    "total_gb": round(system_memory.total / (1024 ** 3), 2),
                    "available_gb": round(system_memory.available / (1024 ** 3), 2),
                    "used_gb": round(system_memory.used / (1024 ** 3), 2),
                    "percent": round(system_memory.percent, 2)
                },
                "optimized_for": "24GB RAM VPS"
            }
        except Exception as e:
            logger.warning(f"Failed to get memory usage: {str(e)}")
            return {
                "error": str(e),
                "optimized_for": "24GB RAM VPS"
            }
    
    def get_resource_status(self) -> Dict[str, Any]:
        """
        Get comprehensive resource status including memory, disk, and Redis.
        
        Returns:
            Dictionary with resource status
        """
        try:
            resource_monitor = self.service_manager.get_resource_monitor()
            memory_usage = self.get_memory_usage()
            system_status = resource_monitor.get_system_status() if resource_monitor else {}
            
            return {
                "memory": memory_usage,
                "system": system_status,
                "last_cleanup": self._last_cleanup,
                "optimized_for": "24GB RAM VPS"
            }
        except Exception as e:
            logger.error(f"Failed to get resource status: {str(e)}")
            return {
                "error": str(e),
                "memory": self.get_memory_usage(),
                "optimized_for": "24GB RAM VPS"
            }
    
    def check_memory_threshold(self, threshold_percent: float = 80.0) -> Dict[str, Any]:
        """
        Check if memory usage exceeds threshold.
        
        Args:
            threshold_percent: Memory usage threshold percentage (default: 80%)
        
        Returns:
            Dictionary with threshold check results
        """
        try:
            import psutil
            system_memory = psutil.virtual_memory()
            process = psutil.Process()
            process_percent = process.memory_percent()
            
            system_exceeded = system_memory.percent > threshold_percent
            process_exceeded = process_percent > threshold_percent
            
            return {
                "system_exceeded": system_exceeded,
                "process_exceeded": process_exceeded,
                "system_usage_percent": round(system_memory.percent, 2),
                "process_usage_percent": round(process_percent, 2),
                "threshold_percent": threshold_percent,
                "recommendation": "Perform cleanup" if (system_exceeded or process_exceeded) else "Memory usage normal"
            }
        except Exception as e:
            logger.warning(f"Failed to check memory threshold: {str(e)}")
            return {
                "error": str(e),
                "threshold_percent": threshold_percent
            }
    
    def optimize_for_24gb_ram(self) -> Dict[str, Any]:
        """
        Perform optimizations specific to 24GB RAM VPS.
        
        Returns:
            Dictionary with optimization results
        """
        results = {
            "cleanup_performed": False,
            "memory_freed_mb": 0,
            "recommendations": []
        }
        
        # Check memory threshold
        threshold_check = self.check_memory_threshold(75.0)  # 75% threshold for 24GB
        
        if threshold_check.get("system_exceeded") or threshold_check.get("process_exceeded"):
            # Perform cleanup
            cleanup_result = self.cleanup_memory(force=True)
            if cleanup_result.get("success"):
                results["cleanup_performed"] = True
                results["memory_freed_mb"] = cleanup_result.get("memory_freed_mb", 0)
            
            # Cleanup OCR service
            ocr_cleanup = self.cleanup_ocr_service_memory()
            if ocr_cleanup.get("success"):
                results["ocr_cleanup_performed"] = True
            
            results["recommendations"].append("Memory cleanup performed due to high usage")
        else:
            results["recommendations"].append("Memory usage within acceptable limits")
        
        # Get current status
        memory_usage = self.get_memory_usage()
        results["current_memory_mb"] = memory_usage.get("process", {}).get("rss_mb", 0)
        results["system_memory_percent"] = memory_usage.get("system", {}).get("percent", 0)
        
        return results
    
    def start_automatic_cleanup(self, interval: int = 300):
        """
        Start automatic periodic cleanup thread.
        
        Args:
            interval: Cleanup interval in seconds (default: 5 minutes)
        """
        if self._cleanup_thread is not None and self._cleanup_thread.is_alive():
            logger.info("Automatic cleanup already running")
            return
        
        self._cleanup_interval = interval
        self._stop_cleanup = False
        
        def cleanup_worker():
            """Background cleanup worker thread."""
            while not self._stop_cleanup:
                try:
                    time.sleep(self._cleanup_interval)
                    if not self._stop_cleanup:
                        logger.debug("Performing automatic memory cleanup...")
                        self.optimize_for_24gb_ram()
                except Exception as e:
                    logger.warning(f"Automatic cleanup error: {str(e)}")
        
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        logger.info(f"Automatic cleanup started (interval: {interval}s)")
    
    def stop_automatic_cleanup(self):
        """Stop automatic cleanup thread."""
        if self._cleanup_thread is not None:
            self._stop_cleanup = True
            logger.info("Automatic cleanup stopped")
    
    def cleanup(self):
        """Cleanup resources (called on shutdown)."""
        self.stop_automatic_cleanup()
        self.cleanup_memory(force=True)


# Global singleton instance
_resource_manager: Optional[ResourceManager] = None
_resource_manager_lock = threading.Lock()


def get_resource_manager() -> ResourceManager:
    """
    Get the global ResourceManager singleton instance.
    
    Returns:
        ResourceManager singleton instance
    """
    global _resource_manager
    if _resource_manager is None:
        with _resource_manager_lock:
            if _resource_manager is None:
                _resource_manager = ResourceManager()
    return _resource_manager


# Convenience function for memory cleanup
def cleanup_memory(force: bool = False) -> Dict[str, Any]:
    """Convenience function for memory cleanup."""
    return get_resource_manager().cleanup_memory(force=force)

