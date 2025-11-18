"""
PDF Hybrid Controller - Handles hybrid PDF text extraction business logic

Refactored to use BaseController and helpers for clean architecture.
"""

import logging
from typing import Dict, Any

from flask import request, current_app

from controllers.base_controller import BaseController
from config import get_config
from utils.constants import (
    ERROR_NO_FILE,
    ERROR_FILE_TOO_LARGE,
    ERROR_INVALID_DPI,
    ERROR_FILE_VALIDATION_FAILED,
    ERROR_INTERNAL_SERVER,
    MIN_DPI
)
from utils.validation_helpers import validate_dpi_with_error, extract_int_param
from utils.response_helpers import (
    create_hybrid_pdf_job_response,
    create_job_status_response,
    create_job_result_response
)
from utils.response_formatter import ResponseFormatter

logger = logging.getLogger(__name__)


class PDFHybridController(BaseController):
    """
    Controller class for handling hybrid PDF text extraction operations.
    
    Refactored to use BaseController and helper functions for clean architecture.
    Keeps only orchestration logic, delegates validation and formatting to helpers.
    """

    def __init__(self):
        """Initialize PDF hybrid controller with services from service manager."""
        super().__init__()
        self.job_service = self.service_manager.get_job_service()
        self.redis_service = self.service_manager.get_redis_service()
        self.config = get_config()

    def process_hybrid_pdf(self) -> tuple[Dict[str, Any], int]:
        """
        Create an async job for hybrid PDF text extraction.

        Returns:
            tuple: (response_dict with job_id, status_code)
        """
        try:
            # Validate file upload using helper
            file, filename, status_code = self._validate_file_upload('file')
            if status_code != 200:
                if status_code == 400:
                    return self._create_error_response(
                        ERROR_NO_FILE,
                        "Please upload a PDF file with the 'file' field",
                        400
                    )
                return self._create_error_response(ERROR_FILE_VALIDATION_FAILED, "File validation failed", status_code)

            # Parse and validate options using helpers
            # DPI
            dpi_param = request.form.get('dpi') or request.args.get('dpi', self.config.PDF_HYBRID_DEFAULT_DPI)
            is_valid_dpi, dpi, dpi_error = validate_dpi_with_error(
                dpi_param,
                MIN_DPI,
                self.config.PDF_HYBRID_MAX_DPI,
                self.config.PDF_HYBRID_DEFAULT_DPI
            )
            if not is_valid_dpi:
                return self._create_error_response(
                    ERROR_INVALID_DPI,
                    dpi_error or f"DPI must be between {MIN_DPI} and {self.config.PDF_HYBRID_MAX_DPI}",
                    400
                )

            # Chunk size
            chunk_size, chunk_error = extract_int_param(
                'chunk_size',
                self.config.PDF_HYBRID_DEFAULT_CHUNK_SIZE,
                min_value=1
            )
            if chunk_error:
                chunk_size = self.config.PDF_HYBRID_DEFAULT_CHUNK_SIZE

            # Max pages
            max_pages, pages_error = extract_int_param(
                'max_pages',
                self.config.PDF_HYBRID_MAX_PAGES,
                min_value=1
            )
            if pages_error:
                max_pages = self.config.PDF_HYBRID_MAX_PAGES

            # Read file data using helper
            file_data = self._read_file_data(file)

            # Validate file size using helper
            is_valid, status_code = self._validate_file_size(file_data)
            if not is_valid:
                max_size_mb = self._get_max_file_size_mb()
                return self._create_error_response(
                    ERROR_FILE_TOO_LARGE,
                    f"File size exceeds maximum limit of {max_size_mb}MB",
                    status_code
                )

            logger.info(
                f"Creating hybrid PDF job: {filename}, "
                f"dpi={dpi}, chunk_size={chunk_size}, max_pages={max_pages}"
            )

            # Create async job with options
            options = {
                "dpi": dpi,
                "chunk_size": chunk_size,
                "max_pages": max_pages,
                "text_threshold": self.config.PDF_HYBRID_TEXT_THRESHOLD,
                "image_area_threshold": self.config.PDF_HYBRID_IMAGE_AREA_THRESHOLD
            }

            job_id = self.job_service.create_hybrid_pdf_job(file_data, filename, options)

            # Get progress info (may not be available immediately)
            progress = None
            if self.redis_service:
                progress = self.redis_service.get_progress(job_id)

            # Use helper for job response creation
            response_data = create_hybrid_pdf_job_response(
                job_id,
                filename,
                len(file_data),
                processing_dpi=dpi,
                chunk_size=chunk_size,
                max_pages=max_pages
            )

            if progress:
                response_data["progress"] = progress

            # Use ResponseFormatter for consistent response
            response = ResponseFormatter.success_response(
                data=response_data,
                message="Hybrid PDF job created successfully",
                status_code=202
            )

            return response, 202

        except ValueError as e:
            logger.error(f"Validation error creating hybrid PDF job: {str(e)}")
            return self._create_error_response(ERROR_FILE_VALIDATION_FAILED, str(e), 400)
        except Exception as e:
            logger.error(f"Error creating hybrid PDF job: {str(e)}")
            return self._create_error_response(ERROR_INTERNAL_SERVER, str(e), 500)

    def get_job_status(self, job_id: str) -> tuple[Dict[str, Any], int]:
        """
        Get the status of an async hybrid PDF job.

        Args:
            job_id: Celery task ID

        Returns:
            tuple: (response_dict, status_code)
        """
        try:
            status = self.job_service.get_job_status(job_id)

            # Add progress information if available
            progress = None
            if self.redis_service:
                progress = self.redis_service.get_progress(job_id)

            # Use helper for status response formatting
            response, http_status = create_job_status_response(status, include_progress=True, progress_data=progress)
            return response, http_status

        except Exception as e:
            logger.error(f"Error getting job status: {str(e)}")
            return self._create_error_response(ERROR_INTERNAL_SERVER, str(e), 500)

    def get_job_result(self, job_id: str) -> tuple[Dict[str, Any], int]:
        """
        Get the result of a completed async hybrid PDF job.

        Args:
            job_id: Celery task ID

        Returns:
            tuple: (response_dict, status_code)
        """
        try:
            result = self.job_service.get_job_result(job_id)

            # Add progress if available
            progress = None
            if self.redis_service and not result.get('ready', False):
                progress = self.redis_service.get_progress(job_id)

            # Use helper for result response formatting
            response, http_status = create_job_result_response(result, include_progress=True, progress_data=progress)
            return response, http_status

        except Exception as e:
            logger.error(f"Error getting job result: {str(e)}")
            return self._create_error_response(ERROR_INTERNAL_SERVER, str(e), 500)

