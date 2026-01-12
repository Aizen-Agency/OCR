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
    ERROR_UNSUPPORTED_FILE_TYPE,
    MIN_DPI
)
from utils.validation_helpers import validate_dpi_with_error, extract_int_param
from utils.file_upload_helpers import is_pdf_file
from utils.response_helpers import (
    create_hybrid_pdf_job_response,
    create_job_status_response,
    create_job_result_response
)
from utils.response_formatter import ResponseFormatter
from utils.service_manager import get_queue_service

logger = logging.getLogger(__name__)


class PDFHybridController(BaseController):
    """
    Controller class for handling hybrid PDF text extraction operations.
    
    Refactored to use BaseController and helper functions for clean architecture.
    Keeps only orchestration logic, delegates validation and formatting to helpers.
    """

    def __init__(self):
        """Initialize PDF hybrid controller with services from service manager."""
        import sys
        print("PDFHybridController.__init__: Starting", file=sys.stderr, flush=True)
        super().__init__()
        print("PDFHybridController.__init__: BaseController initialized", file=sys.stderr, flush=True)
        
        print("PDFHybridController.__init__: Getting job_service", file=sys.stderr, flush=True)
        self.job_service = self.service_manager.get_job_service()
        print("PDFHybridController.__init__: job_service obtained", file=sys.stderr, flush=True)
        
        print("PDFHybridController.__init__: Getting redis_service", file=sys.stderr, flush=True)
        self.redis_service = self.service_manager.get_redis_service()
        print("PDFHybridController.__init__: redis_service obtained", file=sys.stderr, flush=True)
        
        print("PDFHybridController.__init__: Getting config", file=sys.stderr, flush=True)
        self.config = get_config()
        print("PDFHybridController.__init__: Config obtained, initialization complete", file=sys.stderr, flush=True)

    def process_hybrid_pdf(self) -> tuple[Dict[str, Any], int]:
        """
        Create an async job for hybrid PDF text extraction.

        Returns:
            tuple: (response_dict with job_id, status_code)
        """
        import sys
        print("process_hybrid_pdf: Starting request processing", file=sys.stderr, flush=True)
        logger.info("process_hybrid_pdf: Starting request processing")
        try:
            # Validate file upload using helper
            print("process_hybrid_pdf: About to call _validate_file_upload (this accesses request.files)", file=sys.stderr, flush=True)
            logger.info("process_hybrid_pdf: Validating file upload")
            file, filename, status_code = self._validate_file_upload('file')
            print(f"process_hybrid_pdf: File upload validation complete, status={status_code}, filename={filename}", file=sys.stderr, flush=True)
            logger.info(f"process_hybrid_pdf: File upload validation complete, status={status_code}, filename={filename}")
            if status_code != 200:
                if status_code == 400:
                    return self._create_error_response(
                        ERROR_NO_FILE,
                        "Please upload a PDF file with the 'file' field",
                        400
                    )
                return self._create_error_response(ERROR_FILE_VALIDATION_FAILED, "File validation failed", status_code)

            # Validate file type - only PDFs allowed
            print("process_hybrid_pdf: Validating file type", file=sys.stderr, flush=True)
            if not is_pdf_file(filename):
                return self._create_error_response(
                    ERROR_UNSUPPORTED_FILE_TYPE,
                    f"Only PDF files are allowed. Received: {filename}",
                    400
                )
            print("process_hybrid_pdf: File type validated", file=sys.stderr, flush=True)

            # Parse and validate options using helpers
            # DPI
            print("process_hybrid_pdf: Parsing DPI parameter", file=sys.stderr, flush=True)
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
            print(f"process_hybrid_pdf: DPI validated: {dpi}", file=sys.stderr, flush=True)

            # Chunk size
            print("process_hybrid_pdf: Parsing chunk_size parameter", file=sys.stderr, flush=True)
            chunk_size, chunk_error = extract_int_param(
                'chunk_size',
                self.config.PDF_HYBRID_DEFAULT_CHUNK_SIZE,
                min_value=1
            )
            if chunk_error:
                chunk_size = self.config.PDF_HYBRID_DEFAULT_CHUNK_SIZE
            print(f"process_hybrid_pdf: Chunk size: {chunk_size}", file=sys.stderr, flush=True)

            # Max pages
            print("process_hybrid_pdf: Parsing max_pages parameter", file=sys.stderr, flush=True)
            max_pages, pages_error = extract_int_param(
                'max_pages',
                self.config.PDF_HYBRID_MAX_PAGES,
                min_value=1
            )
            if pages_error:
                max_pages = self.config.PDF_HYBRID_MAX_PAGES
            print(f"process_hybrid_pdf: Max pages: {max_pages}", file=sys.stderr, flush=True)

            # Read file data using helper
            print("process_hybrid_pdf: Reading file data (THIS MAY TAKE TIME FOR LARGE FILES)", file=sys.stderr, flush=True)
            logger.info("process_hybrid_pdf: Reading file data")
            file_data = self._read_file_data(file)
            print(f"process_hybrid_pdf: File data read, size={len(file_data)} bytes", file=sys.stderr, flush=True)
            logger.info(f"process_hybrid_pdf: File data read, size={len(file_data)} bytes")

            # Validate file size using helper
            print("process_hybrid_pdf: Validating file size", file=sys.stderr, flush=True)
            logger.info("process_hybrid_pdf: Validating file size")
            is_valid, status_code = self._validate_file_size(file_data)
            if not is_valid:
                max_size_mb = self._get_max_file_size_mb()
                return self._create_error_response(
                    ERROR_FILE_TOO_LARGE,
                    f"File size exceeds maximum limit of {max_size_mb}MB",
                    status_code
                )
            print("process_hybrid_pdf: File size validated", file=sys.stderr, flush=True)

            # Check system capacity before accepting job
            # Note: Capacity checks have built-in timeouts and fail-open behavior
            print("process_hybrid_pdf: Checking system capacity", file=sys.stderr, flush=True)
            try:
                print("process_hybrid_pdf: Getting queue_service", file=sys.stderr, flush=True)
                queue_service = get_queue_service()
                print("process_hybrid_pdf: queue_service obtained", file=sys.stderr, flush=True)
                file_size_mb = len(file_data) / (1024 * 1024)  # Convert bytes to MB
                print(f"process_hybrid_pdf: File size: {file_size_mb:.2f} MB", file=sys.stderr, flush=True)
                print("process_hybrid_pdf: Calling can_accept_new_job", file=sys.stderr, flush=True)
                capacity_check = queue_service.can_accept_new_job(estimated_pdf_size_mb=file_size_mb)
                print(f"process_hybrid_pdf: Capacity check result: {capacity_check.get('can_accept', False)}", file=sys.stderr, flush=True)
                
                if not capacity_check.get("can_accept", True):
                    reason = capacity_check.get("reason", "capacity_exceeded")
                    message = capacity_check.get("message", "System is at capacity. Please try again later.")
                    
                    # Return 503 Service Unavailable
                    error_response, status_code = self._create_error_response(
                        "SERVICE_UNAVAILABLE",
                        message,
                        503
                    )
                    # Add retry-after header suggestion (in minutes)
                    wait_time = capacity_check.get("estimated_wait_time_minutes", 60)
                    error_response["retry_after_minutes"] = wait_time
                    error_response["details"] = capacity_check
                    
                    logger.warning(
                        f"Job rejected due to capacity: {reason} - {message} "
                        f"(queue_size={capacity_check.get('queue_size', 0)})"
                    )
                    return error_response, 503
            except Exception as e:
                # If capacity check fails, log warning but allow job (fail open)
                print(f"process_hybrid_pdf: Capacity check failed, allowing job: {str(e)}", file=sys.stderr, flush=True)
                logger.warning(f"Capacity check failed, allowing job: {str(e)}")

            print(
                f"process_hybrid_pdf: Creating hybrid PDF job: {filename}, "
                f"dpi={dpi}, chunk_size={chunk_size}, max_pages={max_pages}", file=sys.stderr, flush=True
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

            print("process_hybrid_pdf: Calling job_service.create_hybrid_pdf_job (THIS IS WHERE PDF PARSING HAPPENS - MAY TAKE TIME)", file=sys.stderr, flush=True)
            logger.info("process_hybrid_pdf: Calling job_service.create_hybrid_pdf_job (this may take time for PDF parsing)")
            job_id = self.job_service.create_hybrid_pdf_job(file_data, filename, options)
            print(f"process_hybrid_pdf: Job created successfully, job_id={job_id}", file=sys.stderr, flush=True)
            logger.info(f"process_hybrid_pdf: Job created successfully, job_id={job_id}")

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

