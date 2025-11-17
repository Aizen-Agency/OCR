"""
Job Service - Handles async job status and result management
"""

import logging
from typing import Dict, Any, Optional
from celery.result import AsyncResult
from celery_app import celery_app
from tasks.ocr_tasks import process_image_task, process_pdf_task
from utils.encoding import encode_base64
from utils.validators import validate_job_id

logger = logging.getLogger(__name__)


class JobService:
    """
    Service class for managing async OCR jobs.
    """

    def __init__(self):
        self.celery_app = celery_app

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of an async job.

        Args:
            job_id: Celery task ID

        Returns:
            Dict with job status information
        """
        # Validate job ID format
        is_valid, error_msg = validate_job_id(job_id)
        if not is_valid:
            logger.warning(f"Invalid job ID format: {job_id}")
            return {
                "job_id": job_id,
                "status": "error",
                "error": error_msg or "Invalid job ID format"
            }

        try:
            task_result = AsyncResult(job_id, app=self.celery_app)

            status_info = {
                "job_id": job_id,
                "status": task_result.state.lower(),
                "ready": task_result.ready(),
                "successful": task_result.successful() if task_result.ready() else None,
                "failed": task_result.failed() if task_result.ready() else None,
            }

            # Add progress information if available
            if task_result.info:
                if isinstance(task_result.info, dict):
                    status_info.update(task_result.info)
                elif isinstance(task_result.info, str):
                    status_info["info"] = task_result.info

            # Add error information if task failed
            if task_result.failed():
                status_info["error"] = str(task_result.info) if task_result.info else "Unknown error"
                status_info["traceback"] = task_result.traceback if hasattr(task_result, 'traceback') else None

            return status_info

        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {str(e)}")
            return {
                "job_id": job_id,
                "status": "error",
                "error": str(e)
            }

    def get_job_result(self, job_id: str) -> Dict[str, Any]:
        """
        Get the result of a completed job.

        Args:
            job_id: Celery task ID

        Returns:
            Dict with job result or error information
        """
        # Validate job ID format
        is_valid, error_msg = validate_job_id(job_id)
        if not is_valid:
            logger.warning(f"Invalid job ID format: {job_id}")
            return {
                "job_id": job_id,
                "status": "error",
                "error": error_msg or "Invalid job ID format"
            }

        try:
            task_result = AsyncResult(job_id, app=self.celery_app)

            if not task_result.ready():
                return {
                    "job_id": job_id,
                    "status": task_result.state.lower(),
                    "ready": False,
                    "message": "Job is still processing. Please check status again later."
                }

            if task_result.successful():
                result = task_result.result
                if isinstance(result, dict):
                    result["job_id"] = job_id
                    result["status"] = "completed"
                    return result
                else:
                    return {
                        "job_id": job_id,
                        "status": "completed",
                        "result": result
                    }
            else:
                # Task failed
                error_info = {
                    "job_id": job_id,
                    "status": "failed",
                    "error": str(task_result.info) if task_result.info else "Unknown error"
                }
                if hasattr(task_result, 'traceback') and task_result.traceback:
                    error_info["traceback"] = task_result.traceback
                return error_info

        except Exception as e:
            logger.error(f"Error getting job result for {job_id}: {str(e)}")
            return {
                "job_id": job_id,
                "status": "error",
                "error": str(e)
            }

    def create_image_job(self, image_data: bytes, filename: str) -> str:
        """
        Create an async job for image OCR processing.

        Args:
            image_data: Raw image bytes
            filename: Filename for logging

        Returns:
            Job ID (Celery task ID)
        """
        try:
            image_data_b64 = encode_base64(image_data)
            task = process_image_task.delay(image_data_b64, filename)
            logger.info(f"Created image OCR job: {task.id} for file: {filename}")
            return task.id

        except Exception as e:
            logger.error(f"Error creating image job: {str(e)}")
            raise RuntimeError(f"Failed to create image OCR job: {str(e)}")

    def create_pdf_job(self, pdf_data: bytes, filename: str, dpi: int = 300) -> str:
        """
        Create an async job for PDF OCR processing.

        Args:
            pdf_data: Raw PDF bytes
            filename: Filename for logging
            dpi: DPI for PDF conversion

        Returns:
            Job ID (Celery task ID)
        """
        try:
            pdf_data_b64 = encode_base64(pdf_data)
            task = process_pdf_task.delay(pdf_data_b64, filename, dpi)
            logger.info(f"Created PDF OCR job: {task.id} for file: {filename} at {dpi} DPI")
            return task.id

        except Exception as e:
            logger.error(f"Error creating PDF job: {str(e)}")
            raise RuntimeError(f"Failed to create PDF OCR job: {str(e)}")

    def create_hybrid_pdf_job(self, pdf_data: bytes, filename: str, options: dict = None) -> str:
        """
        Create an async job for hybrid PDF text extraction.

        Args:
            pdf_data: Raw PDF bytes
            filename: Filename for logging
            options: Processing options (dpi, chunk_size, max_pages, etc.)

        Returns:
            Job ID (Celery task ID for aggregation task)
        """
        try:
            from services.pdf_hybrid_service import PDFHybridService
            
            pdf_hybrid_service = PDFHybridService()
            job_id = pdf_hybrid_service.create_hybrid_job(
                pdf_data=pdf_data,
                filename=filename,
                options=options or {}
            )
            logger.info(f"Created hybrid PDF job: {job_id} for file: {filename}")
            return job_id

        except Exception as e:
            logger.error(f"Error creating hybrid PDF job: {str(e)}")
            raise RuntimeError(f"Failed to create hybrid PDF job: {str(e)}")
