"""
Redis Service - Handles caching and rate limiting operations
"""

import logging
import hashlib
import json
from typing import Dict, Any, Optional, Tuple
import redis
from config import get_config
from utils.constants import (
    REDIS_KEY_PREFIX_OCR_RESULT,
    REDIS_KEY_PREFIX_RATE_LIMIT,
    CACHE_KEY_SEPARATOR,
    CACHE_DPI_SUFFIX,
    RATE_LIMIT_WINDOW_SECONDS
)

logger = logging.getLogger(__name__)


class RedisService:
    """
    Service class for Redis operations including caching and rate limiting.
    """

    def __init__(self):
        self.config = get_config()
        self.redis_client: Optional[redis.Redis] = None
        self._connect()

    def _connect(self) -> None:
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.from_url(
                self.config.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"Redis connected successfully: {self.config.REDIS_URL}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            logger.warning("Redis operations will be disabled. OCR will work without caching.")
            self.redis_client = None

    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        if self.redis_client is None:
            return False
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False

    def generate_file_hash(self, file_data: bytes) -> str:
        """
        Generate SHA256 hash for file data.

        Args:
            file_data: Raw file bytes

        Returns:
            SHA256 hash string
        """
        return hashlib.sha256(file_data).hexdigest()

    def _build_cache_key(self, file_hash: str, dpi: Optional[int] = None) -> str:
        """
        Build cache key for OCR result.

        Args:
            file_hash: SHA256 hash of the file
            dpi: Optional DPI for PDF caching

        Returns:
            Cache key string
        """
        key = f"{REDIS_KEY_PREFIX_OCR_RESULT}{file_hash}"
        if dpi is not None:
            key = f"{key}{CACHE_KEY_SEPARATOR}{CACHE_DPI_SUFFIX}{CACHE_KEY_SEPARATOR}{dpi}"
        return key

    def get_cached_result(self, file_hash: str, dpi: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached OCR result by file hash.

        Args:
            file_hash: SHA256 hash of the file
            dpi: Optional DPI for PDF caching

        Returns:
            Cached result dict or None if not found
        """
        if not self.is_connected():
            return None

        try:
            cache_key = self._build_cache_key(file_hash, dpi)
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for file hash: {file_hash[:16]}... (key: {cache_key})")
                return json.loads(cached_data)
            logger.debug(f"Cache miss for file hash: {file_hash[:16]}...")
            return None
        except Exception as e:
            logger.warning(f"Error retrieving cache: {str(e)}")
            return None

    def set_cached_result(self, file_hash: str, result: Dict[str, Any], ttl: Optional[int] = None, dpi: Optional[int] = None) -> bool:
        """
        Cache OCR result by file hash.

        Args:
            file_hash: SHA256 hash of the file
            result: OCR result dictionary
            ttl: Time to live in seconds (defaults to config value)
            dpi: Optional DPI for PDF caching

        Returns:
            True if cached successfully, False otherwise
        """
        if not self.is_connected():
            return False

        try:
            cache_key = self._build_cache_key(file_hash, dpi)
            ttl = ttl or self.config.REDIS_CACHE_TTL
            cached_data = json.dumps(result)
            self.redis_client.setex(cache_key, ttl, cached_data)
            logger.debug(f"Cached result for file hash: {file_hash[:16]}... (key: {cache_key}, TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.warning(f"Error caching result: {str(e)}")
            return False

    def check_rate_limit(self, client_id: str) -> Tuple[bool, int]:
        """
        Check and update rate limit for a client.

        Args:
            client_id: Unique client identifier (IP address or API key)

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        if not self.is_connected():
            # If Redis is not available, allow all requests
            return True, self.config.RATE_LIMIT_PER_MINUTE

        try:
            rate_limit_key = f"{REDIS_KEY_PREFIX_RATE_LIMIT}{client_id}"
            current_count = self.redis_client.incr(rate_limit_key)
            
            # Set expiration on first request
            if current_count == 1:
                self.redis_client.expire(rate_limit_key, RATE_LIMIT_WINDOW_SECONDS)

            remaining = max(0, self.config.RATE_LIMIT_PER_MINUTE - current_count)
            is_allowed = current_count <= self.config.RATE_LIMIT_PER_MINUTE

            if not is_allowed:
                logger.warning(f"Rate limit exceeded for client: {client_id}")

            return is_allowed, remaining
        except Exception as e:
            logger.warning(f"Error checking rate limit: {str(e)}")
            # On error, allow the request
            return True, self.config.RATE_LIMIT_PER_MINUTE

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        if not self.is_connected():
            return {
                "connected": False,
                "cache_keys": 0,
                "memory_usage": 0
            }

        try:
            # Count OCR cache keys
            cache_keys = len(self.redis_client.keys(f"{REDIS_KEY_PREFIX_OCR_RESULT}*"))
            
            # Get Redis info
            info = self.redis_client.info('memory')
            memory_usage = info.get('used_memory_human', '0B')

            return {
                "connected": True,
                "cache_keys": cache_keys,
                "memory_usage": memory_usage,
                "ttl_seconds": self.config.REDIS_CACHE_TTL
            }
        except Exception as e:
            logger.warning(f"Error getting cache stats: {str(e)}")
            return {
                "connected": False,
                "error": str(e)
            }
