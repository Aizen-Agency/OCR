"""
Redis Service - Handles caching and rate limiting operations
"""

import logging
import json
import time
from typing import Dict, Any, Optional, Tuple
import redis
from config import get_config
from utils.constants import (
    REDIS_KEY_PREFIX_OCR_RESULT,
    REDIS_KEY_PREFIX_RATE_LIMIT,
    REDIS_KEY_PREFIX_PDF_HYBRID_CHUNK,
    REDIS_KEY_PREFIX_PDF_HYBRID_CHUNKS,
    REDIS_KEY_PREFIX_PDF_HYBRID_PROGRESS,
    CACHE_KEY_SEPARATOR,
    CACHE_DPI_SUFFIX,
    RATE_LIMIT_WINDOW_SECONDS
)
from utils.redis_connection import get_redis_manager

logger = logging.getLogger(__name__)


class RedisService:
    """
    Service class for Redis operations including caching and rate limiting.
    Uses centralized Redis connection manager for consistent connection handling.
    """

    def __init__(self):
        self.config = get_config()
        self.redis_manager = get_redis_manager()
        self.redis_client: Optional[redis.Redis] = None
        self._connect()

    def _connect(self, retry_count: int = 0, max_retries: int = 3) -> None:
        """
        Initialize Redis connection using centralized connection manager.
        
        Args:
            retry_count: Current retry attempt number
            max_retries: Maximum number of retry attempts
        """
        if retry_count == 0:
            logger.info("Attempting to connect to Redis using centralized connection manager")
        else:
            logger.info(f"Retrying Redis connection (attempt {retry_count + 1}/{max_retries + 1})")
        
        try:
            # Get client from centralized connection manager
            self.redis_client = self.redis_manager.get_client(force_reconnect=(retry_count > 0))
            
            if self.redis_client is None:
                raise ConnectionError("Failed to get Redis client from connection manager")
            
            # Test connection
            self.redis_client.ping()
            logger.info("Redis connected successfully via centralized connection manager")
            
        except redis.ConnectionError as e:
            if retry_count < max_retries:
                # Exponential backoff: 1s, 2s, 4s
                wait_time = 2 ** retry_count
                logger.warning(f"Redis connection error (retrying in {wait_time}s): {str(e)}")
                time.sleep(wait_time)
                return self._connect(retry_count + 1, max_retries)
            else:
                logger.error(f"Redis connection error after {max_retries + 1} attempts: {str(e)}")
                logger.warning("Redis operations will be disabled. OCR will work without caching.")
                logger.warning("  Check that Redis service is running and accessible.")
                self.redis_client = None
        except redis.AuthenticationError as e:
            logger.error(f"Redis authentication error: {str(e)}")
            logger.error("  Check REDIS_PASSWORD or REDIS_URL environment variable is set correctly.")
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
                logger.error(f"  Error type: {type(e).__name__}")
                logger.warning("Redis operations will be disabled. OCR will work without caching.")
                self.redis_client = None

    def is_connected(self) -> bool:
        """Check if Redis is connected and attempt reconnection if needed."""
        # Use centralized connection manager's connection check
        if self.redis_manager.is_connected():
            # Update local reference
            self.redis_client = self.redis_manager.get_client()
            return True
        
        # Try to reconnect via centralized manager
        if self.redis_manager.reconnect():
            self.redis_client = self.redis_manager.get_client()
            return True
        
        # Fallback to local reconnection attempt
        if self.redis_client is None:
            self._connect()
            if self.redis_client is None:
                return False
        
        try:
            self.redis_client.ping()
            return True
        except Exception:
            # Try centralized manager reconnect
            if self.redis_manager.reconnect():
                self.redis_client = self.redis_manager.get_client()
                return True
            return False

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
        
        Note: The centralized connection manager maintains the connection,
        so we only clear the local reference here. The manager will handle
        connection cleanup when appropriate.
        """
        # Clear local reference only - centralized manager maintains connection
        self.redis_client = None

    def store_chunk_result(self, job_id: str, chunk_id: int, chunk_result: dict) -> bool:
        """
        Store a chunk result for hybrid PDF processing.

        Uses Redis pipeline for atomic operations and better performance.

        Args:
            job_id: Job ID
            chunk_id: Chunk ID (0-indexed)
            chunk_result: Chunk result dictionary

        Returns:
            True if stored successfully, False otherwise
        """
        if not self.is_connected():
            return False

        try:
            # Use pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            
            # Store chunk result
            chunk_key = f"{REDIS_KEY_PREFIX_PDF_HYBRID_CHUNK}{job_id}:{chunk_id}"
            chunk_data = json.dumps(chunk_result)
            pipe.setex(chunk_key, self.config.REDIS_CACHE_TTL, chunk_data)
            
            # Add chunk_id to set for easy retrieval
            chunks_list_key = f"{REDIS_KEY_PREFIX_PDF_HYBRID_CHUNKS}{job_id}"
            pipe.sadd(chunks_list_key, chunk_id)
            pipe.expire(chunks_list_key, self.config.REDIS_CACHE_TTL)
            
            # Execute all operations atomically
            pipe.execute()
            
            logger.debug(f"Stored chunk {chunk_id} result for job {job_id}")
            return True
        except Exception as e:
            logger.warning(f"Error storing chunk result: {str(e)}")
            return False

    def get_chunk_results(self, job_id: str) -> list:
        """
        Retrieve all chunk results for a job.

        Args:
            job_id: Job ID

        Returns:
            List of chunk result dictionaries, sorted by chunk_id
        """
        if not self.is_connected():
            return []

        try:
            # Get all chunk IDs from the set
            chunks_list_key = f"{REDIS_KEY_PREFIX_PDF_HYBRID_CHUNKS}{job_id}"
            chunk_ids = self.redis_client.smembers(chunks_list_key)
            
            if not chunk_ids:
                return []

            # Retrieve each chunk result
            chunks = []
            for chunk_id_str in chunk_ids:
                try:
                    chunk_id = int(chunk_id_str)
                    chunk_key = f"{REDIS_KEY_PREFIX_PDF_HYBRID_CHUNK}{job_id}:{chunk_id}"
                    chunk_data = self.redis_client.get(chunk_key)
                    if chunk_data:
                        chunks.append((chunk_id, json.loads(chunk_data)))
                except (ValueError, json.JSONDecodeError) as e:
                    logger.warning(f"Error retrieving chunk {chunk_id_str}: {str(e)}")
                    continue

            # Sort by chunk_id and return just the results
            chunks.sort(key=lambda x: x[0])
            return [chunk_result for _, chunk_result in chunks]

        except Exception as e:
            logger.warning(f"Error getting chunk results: {str(e)}")
            return []

    def update_progress(self, job_id: str, pages_processed: int, total_pages: int) -> bool:
        """
        Update progress for a hybrid PDF job.

        Args:
            job_id: Job ID
            pages_processed: Number of pages processed so far
            total_pages: Total number of pages

        Returns:
            True if updated successfully, False otherwise
        """
        if not self.is_connected():
            return False

        try:
            progress_key = f"{REDIS_KEY_PREFIX_PDF_HYBRID_PROGRESS}{job_id}"
            progress_data = {
                "pages_processed": pages_processed,
                "total_pages": total_pages,
                "progress_percent": round((pages_processed / total_pages * 100) if total_pages > 0 else 0, 2)
            }
            self.redis_client.setex(
                progress_key,
                self.config.REDIS_CACHE_TTL,
                json.dumps(progress_data)
            )
            return True
        except Exception as e:
            logger.warning(f"Error updating progress: {str(e)}")
            return False

    def get_progress(self, job_id: str) -> dict:
        """
        Get progress information for a hybrid PDF job.

        Args:
            job_id: Job ID

        Returns:
            Dictionary with progress information, or empty dict if not found
        """
        if not self.is_connected():
            return {}

        try:
            progress_key = f"{REDIS_KEY_PREFIX_PDF_HYBRID_PROGRESS}{job_id}"
            progress_data = self.redis_client.get(progress_key)
            if progress_data:
                return json.loads(progress_data)
            return {}
        except Exception as e:
            logger.warning(f"Error getting progress: {str(e)}")
            return {}

    def cleanup_chunk_data(self, job_id: str) -> bool:
        """
        Cleanup chunk data for a completed job.

        Uses Redis pipeline for efficient batch deletion.

        Args:
            job_id: Job ID

        Returns:
            True if cleaned successfully, False otherwise
        """
        if not self.is_connected():
            return False

        try:
            # Get all chunk IDs
            chunks_list_key = f"{REDIS_KEY_PREFIX_PDF_HYBRID_CHUNKS}{job_id}"
            chunk_ids = self.redis_client.smembers(chunks_list_key)
            
            # Use pipeline for batch deletion
            if chunk_ids:
                pipe = self.redis_client.pipeline()
                
                # Delete each chunk result
                for chunk_id_str in chunk_ids:
                    chunk_key = f"{REDIS_KEY_PREFIX_PDF_HYBRID_CHUNK}{job_id}:{chunk_id_str}"
                    pipe.delete(chunk_key)
                
                # Execute all deletions
                pipe.execute()
            
            # Delete the chunks list and progress (use pipeline for these too)
            pipe = self.redis_client.pipeline()
            pipe.delete(chunks_list_key)
            progress_key = f"{REDIS_KEY_PREFIX_PDF_HYBRID_PROGRESS}{job_id}"
            pipe.delete(progress_key)
            pipe.execute()
            
            logger.debug(f"Cleaned up chunk data for job {job_id}")
            return True
        except Exception as e:
            logger.warning(f"Error cleaning up chunk data: {str(e)}")
            return False

    def __del__(self):
        """Cleanup on object destruction."""
        self.close()
