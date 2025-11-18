"""
OCR Controller - Handles OCR-related business logic

Refactored to use BaseController and helpers for clean architecture.
"""

import logging
from typing import Dict, Any, List
from flask import request, current_app
from werkzeug.utils import secure_filename

from controllers.base_controller import BaseController
from utils.constants import (
    ERROR_NO_FILE,
    ERROR_FILE_TOO_LARGE,
    ERROR_INVALID_DPI,
    ERROR_FILE_VALIDATION_FAILED,
    ERROR_INTERNAL_SERVER,
    DEFAULT_DPI,
    MIN_DPI,
    MAX_DPI
)
from utils.validation_helpers import validate_dpi_with_error, validate_batch_files
from utils.response_helpers import (
    create_job_status_response,
    create_job_result_response,
    format_batch_response
)
from utils.response_formatter import ResponseFormatter
from utils.file_upload_helpers import is_image_file, is_pdf_file
from utils.resource_manager import get_resource_manager

logger = logging.getLogger(__name__)


class OCRController(BaseController):
    """
    Controller class for handling OCR operations.
    
    Refactored to use BaseController and helper functions for clean architecture.
    Keeps only orchestration logic, delegates validation and formatting to helpers.
    """

    def __init__(self):
        """Initialize OCR controller with services from service manager."""
        super().__init__()
        self.job_service = self.service_manager.get_job_service()
        self.resource_manager = get_resource_manager()

    def process_image(self) -> tuple[Dict[str, Any], int]:
        """
        Create an async job for processing an uploaded image file for OCR.

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
                        "Please upload an image file with the 'file' field",
                        400
                    )
                return self._create_error_response(ERROR_FILE_VALIDATION_FAILED, "File validation failed", status_code)

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

            logger.info(f"Creating async job for image: {filename}")

            # Create async job
            job_id = self.job_service.create_image_job(file_data, filename)

            # Use ResponseFormatter for consistent response
            response = ResponseFormatter.success_response(
                data=self._create_job_response(job_id, filename, len(file_data)),
                message="OCR job created successfully",
                status_code=202
            )
            return response, 202

        except Exception as e:
            logger.error(f"Error creating image OCR job: {str(e)}")
            return self._create_error_response(ERROR_INTERNAL_SERVER, str(e), 500)

    def process_pdf(self) -> tuple[Dict[str, Any], int]:
        """
        Create an async job for processing an uploaded PDF file for OCR.

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

            # Get and validate DPI using helper
            dpi_param = request.args.get('dpi', DEFAULT_DPI)
            is_valid_dpi, dpi, dpi_error = validate_dpi_with_error(dpi_param, MIN_DPI, MAX_DPI, DEFAULT_DPI)
            if not is_valid_dpi:
                return self._create_error_response(ERROR_INVALID_DPI, dpi_error or f"DPI must be between {MIN_DPI} and {MAX_DPI}", 400)

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

            logger.info(f"Creating async job for PDF: {filename} at {dpi} DPI")

            # Create async job
            job_id = self.job_service.create_pdf_job(file_data, filename, dpi)

            # Use ResponseFormatter for consistent response
            response = ResponseFormatter.success_response(
                data=self._create_job_response(job_id, filename, len(file_data), processing_dpi=dpi),
                message="OCR job created successfully",
                status_code=202
            )
            return response, 202

        except Exception as e:
            logger.error(f"Error creating PDF OCR job: {str(e)}")
            return self._create_error_response(ERROR_INTERNAL_SERVER, str(e), 500)

    def process_batch(self) -> tuple[Dict[str, Any], int]:
        """
        Create async jobs for processing multiple uploaded files for OCR.

        Returns:
            tuple: (response_dict with job_ids, status_code)
        """
        try:
            # Validate batch files using helper
            files = request.files.getlist('files') if 'files' in request.files else []
            is_valid, error_msg, status_code = validate_batch_files(files)
            if not is_valid:
                return self._create_error_response("No files provided", error_msg or "Please upload files", status_code)

            # Get and validate DPI using helper
            dpi_param = request.args.get('dpi', DEFAULT_DPI)
            is_valid_dpi, dpi, dpi_error = validate_dpi_with_error(dpi_param, MIN_DPI, MAX_DPI, DEFAULT_DPI)
            if not is_valid_dpi:
                dpi = DEFAULT_DPI  # Use default if invalid

            job_ids: List[Dict[str, Any]] = []
            total_files = 0
            created_jobs = 0

            for file in files:
                if file.filename == '':
                    continue

                total_files += 1
                filename = secure_filename(file.filename)
                file_data = self._read_file_data(file)

                # Validate file size using helper
                is_valid, status_code = self._validate_file_size(file_data)
                if not is_valid:
                    max_size_mb = self._get_max_file_size_mb()
                    job_ids.append({
                        "filename": filename,
                        "success": False,
                        "error": f"File too large (max {max_size_mb}MB)",
                        "type": "unknown"
                    })
                    continue

                # Determine file type and create job accordingly
                try:
                    if is_pdf_file(filename):
                        logger.info(f"Creating PDF job in batch: {filename}")
                        job_id = self.job_service.create_pdf_job(file_data, filename, dpi)
                        job_ids.append({
                            "filename": filename,
                            "job_id": job_id,
                            "status": "processing",
                            "type": "pdf",
                            "file_size": len(file_data)
                        })
                        created_jobs += 1
                    elif is_image_file(filename):
                        logger.info(f"Creating image job in batch: {filename}")
                        job_id = self.job_service.create_image_job(file_data, filename)
                        job_ids.append({
                            "filename": filename,
                            "job_id": job_id,
                            "status": "processing",
                            "type": "image",
                            "file_size": len(file_data)
                        })
                        created_jobs += 1
                    else:
                        job_ids.append({
                            "filename": filename,
                            "success": False,
                            "error": "Unsupported file type",
                            "type": "unknown"
                        })
                        continue

                except Exception as file_error:
                    logger.error(f"Error creating job for file {filename}: {str(file_error)}")
                    job_ids.append({
                        "filename": filename,
                        "success": False,
                        "error": str(file_error),
                        "type": "unknown"
                    })

            # Use helper for batch response formatting
            summary = {
                "total_files": total_files,
                "jobs_created": created_jobs,
                "failed_files": total_files - created_jobs,
                "success": created_jobs > 0
            }
            response = ResponseFormatter.success_response(
                data=format_batch_response(job_ids, summary),
                message="Batch jobs created successfully",
                status_code=202
            )

            logger.info(f"Batch job creation completed: {created_jobs}/{total_files} jobs created")
            return response, 202  # 202 Accepted

        except Exception as e:
            logger.error(f"Error in batch job creation: {str(e)}")
            return self._create_error_response(ERROR_INTERNAL_SERVER, str(e), 500)

    def get_job_status(self, job_id: str) -> tuple[Dict[str, Any], int]:
        """
        Get the status of an async OCR job.

        Args:
            job_id: Celery task ID

        Returns:
            tuple: (response_dict, status_code)
        """
        try:
            status = self.job_service.get_job_status(job_id)

            # Use helper for status response formatting
            response, http_status = create_job_status_response(status)
            return response, http_status

        except Exception as e:
            logger.error(f"Error getting job status: {str(e)}")
            return self._create_error_response(ERROR_INTERNAL_SERVER, str(e), 500)

    def get_job_result(self, job_id: str) -> tuple[Dict[str, Any], int]:
        """
        Get the result of a completed async OCR job.

        Args:
            job_id: Celery task ID

        Returns:
            tuple: (response_dict, status_code)
        """
        try:
            result = self.job_service.get_job_result(job_id)

            # Use helper for result response formatting
            response, http_status = create_job_result_response(result)
            return response, http_status

        except Exception as e:
            logger.error(f"Error getting job result: {str(e)}")
            return self._create_error_response(ERROR_INTERNAL_SERVER, str(e), 500)
