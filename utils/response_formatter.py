"""
Response Formatter - Utilities for standardizing API responses
"""

import logging
import time
from typing import Dict, Any, Optional, Union
from datetime import datetime

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """
    Utility class for formatting API responses consistently.
    """

    @staticmethod
    def success_response(
        data: Any = None,
        message: str = "Success",
        status_code: int = 200,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format a successful response.

        Args:
            data: Response data
            message: Success message
            status_code: HTTP status code
            metadata: Additional metadata

        Returns:
            Formatted response dictionary
        """
        response = {
            "success": True,
            "message": message,
            "timestamp": ResponseFormatter._get_current_timestamp(),
            "status_code": status_code
        }

        if data is not None:
            response["data"] = data

        if metadata:
            response["metadata"] = metadata

        return response

    @staticmethod
    def error_response(
        message: str = "An error occurred",
        error_code: Optional[str] = None,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format an error response.

        Args:
            message: Error message
            error_code: Specific error code
            status_code: HTTP status code
            details: Additional error details
            request_id: Request ID for tracking

        Returns:
            Formatted error response dictionary
        """
        response = {
            "success": False,
            "message": message,
            "timestamp": ResponseFormatter._get_current_timestamp(),
            "status_code": status_code
        }

        if error_code:
            response["error_code"] = error_code

        if details:
            response["details"] = details

        if request_id:
            response["request_id"] = request_id

        return response

    @staticmethod
    def paginated_response(
        items: list,
        page: int,
        per_page: int,
        total: int,
        total_pages: int,
        base_url: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format a paginated response.

        Args:
            items: List of items for current page
            page: Current page number
            per_page: Items per page
            total: Total number of items
            total_pages: Total number of pages
            base_url: Base URL for pagination links
            metadata: Additional metadata

        Returns:
            Formatted paginated response
        """
        response = ResponseFormatter.success_response(
            data={
                "items": items,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1,
                    "next_page": page + 1 if page < total_pages else None,
                    "prev_page": page - 1 if page > 1 else None
                }
            },
            message="Data retrieved successfully"
        )

        if metadata:
            response["metadata"] = metadata

        return response

    @staticmethod
    def health_response(
        status: str,
        service_name: str,
        checks: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format a health check response.

        Args:
            status: Health status (healthy, unhealthy, degraded)
            service_name: Name of the service
            checks: Individual health checks
            details: Additional health details

        Returns:
            Formatted health response
        """
        response = {
            "status": status,
            "service": service_name,
            "timestamp": ResponseFormatter._get_current_timestamp(),
            "uptime": ResponseFormatter._get_uptime()
        }

        if checks:
            response["checks"] = checks

        if details:
            response["details"] = details

        return response

    @staticmethod
    def file_upload_response(
        filename: str,
        file_size: int,
        processing_time: float,
        result: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format a file upload/processing response.

        Args:
            filename: Name of processed file
            file_size: Size of file in bytes
            processing_time: Time taken to process in seconds
            result: Processing result
            metadata: Additional metadata

        Returns:
            Formatted file processing response
        """
        response = ResponseFormatter.success_response(
            data=result,
            message=f"File '{filename}' processed successfully",
            metadata={
                "filename": filename,
                "file_size_bytes": file_size,
                "processing_time_seconds": round(processing_time, 2),
                **(metadata or {})
            }
        )

        return response

    @staticmethod
    def batch_response(
        results: list,
        summary: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format a batch processing response.

        Args:
            results: List of individual results
            summary: Batch processing summary
            metadata: Additional metadata

        Returns:
            Formatted batch response
        """
        response = ResponseFormatter.success_response(
            data={
                "results": results,
                "summary": summary
            },
            message=f"Batch processing completed: {summary.get('processed_files', 0)}/{summary.get('total_files', 0)} files processed"
        )

        if metadata:
            response["metadata"] = metadata

        return response

    @staticmethod
    def _get_current_timestamp() -> str:
        """Get current timestamp in ISO format."""
        return datetime.utcnow().isoformat() + "Z"

    @staticmethod
    def _get_uptime() -> Optional[float]:
        """Get service uptime in seconds."""
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            uptime = time.time() - process.create_time()
            return round(uptime, 2)
        except Exception:
            return None
