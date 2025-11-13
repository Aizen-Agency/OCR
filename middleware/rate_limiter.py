"""
Rate Limiter Middleware - Redis-based rate limiting
"""

import logging
from typing import Optional, Tuple
from flask import request, jsonify, current_app
from services.redis_service import RedisService

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
        # Handle proxy headers
        if request.headers.get('X-Forwarded-For'):
            ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
        elif request.headers.get('X-Real-IP'):
            ip = request.headers.get('X-Real-IP')
        else:
            ip = request.remote_addr

        return f"ip:{ip}"

    def check_rate_limit(self, request) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if request is within rate limits.

        Args:
            request: Flask request object

        Returns:
            Tuple of (is_allowed, error_response_dict)
            If allowed, error_response_dict is None
        """
        try:
            client_id = self.get_client_identifier(request)
            is_allowed, remaining = self.redis_service.check_rate_limit(client_id)

            if not is_allowed:
                return False, {
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {self.redis_service.config.RATE_LIMIT_PER_MINUTE} per minute",
                    "retry_after": 60,
                    "remaining": 0
                }

            # Add rate limit headers
            request.rate_limit_remaining = remaining
            request.rate_limit_total = self.redis_service.config.RATE_LIMIT_PER_MINUTE

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
        if request.method == 'GET' and request.path.startswith('/ocr/job/'):
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
            response.headers['X-RateLimit-Limit'] = str(rate_limiter.redis_service.config.RATE_LIMIT_PER_MINUTE)
            response.headers['X-RateLimit-Remaining'] = str(getattr(request, 'rate_limit_remaining', 0))
        return response
