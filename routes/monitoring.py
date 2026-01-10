"""
Monitoring Blueprint - Routes for queue and system monitoring
"""
import logging
from flask import Blueprint, jsonify, request, current_app
from utils.service_manager import get_queue_service, get_resource_monitor

logger = logging.getLogger(__name__)

# Create blueprint
monitoring_bp = Blueprint('monitoring', __name__, url_prefix='/monitoring')


def _check_auth():
    """Check authentication for monitoring endpoints."""
    auth_token = current_app.config.get('AUTH_TOKEN', '')
    if not auth_token:
        return None  # No auth required if not configured
    
    provided_token = request.headers.get('X-Auth-Token')
    if not provided_token or provided_token != auth_token:
        return jsonify({
            "error": "Unauthorized",
            "message": "Missing or invalid X-Auth-Token header"
        }), 401
    return None


@monitoring_bp.route('/queue', methods=['GET'])
def get_queue_status():
    """
    Get queue status and metrics.
    
    Returns: JSON with queue information
    """
    # Check authentication
    auth_error = _check_auth()
    if auth_error:
        return auth_error
    
    try:
        queue_service = get_queue_service()
        queue_status = queue_service.get_queue_status()
        
        return jsonify({
            "status": "success",
            "data": queue_status
        }), 200
    except Exception as e:
        logger.error(f"Error getting queue status: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@monitoring_bp.route('/capacity', methods=['GET'])
def get_capacity_status():
    """
    Get system capacity status (disk, Redis, queue).
    
    Returns: JSON with capacity information
    """
    # Check authentication
    auth_error = _check_auth()
    if auth_error:
        return auth_error
    
    try:
        resource_monitor = get_resource_monitor()
        queue_service = get_queue_service()
        
        system_status = resource_monitor.get_system_status() if resource_monitor else {
            "status": "unknown",
            "error": "ResourceMonitor not available"
        }
        queue_status = queue_service.get_queue_status()
        
        return jsonify({
            "status": "success",
            "data": {
                "system": system_status,
                "queue": queue_status,
                "can_accept_jobs": queue_status.get("can_accept_jobs", True)
            }
        }), 200
    except Exception as e:
        logger.error(f"Error getting capacity status: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@monitoring_bp.route('/health', methods=['GET'])
def get_monitoring_health():
    """
    Get monitoring service health (no auth required for health checks).
    
    Returns: JSON with monitoring service status
    """
    try:
        queue_service = get_queue_service()
        resource_monitor = get_resource_monitor()
        
        return jsonify({
            "status": "healthy",
            "services": {
                "queue_service": queue_service is not None,
                "resource_monitor": resource_monitor is not None
            }
        }), 200
    except Exception as e:
        logger.error(f"Error checking monitoring health: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500
