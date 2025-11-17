"""
Authentication Middleware - API Key validation using X-Auth-Token header
"""

import logging
from flask import Flask, request, jsonify, current_app
from utils.request_utils import get_client_ip

logger = logging.getLogger(__name__)


def register_auth_middleware(app: Flask) -> None:
    """
    Register API key authentication middleware with Flask app.
    
    Only applies to /ocr/* endpoints. Health endpoints are excluded.
    
    Args:
        app: Flask application instance
    """
    @app.before_request
    def check_auth():
        """Check API key authentication for protected endpoints."""
        # Skip health endpoints (needed for monitoring/load balancers)
        if request.path.startswith('/health'):
            return None
        
        # Only require authentication for /ocr/* endpoints
        if request.path.startswith('/ocr'):
            auth_token = app.config.get('AUTH_TOKEN', '')
            
            # If AUTH_TOKEN is not configured, allow requests (for development)
            if not auth_token:
                logger.warning("AUTH_TOKEN not configured - authentication disabled")
                return None
            
            # Get token from X-Auth-Token header
            provided_token = request.headers.get('X-Auth-Token')
            
            if not provided_token:
                # Log authentication failure for Fail2ban monitoring
                client_ip = get_client_ip()
                logger.warning(f"Authentication failed: Missing X-Auth-Token header from {client_ip} - {request.path}")
                return jsonify({
                    "error": "Unauthorized",
                    "message": "Missing X-Auth-Token header. Please provide a valid API key."
                }), 401
            
            # Validate token
            if provided_token != auth_token:
                # Log authentication failure for Fail2ban monitoring
                client_ip = get_client_ip()
                logger.warning(f"Authentication failed: Invalid X-Auth-Token from {client_ip} - {request.path}")
                return jsonify({
                    "error": "Unauthorized",
                    "message": "Invalid X-Auth-Token. Please provide a valid API key."
                }), 401
        
        return None
    
    logger.info("API key authentication middleware registered (X-Auth-Token required for /ocr/* endpoints)")

