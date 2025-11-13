"""
OCR Controller - Handles OCR-related business logic
"""

import logging
import time
from typing import Dict, Any, List
from flask import request, current_app
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

from services.ocr_service.ocr_service import OCRService
from services.job_service import JobService
from services.redis_service import RedisService

logger = logging.getLogger(__name__)


class OCRController:
    """
    Controller class for handling OCR operations.
    Contains all the business logic for OCR endpoints.
    """

    def __init__(self, ocr_service: OCRService, job_service: JobService, redis_service: RedisService):
        self.ocr_service = ocr_service
        self.job_service = job_service
        self.redis_service = redis_service

    def _validate_file_upload(self, file_field: str = 'file') -> tuple[FileStorage, str, int]:
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
            "status": "processing",
            "filename": filename,
            "file_size": file_size,
            "message": JOB_CREATED_MESSAGE
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

    def _process_file_with_timing(self, processor_func, *args, **kwargs) -> tuple[Dict[str, Any], float]:
        """
        Process a file and track execution time.

        Returns:
            tuple: (result_dict, processing_time_seconds)
        """
        start_time = time.time()
        try:
            result = processor_func(*args, **kwargs)
            processing_time = time.time() - start_time
            return result, processing_time
        finally:
            # Always cleanup memory
            self.ocr_service.cleanup_memory()

    def process_image(self) -> tuple[Dict[str, Any], int]:
        """
        Create an async job for processing an uploaded image file for OCR.

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
                        "Please upload an image file with the 'file' field",
                        400
                    )
                return self._create_error_response(ERROR_FILE_VALIDATION_FAILED, "File validation failed", status_code)

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

            logger.info(f"Creating async job for image: {filename}")

            # Create async job
            job_id = self.job_service.create_image_job(file_data, filename)

            return self._create_job_response(job_id, filename, len(file_data)), 202

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

            # Get and validate DPI
            dpi = request.args.get('dpi', DEFAULT_DPI, type=int)
            is_valid_dpi, dpi_error = validate_dpi(dpi, MIN_DPI, MAX_DPI)
            if not is_valid_dpi:
                return self._create_error_response(ERROR_INVALID_DPI, dpi_error or f"DPI must be between {MIN_DPI} and {MAX_DPI}", 400)

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

            logger.info(f"Creating async job for PDF: {filename} at {dpi} DPI")

            # Create async job
            job_id = self.job_service.create_pdf_job(file_data, filename, dpi)

            return self._create_job_response(job_id, filename, len(file_data), processing_dpi=dpi), 202

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
            # Check if files were uploaded
            if 'files' not in request.files:
                return {
                    "error": "No files provided",
                    "message": "Please upload files with the 'files' field"
                }, 400

            files = request.files.getlist('files')

            if not files or all(file.filename == '' for file in files):
                return {
                    "error": "No valid files selected",
                    "message": "Please select files to upload"
                }, 400

            # Get optional parameters
            dpi = request.args.get('dpi', 300, type=int)

            job_ids: List[Dict[str, Any]] = []
            total_files = 0
            created_jobs = 0

            for file in files:
                if file.filename == '':
                    continue

                total_files += 1
                filename = secure_filename(file.filename)
                file_data = file.read()

                # Validate file size
                is_valid, status_code = self._validate_file_size(file_data)
                if not is_valid:
                    job_ids.append({
                        "filename": filename,
                        "success": False,
                        "error": f"File too large (max {current_app.config['MAX_CONTENT_LENGTH'] // (1024*1024)}MB)",
                        "type": "unknown"
                    })
                    continue

                # Determine file type and create job accordingly
                try:
                    if filename.lower().endswith(('.pdf',)):
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
                    elif filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.gif')):
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

            response = {
                "jobs": job_ids,
                "summary": {
                    "total_files": total_files,
                    "jobs_created": created_jobs,
                    "failed_files": total_files - created_jobs,
                    "success": created_jobs > 0
                },
                "message": "Batch jobs created successfully. Use GET /ocr/job/{job_id} to check status for each job."
            }

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
        Get the result of a completed async OCR job.

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
