"""
Rate Limiter Middleware - Redis-based rate limiting
"""

import logging
from typing import Optional, Tuple, Dict, Any
from flask import request, jsonify, current_app
from services.redis_service import RedisService
from utils.request_utils import get_client_ip

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiting middleware using Redis.
    """

    def __init__(self, redis_service: RedisService):
        self.redis_service = redis_service

    def get_client_identifier(self, request) -> str:
        """
        Extract client identifier from request.

        Args:
            request: Flask request object

        Returns:
            Client identifier (IP address or API key)
        """
        # Check for API key in headers
        api_key = request.headers.get('X-API-Key')
        if api_key:
            return f"api_key:{api_key}"

        # Fall back to IP address
        ip = get_client_ip()
        return f"ip:{ip}"

    def _get_dynamic_rate_limit(self, request) -> int:
        """
        Get dynamic rate limit based on request type and file size.
        
        Args:
            request: Flask request object
            
        Returns:
            Rate limit per minute
        """
        config = self.redis_service.config
        
        # Check if this is a PDF upload request
        if request.method == 'POST' and request.path.startswith('/pdf/'):
            # Try to estimate PDF size from Content-Length header
            content_length = request.headers.get('Content-Length')
            if content_length:
                try:
                    file_size_bytes = int(content_length)
                    file_size_mb = file_size_bytes / (1024 * 1024)
                    
                    # Dynamic limits based on PDF size
                    if file_size_mb > 100:  # Large PDF (>100MB, likely 5000 pages)
                        return config.RATE_LIMIT_LARGE_PDF
                    elif file_size_mb > 10:  # Medium PDF (10-100MB)
                        return config.RATE_LIMIT_MEDIUM_PDF
                    else:  # Small PDF (<10MB)
                        return config.RATE_LIMIT_SMALL_PDF
                except (ValueError, TypeError):
                    pass
            
            # Fallback: use PDF hybrid rate limit
            return config.PDF_HYBRID_RATE_LIMIT_PER_MINUTE
        
        # Default rate limit for other requests
        return config.RATE_LIMIT_PER_MINUTE

    def check_rate_limit(self, request) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if request is within rate limits with dynamic limits based on request type.

        Args:
            request: Flask request object

        Returns:
            Tuple of (is_allowed, error_response_dict)
            If allowed, error_response_dict is None
        """
        try:
            client_id = self.get_client_identifier(request)
            
            # Get dynamic rate limit based on request type
            rate_limit = self._get_dynamic_rate_limit(request)
            
            # Check rate limit with dynamic limit
            is_allowed, remaining = self.redis_service.check_rate_limit(client_id, limit_per_minute=rate_limit)

            if not is_allowed:
                return False, {
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {rate_limit} per minute",
                    "retry_after": 60,
                    "remaining": 0
                }

            # Add rate limit headers with dynamic limit
            request.rate_limit_remaining = remaining
            request.rate_limit_total = rate_limit
            request.rate_limit_dynamic = rate_limit != self.redis_service.config.RATE_LIMIT_PER_MINUTE

            return True, None

        except Exception as e:
            logger.warning(f"Rate limit check failed: {str(e)}. Allowing request.")
            # On error, allow the request
            return True, None


def register_rate_limiter(app, redis_service: RedisService) -> None:
    """
    Register rate limiting middleware with Flask app.

    Args:
        app: Flask application instance
        redis_service: RedisService instance
    """
    rate_limiter = RateLimiter(redis_service)

    @app.before_request
    def check_rate_limit():
        """Check rate limit before processing request."""
        # Skip rate limiting for health checks
        if request.endpoint in ('health.health_check', 'health.readiness_check', 'health.liveness_check'):
            return None

        # Skip rate limiting for job status endpoints (read-only)
        if request.method == 'GET' and (
            request.path.startswith('/ocr/job/') or 
            request.path.startswith('/pdf/job/')
        ):
            return None

        # Skip rate limiting for /pdf endpoints (PDF processing is already rate-limited by file size and processing time)
        # This prevents Redis blocking during PDF upload/validation
        if request.path.startswith('/pdf'):
            return None

        is_allowed, error_response = rate_limiter.check_rate_limit(request)

        if not is_allowed:
            response = jsonify(error_response)
            response.status_code = 429
            response.headers['Retry-After'] = str(error_response['retry_after'])
            response.headers['X-RateLimit-Limit'] = str(rate_limiter.redis_service.config.RATE_LIMIT_PER_MINUTE)
            response.headers['X-RateLimit-Remaining'] = '0'
            return response

        return None

    @app.after_request
    def add_rate_limit_headers(response):
        """Add rate limit headers to all responses."""
        if hasattr(request, 'rate_limit_remaining'):
            # Use dynamic limit if set, otherwise use default
            limit = getattr(request, 'rate_limit_total', rate_limiter.redis_service.config.RATE_LIMIT_PER_MINUTE)
            response.headers['X-RateLimit-Limit'] = str(limit)
            response.headers['X-RateLimit-Remaining'] = str(getattr(request, 'rate_limit_remaining', 0))
        return response
