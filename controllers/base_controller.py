"""
Base Controller - Abstract base class for all controllers

Provides common functionality and helper methods to eliminate code duplication
across controllers. All controllers should inherit from this base class.
"""

from abc import ABC
from typing import Dict, Any, Tuple
from flask import current_app
from utils.response_helpers import (
    create_error_response as _create_error_response,
    create_job_response as _create_job_response,
    map_celery_state_to_http_status
)
from utils.file_upload_helpers import (
    validate_file_upload,
    read_file_data,
    validate_file_size
)
from utils.service_manager import get_service_manager


class BaseController(ABC):
    """
    Abstract base class for all controllers.
    
    Provides common methods and helper functions to eliminate code duplication.
    Controllers should inherit from this class and use the provided helpers.
    """
    
    def __init__(self):
        """Initialize base controller with service manager."""
        self.service_manager = get_service_manager()
    
    def _create_error_response(self, error: str, message: str, status_code: int = 400) -> Tuple[Dict[str, Any], int]:
        """
        Create standardized error response.
        
        Args:
            error: Error type/code
            message: Error message
            status_code: HTTP status code
        
        Returns:
            tuple: (error_response_dict, status_code)
        """
        return _create_error_response(error, message, status_code)
    
    def _create_job_response(
        self,
        job_id: str,
        filename: str,
        file_size: int,
        status: str = "processing",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create standardized job creation response.
        
        Args:
            job_id: Created job ID
            filename: Filename
            file_size: File size in bytes
            status: Job status (default: "processing")
            **kwargs: Additional fields to include
        
        Returns:
            Job creation response dictionary
        """
        return _create_job_response(job_id, filename, file_size, status=status, **kwargs)
    
    def _validate_file_upload(self, file_field: str = 'file') -> Tuple:
        """
        Validate file upload from request.
        
        Args:
            file_field: Name of the file field in the request
        
        Returns:
            tuple: (file_object, filename, status_code)
                   Returns (None, None, status_code) on error
        """
        return validate_file_upload(file_field)
    
    def _read_file_data(self, file) -> bytes:
        """
        Read file data from FileStorage object.
        
        Args:
            file: FileStorage object from Flask request
        
        Returns:
            File data as bytes
        """
        return read_file_data(file)
    
    def _validate_file_size(self, file_data: bytes, max_size: int = None) -> Tuple[bool, int]:
        """
        Validate file size against configured limits.
        
        Args:
            file_data: File data as bytes
            max_size: Maximum allowed size in bytes (if None, uses Flask's MAX_CONTENT_LENGTH)
        
        Returns:
            tuple: (is_valid, error_status_code)
        """
        if max_size is None:
            max_size = current_app.config['MAX_CONTENT_LENGTH']
        return validate_file_size(file_data, max_size)
    
    def _map_celery_state_to_http_status(self, celery_state: str) -> int:
        """
        Map Celery task state to appropriate HTTP status code.
        
        Args:
            celery_state: Celery task state
        
        Returns:
            HTTP status code
        """
        return map_celery_state_to_http_status(celery_state)
    
    def _get_max_file_size_mb(self) -> int:
        """
        Get maximum file size in MB from Flask config.
        
        Returns:
            Maximum file size in MB
        """
        max_size_bytes = current_app.config['MAX_CONTENT_LENGTH']
        return max_size_bytes // (1024 * 1024)

