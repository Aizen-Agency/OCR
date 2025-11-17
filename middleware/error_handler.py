"""
Error Handler Middleware - Centralized error handling for the Flask application
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from flask import Flask, jsonify, current_app, request
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


def register_error_handlers(app: Flask) -> None:
    """
    Register all error handlers with the Flask application.

    Args:
        app: Flask application instance
    """

    @app.errorhandler(400)
    def bad_request_error(error: HTTPException) -> tuple[Dict[str, Any], int]:
        """Handle 400 Bad Request errors."""
        return _handle_error(error, 400, "Bad Request")

    @app.errorhandler(401)
    def unauthorized_error(error: HTTPException) -> tuple[Dict[str, Any], int]:
        """Handle 401 Unauthorized errors."""
        return _handle_error(error, 401, "Unauthorized")

    @app.errorhandler(403)
    def forbidden_error(error: HTTPException) -> tuple[Dict[str, Any], int]:
        """Handle 403 Forbidden errors."""
        return _handle_error(error, 403, "Forbidden")

    @app.errorhandler(404)
    def not_found_error(error: HTTPException) -> tuple[Dict[str, Any], int]:
        """Handle 404 Not Found errors."""
        return _handle_error(error, 404, "Not Found")

    @app.errorhandler(405)
    def method_not_allowed_error(error: HTTPException) -> tuple[Dict[str, Any], int]:
        """Handle 405 Method Not Allowed errors."""
        return _handle_error(error, 405, "Method Not Allowed")

    @app.errorhandler(413)
    def request_entity_too_large_error(error: HTTPException) -> tuple[Dict[str, Any], int]:
        """Handle 413 Request Entity Too Large errors."""
        max_size = current_app.config.get('MAX_CONTENT_LENGTH', 50 * 1024 * 1024)
        return {
            "error": "File too large",
            "message": f"File size exceeds maximum limit of {max_size // (1024*1024)}MB",
            "max_size_bytes": max_size,
            "timestamp": _get_current_timestamp()
        }, 413

    @app.errorhandler(422)
    def unprocessable_entity_error(error: HTTPException) -> tuple[Dict[str, Any], int]:
        """Handle 422 Unprocessable Entity errors."""
        return _handle_error(error, 422, "Unprocessable Entity")

    @app.errorhandler(429)
    def too_many_requests_error(error: HTTPException) -> tuple[Dict[str, Any], int]:
        """Handle 429 Too Many Requests errors."""
        return _handle_error(error, 429, "Too Many Requests")

    @app.errorhandler(500)
    def internal_server_error(error: Exception) -> tuple[Dict[str, Any], int]:
        """Handle 500 Internal Server Error."""
        logger.error(f"Internal server error: {str(error)}", exc_info=True)
        return {
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
            "timestamp": _get_current_timestamp(),
            "request_id": _get_request_id()
        }, 500

    @app.errorhandler(503)
    def service_unavailable_error(error: HTTPException) -> tuple[Dict[str, Any], int]:
        """Handle 503 Service Unavailable errors."""
        return _handle_error(error, 503, "Service Unavailable")

    @app.errorhandler(Exception)
    def generic_error(error: Exception) -> tuple[Dict[str, Any], int]:
        """Handle any unhandled exceptions."""
        logger.error(f"Unhandled exception: {str(error)}", exc_info=True)
        return {
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
            "timestamp": _get_current_timestamp(),
            "request_id": _get_request_id()
        }, 500


def _is_attack_pattern(request_path: str, user_agent: Optional[str] = None) -> bool:
    """
    Detect common attack patterns to reduce log noise.
    
    Args:
        request_path: The request path
        user_agent: The user agent string
        
    Returns:
        bool: True if this looks like an attack/scanner pattern
    """
    if not request_path:
        return False
    
    # Common scanner/bot patterns
    attack_patterns = [
        '/.env', '/.git', '/wp-admin', '/wp-login', '/phpmyadmin',
        '/admin', '/administrator', '/.well-known', '/.htaccess',
        '/api/v1', '/api/v2', '/swagger', '/graphql',
        '/.git/config', '/.svn', '/backup', '/test',
        '/shell', '/cmd', '/exec', '/eval'
    ]
    
    # Check if path matches attack patterns
    path_lower = request_path.lower()
    for pattern in attack_patterns:
        if pattern in path_lower:
            return True
    
    # Check for suspicious user agents (scanners, bots)
    if user_agent:
        ua_lower = user_agent.lower()
        bot_patterns = [
            'scanner', 'bot', 'crawler', 'spider', 'nmap', 'masscan',
            'sqlmap', 'nikto', 'dirb', 'gobuster', 'wfuzz', 'burp',
            'nessus', 'openvas', 'acunetix', 'netsparker'
        ]
        for pattern in bot_patterns:
            if pattern in ua_lower:
                return True
    
    return False


def _handle_error(error: HTTPException, status_code: int, default_message: str) -> tuple[Dict[str, Any], int]:
    """
    Generic error handler for HTTP exceptions with intelligent logging.

    Args:
        error: The HTTP exception
        status_code: HTTP status code
        default_message: Default error message

    Returns:
        tuple: (error_response_dict, status_code)
    """
    # Get request information for attack pattern detection
    request_path = request.path if request else None
    user_agent = request.headers.get('User-Agent') if request else None
    is_attack = _is_attack_pattern(request_path or '', user_agent)
    
    # Log the error with appropriate level based on attack pattern
    if status_code >= 500:
        logger.error(f"HTTP {status_code} error: {str(error)}", exc_info=True)
    elif status_code >= 400:
        # Reduce log noise for attack patterns - only log at debug level
        if is_attack:
            logger.debug(f"HTTP {status_code} error (attack pattern): {request_path} - {str(error)[:100]}")
        else:
            # Only log 404s for legitimate API routes
            if status_code == 404:
                # Check if it's a legitimate API route attempt
                api_routes = ['/ocr', '/health', '/api']
                is_api_route = any(request_path.startswith(route) for route in api_routes) if request_path else False
                if is_api_route:
                    logger.warning(f"HTTP {status_code} error: {request_path} - {str(error)}")
                else:
                    logger.debug(f"HTTP {status_code} error (non-API route): {request_path}")
            else:
                logger.warning(f"HTTP {status_code} error: {str(error)}")

    # Create error response
    response = {
        "error": getattr(error, 'name', default_message),
        "message": str(error),
        "timestamp": _get_current_timestamp(),
        "status_code": status_code
    }

    # Add request ID if available
    request_id = _get_request_id()
    if request_id:
        response["request_id"] = request_id

    # Add additional context for certain errors
    if hasattr(error, 'description') and error.description:
        response["description"] = error.description

    return response, status_code


def _get_current_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


def _get_request_id() -> Optional[str]:
    """Get request ID from headers or generate one."""
    # Check for X-Request-ID header
    request_id = request.headers.get('X-Request-ID')
    if request_id:
        return request_id

    # Could generate a unique request ID here if needed
    # For now, return None
    return None
