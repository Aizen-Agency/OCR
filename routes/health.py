"""
Health Blueprint - Routes for health check operations
"""

from flask import Blueprint, jsonify, current_app
from controllers.health_controller import HealthController

# Create blueprint
health_bp = Blueprint('health', __name__, url_prefix='/health')


def get_health_controller() -> HealthController:
    """Get health controller instance with app's service."""
    return HealthController(current_app.ocr_service)


@health_bp.route('', methods=['GET'])
@health_bp.route('/', methods=['GET'])
def health_check():
    """
    Get comprehensive health status of the service.

    Returns: JSON with detailed health information
    """
    controller = get_health_controller()
    result, status_code = controller.get_health_status()
    return jsonify(result), status_code


@health_bp.route('/ready', methods=['GET'])
def readiness_check():
    """
    Get readiness status for Kubernetes readiness probes.

    Returns: JSON with readiness status
    """
    controller = get_health_controller()
    result, status_code = controller.get_readiness_status()
    return jsonify(result), status_code


@health_bp.route('/alive', methods=['GET'])
def liveness_check():
    """
    Get liveness status for Kubernetes liveness probes.

    Returns: JSON with liveness status
    """
    controller = get_health_controller()
    result, status_code = controller.get_liveness_status()
    return jsonify(result), status_code
