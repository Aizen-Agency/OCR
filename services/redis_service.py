"""
Redis Service - Handles caching and rate limiting operations
"""

import logging
import hashlib
import json
import time
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
from utils.encoding import mask_redis_url

logger = logging.getLogger(__name__)


class RedisService:
    """
    Service class for Redis operations including caching and rate limiting.
    """

    def __init__(self):
        self.config = get_config()
        self.redis_client: Optional[redis.Redis] = None
        self._connect()

    def _connect(self, retry_count: int = 0, max_retries: int = 3) -> None:
        """
        Initialize Redis connection with retry logic and exponential backoff.
        
        Args:
            retry_count: Current retry attempt number
            max_retries: Maximum number of retry attempts
        """
        redis_url = self.config.REDIS_URL
        
        # Mask password in logs for security
        safe_url = mask_redis_url(redis_url)
        
        if retry_count == 0:
            logger.info(f"Attempting to connect to Redis at: {safe_url}")
        else:
            logger.info(f"Retrying Redis connection (attempt {retry_count + 1}/{max_retries + 1}): {safe_url}")
        
        try:
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
                socket_keepalive=True,
                socket_keepalive_options={}
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"Redis connected successfully: {safe_url}")
        except redis.ConnectionError as e:
            if retry_count < max_retries:
                # Exponential backoff: 1s, 2s, 4s
                wait_time = 2 ** retry_count
                logger.warning(f"Redis connection error (retrying in {wait_time}s): {str(e)}")
                time.sleep(wait_time)
                return self._connect(retry_count + 1, max_retries)
            else:
                logger.error(f"Redis connection error after {max_retries + 1} attempts: {str(e)}")
                logger.error(f"  Attempted URL: {safe_url}")
                logger.warning("Redis operations will be disabled. OCR will work without caching.")
                logger.warning("  Check that Redis service is running and accessible at the configured URL.")
                self.redis_client = None
        except redis.AuthenticationError as e:
            logger.error(f"Redis authentication error: {str(e)}")
            logger.error(f"  Attempted URL: {safe_url}")
            logger.error("  Check REDIS_PASSWORD environment variable is set correctly.")
            logger.warning("Redis operations will be disabled. OCR will work without caching.")
            self.redis_client = None
        except redis.ResponseError as e:
            # Handle Redis state changes (master -> replica) gracefully
            error_msg = str(e).lower()
            if 'unblocked' in error_msg or 'instance state changed' in error_msg:
                logger.warning(f"Redis state change detected (will retry): {str(e)}")
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count
                    time.sleep(wait_time)
                    return self._connect(retry_count + 1, max_retries)
                else:
                    logger.error(f"Redis state change persisted after {max_retries + 1} attempts")
                    self.redis_client = None
            else:
                logger.error(f"Redis response error: {str(e)}")
                self.redis_client = None
        except Exception as e:
            if retry_count < max_retries:
                wait_time = 2 ** retry_count
                logger.warning(f"Redis connection failed (retrying in {wait_time}s): {str(e)}")
                time.sleep(wait_time)
                return self._connect(retry_count + 1, max_retries)
            else:
                logger.error(f"Failed to connect to Redis after {max_retries + 1} attempts: {str(e)}")
                logger.error(f"  Attempted URL: {safe_url}")
                logger.error(f"  Error type: {type(e).__name__}")
                logger.warning("Redis operations will be disabled. OCR will work without caching.")
                self.redis_client = None

    def is_connected(self) -> bool:
        """Check if Redis is connected and attempt reconnection if needed."""
        if self.redis_client is None:
            # Try to reconnect once
            self._connect()
            if self.redis_client is None:
                return False
        
        try:
            self.redis_client.ping()
            return True
        except redis.ResponseError as e:
            # Handle Redis state changes
            error_msg = str(e).lower()
            if 'unblocked' in error_msg or 'instance state changed' in error_msg:
                logger.warning("Redis state changed, reconnecting...")
                self._connect()
                try:
                    self.redis_client.ping()
                    return True
                except Exception:
                    return False
            return False
        except Exception:
            # Try to reconnect once on any other error
            try:
                self._connect()
                if self.redis_client:
                    self.redis_client.ping()
                    return True
            except Exception:
                pass
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
            # Count OCR cache keys using SCAN (non-blocking, better performance)
            # SCAN is preferred over KEYS for production as it doesn't block Redis
            cache_keys = 0
            cursor = 0
            pattern = f"{REDIS_KEY_PREFIX_OCR_RESULT}*"
            while True:
                cursor, keys = self.redis_client.scan(cursor, match=pattern, count=100)
                cache_keys += len(keys)
                if cursor == 0:
                    break
            
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

    def close(self) -> None:
        """
        Close Redis connection and cleanup resources.
        
        This should be called when the service is being destroyed
        to properly release connections.
        """
        if self.redis_client is not None:
            try:
                self.redis_client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {str(e)}")
            finally:
                self.redis_client = None

    def __del__(self):
        """Cleanup on object destruction."""
        self.close()
