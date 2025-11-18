"""
Centralized Redis Connection Manager

Provides a singleton Redis connection manager that all services can use.
Supports both direct connection parameters and URL-based connection for backward compatibility.
"""

import os
import logging
import threading
from typing import Optional
import redis
from redis.exceptions import (
    ConnectionError,
    AuthenticationError,
    ResponseError,
    TimeoutError
)
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


class RedisConnectionManager:
    """
    Singleton Redis connection manager.
    
    Provides a centralized way to manage Redis connections across all services.
    Supports both direct connection parameters and URL-based connection.
    """
    
    _instance = None
    _lock = threading.Lock()
    _client: Optional[redis.Redis] = None
    
    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(RedisConnectionManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the connection manager (only once)."""
        if self._initialized:
            return
        
        with self._lock:
            if self._initialized:
                return
            
            self._host = os.getenv('REDIS_HOST', 'redis')
            self._port = int(os.getenv('REDIS_PORT', '6379'))
            self._username = os.getenv('REDIS_USERNAME', 'default')
            self._password = os.getenv('REDIS_PASSWORD', '')
            self._db = int(os.getenv('REDIS_DB', '0'))
            self._redis_url = os.getenv('REDIS_URL', '')
            
            # Determine connection method
            self._use_direct_connection = bool(
                self._host and self._port and self._password
            )
            
            # Build connection parameters
            if self._use_direct_connection:
                logger.info(f"Using direct Redis connection: {self._host}:{self._port}/{self._db}")
            elif self._redis_url:
                logger.info(f"Using Redis URL connection (fallback mode)")
            else:
                logger.warning("No Redis credentials found - connection will fail")
            
            self._initialized = True
    
    def _build_redis_url(self) -> str:
        """
        Build Redis URL from individual parameters.
        
        Returns:
            Redis connection URL string
        """
        if self._redis_url:
            return self._redis_url
        
        if not self._password:
            # No password - insecure but allows local dev
            return f"redis://{self._host}:{self._port}/{self._db}"
        
        # URL-encode password to handle special characters
        encoded_password = quote_plus(self._password)
        
        # Build URL with username if provided (Redis 6+ ACL support)
        if self._username and self._username != 'default':
            return f"redis://{quote_plus(self._username)}:{encoded_password}@{self._host}:{self._port}/{self._db}"
        else:
            return f"redis://:{encoded_password}@{self._host}:{self._port}/{self._db}"
    
    def _create_client_from_params(self) -> redis.Redis:
        """
        Create Redis client using direct connection parameters.
        
        Returns:
            Redis client instance
        """
        connection_kwargs = {
            'host': self._host,
            'port': self._port,
            'db': self._db,
            'decode_responses': True,
            'socket_connect_timeout': 5,
            'socket_timeout': 5,
            'retry_on_timeout': True,
            'health_check_interval': 30,
            'socket_keepalive': True,
            'socket_keepalive_options': {},
            'max_connections': 50,
            'retry_on_error': [ConnectionError, TimeoutError]
        }
        
        # Add authentication if password is provided
        if self._password:
            if self._username and self._username != 'default':
                connection_kwargs['username'] = self._username
            connection_kwargs['password'] = self._password
        
        return redis.Redis(**connection_kwargs)
    
    def _create_client_from_url(self) -> redis.Redis:
        """
        Create Redis client using URL connection.
        
        Returns:
            Redis client instance
        """
        redis_url = self._build_redis_url()
        
        return redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
            socket_keepalive=True,
            socket_keepalive_options={},
            max_connections=50,
            retry_on_error=[ConnectionError, TimeoutError]
        )
    
    def get_client(self, force_reconnect: bool = False) -> Optional[redis.Redis]:
        """
        Get or create Redis client instance.
        
        Args:
            force_reconnect: If True, force reconnection even if client exists
            
        Returns:
            Redis client instance or None if connection fails
        """
        # Return existing client if available and not forcing reconnect
        if self._client is not None and not force_reconnect:
            try:
                # Quick health check
                self._client.ping()
                return self._client
            except Exception:
                # Connection lost, will reconnect below
                logger.warning("Redis connection lost, reconnecting...")
                self._client = None
        
        # Create new connection
        with self._lock:
            # Double-check after acquiring lock
            if self._client is not None and not force_reconnect:
                try:
                    self._client.ping()
                    return self._client
                except Exception:
                    self._client = None
            
            try:
                if self._use_direct_connection:
                    self._client = self._create_client_from_params()
                else:
                    self._client = self._create_client_from_url()
                
                # Test connection
                self._client.ping()
                
                # Mask password in logs
                safe_info = f"{self._host}:{self._port}/{self._db}"
                logger.info(f"Redis connected successfully: {safe_info}")
                
                return self._client
                
            except AuthenticationError as e:
                logger.error(f"Redis authentication error: {str(e)}")
                logger.error("Check REDIS_PASSWORD or REDIS_URL environment variable is set correctly.")
                self._client = None
                return None
                
            except ConnectionError as e:
                logger.error(f"Redis connection error: {str(e)}")
                logger.error(f"  Attempted connection to: {self._host}:{self._port}")
                self._client = None
                return None
                
            except Exception as e:
                logger.error(f"Failed to create Redis connection: {str(e)}")
                logger.error(f"  Error type: {type(e).__name__}")
                self._client = None
                return None
    
    def get_connection_url(self) -> str:
        """
        Get the Redis connection URL (for Celery configuration).
        
        Returns:
            Redis connection URL string
        """
        return self._build_redis_url()
    
    def is_connected(self) -> bool:
        """
        Check if Redis is currently connected.
        
        Returns:
            True if connected, False otherwise
        """
        if self._client is None:
            return False
        
        try:
            self._client.ping()
            return True
        except Exception:
            return False
    
    def reconnect(self) -> bool:
        """
        Force reconnection to Redis.
        
        Returns:
            True if reconnection successful, False otherwise
        """
        logger.info("Forcing Redis reconnection...")
        client = self.get_client(force_reconnect=True)
        return client is not None
    
    def close(self) -> None:
        """Close Redis connection and cleanup resources."""
        if self._client is not None:
            try:
                self._client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {str(e)}")
            finally:
                self._client = None


# Global singleton instance
_redis_manager: Optional[RedisConnectionManager] = None


def get_redis_manager() -> RedisConnectionManager:
    """
    Get the global Redis connection manager instance.
    
    Returns:
        RedisConnectionManager singleton instance
    """
    global _redis_manager
    if _redis_manager is None:
        _redis_manager = RedisConnectionManager()
    return _redis_manager

