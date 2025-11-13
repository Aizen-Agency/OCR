"""
Health Controller - Handles health check operations
"""

import logging
from typing import Dict, Any

from services.ocr_service.ocr_service import OCRService

logger = logging.getLogger(__name__)


class HealthController:
    """
    Controller class for handling health check operations.
    """

    def __init__(self, ocr_service: OCRService):
        self.ocr_service = ocr_service

    def get_health_status(self) -> tuple[Dict[str, Any], int]:
        """
        Get comprehensive health status of the service.

        Returns:
            tuple: (health_response_dict, status_code)
        """
        try:
            # Get OCR service health
            service_health = self.ocr_service.health_check()
            status_code = 200 if service_health['status'] == 'healthy' else 503

            response = {
                "status": service_health['status'],
                "service": "OCR Microservice",
                "timestamp": self._get_current_timestamp(),
                "version": "1.0.0",  # Could be made configurable
                "ocr_service": service_health,
                "checks": {
                    "ocr_service_initialized": service_health.get('initialized', False),
                    "paddleocr_available": service_health.get('paddleocr_available', False),
                    "memory_usage": service_health.get('memory_usage', {}),
                    "configuration_loaded": True  # Could be expanded to check config validity
                }
            }

            # Add detailed health information
            response["details"] = self._get_detailed_health_info(service_health)

            return response, status_code

        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "error",
                "service": "OCR Microservice",
                "timestamp": self._get_current_timestamp(),
                "error": str(e),
                "checks": {
                    "health_check_failed": True
                }
            }, 500

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"

    def _get_detailed_health_info(self, service_health: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get detailed health information including recommendations.

        Args:
            service_health: Health data from OCR service

        Returns:
            Dict with detailed health analysis
        """
        details = {
            "service_status": "operational" if service_health.get('status') == 'healthy' else "degraded",
            "recommendations": []
        }

        # Check memory usage
        memory_info = service_health.get('memory_usage', {})
        memory_percent = memory_info.get('percent', 0)

        if memory_percent > 85:
            details["service_status"] = "critical"
            details["recommendations"].append("High memory usage detected. Consider restarting the service.")
        elif memory_percent > 70:
            details["service_status"] = "warning"
            details["recommendations"].append("Elevated memory usage. Monitor closely.")

        # Check OCR service
        if not service_health.get('initialized', False):
            details["service_status"] = "critical"
            details["recommendations"].append("OCR service not initialized. Check service configuration.")

        if not service_health.get('paddleocr_available', False):
            details["service_status"] = "critical"
            details["recommendations"].append("PaddleOCR not available. Check PaddleOCR installation.")

        # If no issues found, service is healthy
        if not details["recommendations"]:
            details["recommendations"].append("All systems operational.")

        return details

    def get_readiness_status(self) -> tuple[Dict[str, Any], int]:
        """
        Get readiness status (used for Kubernetes readiness probes).

        Returns:
            tuple: (readiness_response_dict, status_code)
        """
        try:
            service_health = self.ocr_service.health_check()

            # Readiness is simpler - just check if service can handle requests
            is_ready = service_health.get('initialized', False) and service_health.get('paddleocr_available', False)

            response = {
                "status": "ready" if is_ready else "not ready",
                "service": "OCR Microservice",
                "timestamp": self._get_current_timestamp(),
                "checks": {
                    "ocr_service_initialized": service_health.get('initialized', False),
                    "paddleocr_available": service_health.get('paddleocr_available', False)
                }
            }

            return response, 200 if is_ready else 503

        except Exception as e:
            logger.error(f"Readiness check failed: {str(e)}")
            return {
                "status": "error",
                "service": "OCR Microservice",
                "timestamp": self._get_current_timestamp(),
                "error": str(e)
            }, 503

    def get_liveness_status(self) -> tuple[Dict[str, Any], int]:
        """
        Get liveness status (used for Kubernetes liveness probes).
        Simpler check - just verify the service is running.

        Returns:
            tuple: (liveness_response_dict, status_code)
        """
        try:
            response = {
                "status": "alive",
                "service": "OCR Microservice",
                "timestamp": self._get_current_timestamp()
            }

            return response, 200

        except Exception as e:
            logger.error(f"Liveness check failed: {str(e)}")
            return {
                "status": "error",
                "service": "OCR Microservice",
                "timestamp": self._get_current_timestamp(),
                "error": str(e)
            }, 503
