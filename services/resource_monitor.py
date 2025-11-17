"""
Resource Monitor - Monitors disk space, Redis memory, and active jobs
"""

import os
import logging
import shutil
from typing import Dict, Any, Optional
from pathlib import Path

from config import get_config
from services.redis_service import RedisService

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """
    Service for monitoring system resources and providing capacity warnings.
    """

    def __init__(self, redis_service: Optional[RedisService] = None):
        self.config = get_config()
        self.redis_service = redis_service

    def get_disk_usage(self, path: str = None) -> Dict[str, Any]:
        """
        Get disk usage information for a path.

        Args:
            path: Path to check (default: temp directory)

        Returns:
            Dictionary with disk usage information
        """
        try:
            if path is None:
                path = self.config.PDF_HYBRID_TEMP_DIR
            
            stat = shutil.disk_usage(path)
            
            return {
                "path": path,
                "total_bytes": stat.total,
                "used_bytes": stat.used,
                "free_bytes": stat.free,
                "total_gb": round(stat.total / (1024 ** 3), 2),
                "used_gb": round(stat.used / (1024 ** 3), 2),
                "free_gb": round(stat.free / (1024 ** 3), 2),
                "usage_percent": round((stat.used / stat.total) * 100, 2) if stat.total > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error getting disk usage: {str(e)}")
            return {
                "path": path,
                "error": str(e)
            }

    def get_redis_memory_usage(self) -> Dict[str, Any]:
        """
        Get Redis memory usage information.

        Returns:
            Dictionary with Redis memory information
        """
        if not self.redis_service or not self.redis_service.is_connected():
            return {
                "connected": False,
                "error": "Redis not connected"
            }

        try:
            info = self.redis_service.redis_client.info('memory')
            
            used_memory = info.get('used_memory', 0)
            used_memory_human = info.get('used_memory_human', '0B')
            maxmemory = info.get('maxmemory', 0)
            maxmemory_human = info.get('maxmemory_human', '0B')
            
            usage_percent = 0
            if maxmemory > 0:
                usage_percent = round((used_memory / maxmemory) * 100, 2)
            
            return {
                "connected": True,
                "used_memory_bytes": used_memory,
                "used_memory_human": used_memory_human,
                "max_memory_bytes": maxmemory,
                "max_memory_human": maxmemory_human,
                "usage_percent": usage_percent,
                "keyspace_keys": info.get('keyspace_keys', 0)
            }
        except Exception as e:
            logger.error(f"Error getting Redis memory usage: {str(e)}")
            return {
                "connected": False,
                "error": str(e)
            }

    def check_disk_capacity(self, required_bytes: int, path: str = None) -> Dict[str, Any]:
        """
        Check if there's enough disk space for an operation.

        Args:
            required_bytes: Bytes required for the operation
            path: Path to check (default: temp directory)

        Returns:
            Dictionary with capacity check results
        """
        disk_usage = self.get_disk_usage(path)
        
        if "error" in disk_usage:
            return {
                "has_capacity": False,
                "error": disk_usage.get("error"),
                "disk_usage": disk_usage
            }
        
        free_bytes = disk_usage.get("free_bytes", 0)
        min_free_bytes = 100 * 1024 * 1024  # 100MB buffer
        total_needed = required_bytes + min_free_bytes
        
        has_capacity = free_bytes >= total_needed
        
        return {
            "has_capacity": has_capacity,
            "required_bytes": required_bytes,
            "required_gb": round(required_bytes / (1024 ** 3), 2),
            "free_bytes": free_bytes,
            "free_gb": disk_usage.get("free_gb", 0),
            "min_free_bytes": min_free_bytes,
            "total_needed_bytes": total_needed,
            "total_needed_gb": round(total_needed / (1024 ** 3), 2),
            "disk_usage": disk_usage
        }

    def check_redis_capacity(self, estimated_bytes: int) -> Dict[str, Any]:
        """
        Check if Redis has enough memory for an operation.

        Args:
            estimated_bytes: Estimated bytes needed in Redis

        Returns:
            Dictionary with Redis capacity check results
        """
        redis_info = self.get_redis_memory_usage()
        
        if not redis_info.get("connected", False):
            return {
                "has_capacity": True,  # Assume capacity if Redis unavailable
                "warning": "Redis not connected - cannot check capacity",
                "redis_info": redis_info
            }
        
        max_memory = redis_info.get("max_memory_bytes", 0)
        used_memory = redis_info.get("used_memory_bytes", 0)
        
        if max_memory == 0:
            # No maxmemory set - assume unlimited
            return {
                "has_capacity": True,
                "warning": "Redis maxmemory not set",
                "redis_info": redis_info
            }
        
        available_memory = max_memory - used_memory
        min_free_bytes = max_memory * 0.1  # 10% buffer
        total_needed = estimated_bytes + min_free_bytes
        
        has_capacity = available_memory >= total_needed
        
        return {
            "has_capacity": has_capacity,
            "estimated_bytes": estimated_bytes,
            "estimated_mb": round(estimated_bytes / (1024 ** 2), 2),
            "available_memory_bytes": available_memory,
            "available_memory_mb": round(available_memory / (1024 ** 2), 2),
            "min_free_bytes": min_free_bytes,
            "total_needed_bytes": total_needed,
            "redis_info": redis_info
        }

    def get_system_status(self) -> Dict[str, Any]:
        """
        Get overall system resource status.

        Returns:
            Dictionary with system status information
        """
        disk_usage = self.get_disk_usage()
        redis_info = self.get_redis_memory_usage()
        
        # Determine overall health
        disk_healthy = True
        if "error" not in disk_usage:
            usage_percent = disk_usage.get("usage_percent", 0)
            disk_healthy = usage_percent < 90  # Warning if >90% used
        
        redis_healthy = True
        if redis_info.get("connected", False):
            usage_percent = redis_info.get("usage_percent", 0)
            redis_healthy = usage_percent < 90  # Warning if >90% used
        
        overall_healthy = disk_healthy and redis_healthy
        
        return {
            "status": "healthy" if overall_healthy else "warning",
            "disk": {
                "healthy": disk_healthy,
                "usage": disk_usage
            },
            "redis": {
                "healthy": redis_healthy,
                "usage": redis_info
            },
            "warnings": self._generate_warnings(disk_usage, redis_info)
        }

    def _generate_warnings(self, disk_usage: Dict[str, Any], redis_info: Dict[str, Any]) -> list:
        """
        Generate capacity warnings based on current usage.

        Args:
            disk_usage: Disk usage information
            redis_info: Redis memory information

        Returns:
            List of warning messages
        """
        warnings = []
        
        # Disk warnings
        if "error" not in disk_usage:
            usage_percent = disk_usage.get("usage_percent", 0)
            if usage_percent > 90:
                warnings.append(f"Disk usage critical: {usage_percent:.1f}% used")
            elif usage_percent > 80:
                warnings.append(f"Disk usage high: {usage_percent:.1f}% used")
            
            free_gb = disk_usage.get("free_gb", 0)
            if free_gb < 10:
                warnings.append(f"Low disk space: {free_gb:.1f}GB free")
        
        # Redis warnings
        if redis_info.get("connected", False):
            usage_percent = redis_info.get("usage_percent", 0)
            if usage_percent > 90:
                warnings.append(f"Redis memory critical: {usage_percent:.1f}% used")
            elif usage_percent > 80:
                warnings.append(f"Redis memory high: {usage_percent:.1f}% used")
        
        return warnings

