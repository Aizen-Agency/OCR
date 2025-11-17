"""
Request Utilities - Common request processing helpers
"""

from flask import request
from typing import Optional


def get_client_ip() -> str:
    """
    Extract client IP address from request, handling proxy headers.
    
    Checks X-Forwarded-For and X-Real-IP headers, falling back to remote_addr.
    This is a centralized utility to ensure consistent IP extraction across the codebase.
    
    Returns:
        Client IP address string
    """
    # Check X-Forwarded-For header (may contain multiple IPs, take first)
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
        return ip
    
    # Check X-Real-IP header
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    
    # Fall back to direct connection IP
    return request.remote_addr or 'unknown'

