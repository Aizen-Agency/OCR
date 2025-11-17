"""
PDF Hybrid Controller - Handles hybrid PDF text extraction business logic
"""

import logging
from typing import Dict, Any

from flask import request, current_app
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

from config import get_config
from services.job_service import JobService
from services.redis_service import RedisService
from utils.constants import (
    ERROR_NO_FILE,
    ERROR_FILE_TOO_LARGE,
    ERROR_INVALID_DPI,
    ERROR_FILE_VALIDATION_FAILED,
    ERROR_INTERNAL_SERVER,
    HYBRID_PDF_JOB_CREATED_MESSAGE,
    DEFAULT_DPI,
    MIN_DPI,
    MAX_DPI
)
from utils.validators import validate_dpi

logger = logging.getLogger(__name__)


class PDFHybridController:
    """
    Controller class for handling hybrid PDF text extraction operations.
    """

    def __init__(self, job_service: JobService, redis_service: RedisService):
        self.job_service = job_service
        self.redis_service = redis_service
        self.config = get_config()

    def _validate_file_upload(self, file_field: str = 'file') -> tuple:
        """
        Validate file upload from request.

        Returns:
            tuple: (file_object, filename, error_status_code)
                   Returns (None, None, status_code) on error
        """
        # Check if file was uploaded
        if file_field not in request.files:
            return None, None, 400

        file = request.files[file_field]

        if file.filename == '':
            return None, None, 400

        # Secure filename
        filename = secure_filename(file.filename)

        return file, filename, 200

    def _create_error_response(self, error: str, message: str, status_code: int = 400) -> tuple[Dict[str, Any], int]:
        """
        Create standardized error response.

        Args:
            error: Error type
            message: Error message
            status_code: HTTP status code

        Returns:
            tuple: (error_response_dict, status_code)
        """
        return {
            "error": error,
            "message": message
        }, status_code

    def _create_job_response(self, job_id: str, filename: str, file_size: int, **kwargs) -> Dict[str, Any]:
        """
        Create standardized job creation response.

        Args:
            job_id: Created job ID
            filename: Filename
            file_size: File size in bytes
            **kwargs: Additional fields to include

        Returns:
            Job creation response dictionary
        """
        response = {
            "job_id": job_id,
            "status": "queued",
            "filename": filename,
            "file_size": file_size,
            "strategy": "hybrid_pdf",
            "message": HYBRID_PDF_JOB_CREATED_MESSAGE
        }
        response.update(kwargs)
        return response

    def _validate_file_size(self, file_data: bytes) -> tuple[bool, int]:
        """
        Validate file size against configured limits.

        Returns:
            tuple: (is_valid, error_status_code)
        """
        max_size = current_app.config['MAX_CONTENT_LENGTH']
        if len(file_data) > max_size:
            return False, 413
        return True, 200

    def process_hybrid_pdf(self) -> tuple[Dict[str, Any], int]:
        """
        Create an async job for hybrid PDF text extraction.

        Returns:
            tuple: (response_dict with job_id, status_code)
        """
        try:
            # Validate file upload
            file, filename, status_code = self._validate_file_upload('file')
            if status_code != 200:
                if status_code == 400:
                    return self._create_error_response(
                        ERROR_NO_FILE,
                        "Please upload a PDF file with the 'file' field",
                        400
                    )
                return self._create_error_response(ERROR_FILE_VALIDATION_FAILED, "File validation failed", status_code)

            # Parse options from form data or query params
            # DPI
            dpi = request.form.get('dpi') or request.args.get('dpi', self.config.PDF_HYBRID_DEFAULT_DPI)
            try:
                dpi = int(dpi)
            except (ValueError, TypeError):
                dpi = self.config.PDF_HYBRID_DEFAULT_DPI

            is_valid_dpi, dpi_error = validate_dpi(dpi, MIN_DPI, self.config.PDF_HYBRID_MAX_DPI)
            if not is_valid_dpi:
                return self._create_error_response(
                    ERROR_INVALID_DPI,
                    dpi_error or f"DPI must be between {MIN_DPI} and {self.config.PDF_HYBRID_MAX_DPI}",
                    400
                )

            # Chunk size
            chunk_size = request.form.get('chunk_size') or request.args.get('chunk_size', self.config.PDF_HYBRID_DEFAULT_CHUNK_SIZE)
            try:
                chunk_size = int(chunk_size)
                if chunk_size < 1:
                    chunk_size = self.config.PDF_HYBRID_DEFAULT_CHUNK_SIZE
            except (ValueError, TypeError):
                chunk_size = self.config.PDF_HYBRID_DEFAULT_CHUNK_SIZE

            # Max pages
            max_pages = request.form.get('max_pages') or request.args.get('max_pages', self.config.PDF_HYBRID_MAX_PAGES)
            try:
                max_pages = int(max_pages)
                if max_pages < 1:
                    max_pages = self.config.PDF_HYBRID_MAX_PAGES
            except (ValueError, TypeError):
                max_pages = self.config.PDF_HYBRID_MAX_PAGES

            # Read file data
            file_data = file.read()

            # Validate file size
            is_valid, status_code = self._validate_file_size(file_data)
            if not is_valid:
                max_size_mb = current_app.config['MAX_CONTENT_LENGTH'] // (1024*1024)
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
            progress = self.redis_service.get_progress(job_id)

            response = self._create_job_response(
                job_id,
                filename,
                len(file_data),
                processing_dpi=dpi,
                chunk_size=chunk_size,
                max_pages=max_pages
            )

            if progress:
                response["progress"] = progress

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
            progress = self.redis_service.get_progress(job_id)
            if progress:
                status["progress"] = progress

            if status.get('status') == 'error':
                return status, 500

            # Map Celery states to HTTP status codes
            celery_state = status.get('status', 'unknown')
            if celery_state == 'pending':
                return status, 202  # Accepted
            elif celery_state == 'started' or celery_state == 'processing':
                return status, 202  # Accepted
            elif celery_state == 'success' or celery_state == 'completed':
                return status, 200  # OK
            elif celery_state == 'failure' or celery_state == 'failed':
                return status, 500  # Internal Server Error
            else:
                return status, 200  # Default

        except Exception as e:
            logger.error(f"Error getting job status: {str(e)}")
            return {
                "job_id": job_id,
                "status": "error",
                "error": str(e)
            }, 500

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

            if result.get('status') == 'error':
                return result, 500

            if not result.get('ready', False):
                # Add progress if available
                progress = self.redis_service.get_progress(job_id)
                if progress:
                    result["progress"] = progress
                return result, 202  # Still processing

            if result.get('status') == 'failed':
                return result, 500

            return result, 200

        except Exception as e:
            logger.error(f"Error getting job result: {str(e)}")
            return {
                "job_id": job_id,
                "status": "error",
                "error": str(e)
            }, 500

