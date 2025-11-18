"""
Response Helpers - Centralized response formatting utilities

Provides standardized response creation functions to eliminate code duplication
and ensure consistent API responses across all controllers.
"""

from typing import Dict, Any, List, Tuple
from utils.constants import (
    JOB_CREATED_MESSAGE,
    HYBRID_PDF_JOB_CREATED_MESSAGE
)


def create_error_response(error: str, message: str, status_code: int = 400) -> Tuple[Dict[str, Any], int]:
    """
    Create standardized error response.
    
    Args:
        error: Error type/code
        message: Error message
        status_code: HTTP status code
    
    Returns:
        tuple: (error_response_dict, status_code)
    """
    return {
        "error": error,
        "message": message
    }, status_code


def create_job_response(
    job_id: str,
    filename: str,
    file_size: int,
    status: str = "processing",
    message: str = JOB_CREATED_MESSAGE,
    **kwargs
) -> Dict[str, Any]:
    """
    Create standardized job creation response.
    
    Args:
        job_id: Created job ID
        filename: Filename
        file_size: File size in bytes
        status: Job status (default: "processing")
        message: Success message
        **kwargs: Additional fields to include in response
    
    Returns:
        Job creation response dictionary
    """
    response = {
        "job_id": job_id,
        "status": status,
        "filename": filename,
        "file_size": file_size,
        "message": message
    }
    response.update(kwargs)
    return response


def create_hybrid_pdf_job_response(
    job_id: str,
    filename: str,
    file_size: int,
    **kwargs
) -> Dict[str, Any]:
    """
    Create standardized hybrid PDF job creation response.
    
    Args:
        job_id: Created job ID
        filename: Filename
        file_size: File size in bytes
        **kwargs: Additional fields to include
    
    Returns:
        Hybrid PDF job creation response dictionary
    """
    return create_job_response(
        job_id=job_id,
        filename=filename,
        file_size=file_size,
        status="queued",
        message=HYBRID_PDF_JOB_CREATED_MESSAGE,
        strategy="hybrid_pdf",
        **kwargs
    )


def map_celery_state_to_http_status(celery_state: str) -> int:
    """
    Map Celery task state to appropriate HTTP status code.
    
    Args:
        celery_state: Celery task state (pending, started, processing, success, completed, failure, failed, etc.)
    
    Returns:
        HTTP status code
    """
    state_lower = celery_state.lower()
    
    if state_lower in ('pending', 'started', 'processing'):
        return 202  # Accepted - still processing
    elif state_lower in ('success', 'completed'):
        return 200  # OK - completed successfully
    elif state_lower in ('failure', 'failed'):
        return 500  # Internal Server Error - task failed
    else:
        return 200  # Default - return OK for unknown states


def format_batch_response(
    job_ids: List[Dict[str, Any]],
    summary: Dict[str, Any],
    message: str = None
) -> Dict[str, Any]:
    """
    Format batch processing response.
    
    Args:
        job_ids: List of job result dictionaries
        summary: Summary dictionary with total_files, jobs_created, failed_files, success
        message: Optional custom message
    
    Returns:
        Formatted batch response dictionary
    """
    if message is None:
        message = f"Batch jobs created successfully. Use GET /ocr/job/{{job_id}} to check status for each job."
    
    return {
        "jobs": job_ids,
        "summary": summary,
        "message": message
    }


def create_job_status_response(
    job_status: Dict[str, Any],
    include_progress: bool = False,
    progress_data: Dict[str, Any] = None
) -> Tuple[Dict[str, Any], int]:
    """
    Create standardized job status response with appropriate HTTP status code.
    
    Args:
        job_status: Job status dictionary from JobService
        include_progress: Whether to include progress information
        progress_data: Optional progress data to include
    
    Returns:
        tuple: (response_dict, http_status_code)
    """
    response = job_status.copy()
    
    # Add progress if requested
    if include_progress and progress_data:
        response["progress"] = progress_data
    
    # Determine HTTP status code
    status = job_status.get('status', 'unknown')
    
    if status == 'error':
        return response, 500
    
    http_status = map_celery_state_to_http_status(status)
    
    return response, http_status


def create_job_result_response(
    job_result: Dict[str, Any],
    include_progress: bool = False,
    progress_data: Dict[str, Any] = None
) -> Tuple[Dict[str, Any], int]:
    """
    Create standardized job result response with appropriate HTTP status code.
    
    Args:
        job_result: Job result dictionary from JobService
        include_progress: Whether to include progress information
        progress_data: Optional progress data to include
    
    Returns:
        tuple: (response_dict, http_status_code)
    """
    response = job_result.copy()
    
    # Add progress if requested
    if include_progress and progress_data:
        response["progress"] = progress_data
    
    # Determine HTTP status code
    if response.get('status') == 'error':
        return response, 500
    
    if not response.get('ready', False):
        return response, 202  # Still processing
    
    if response.get('status') == 'failed':
        return response, 500
    
    return response, 200  # Completed successfully

