"""
PDF Hybrid Blueprint - Routes for hybrid PDF text extraction operations
"""

from flask import Blueprint, jsonify, current_app
from controllers.pdf_hybrid_controller import PDFHybridController

# Create blueprint
pdf_hybrid_bp = Blueprint('pdf_hybrid', __name__, url_prefix='/pdf')


def get_pdf_hybrid_controller() -> PDFHybridController:
    """Get PDF hybrid controller instance (uses service manager internally)."""
    return PDFHybridController()


# Note: Rate limiting for PDF hybrid endpoint is handled by the main rate limiter middleware
# The PDF_HYBRID_RATE_LIMIT_PER_MINUTE config allows for separate limits if needed
# Currently uses the same rate limiting as other endpoints (10 req/min default)


@pdf_hybrid_bp.route('/hybrid-extract', methods=['POST'])
def hybrid_extract():
    """
    Create an async job for hybrid PDF text extraction.

    Expected: multipart/form-data with 'file' field containing PDF
    Optional form/query params:
        - dpi (int, default: 300)
        - chunk_size (int, default: 50)
        - max_pages (int, default: 5000)
    Returns: JSON with job_id and status
    """
    controller = get_pdf_hybrid_controller()
    result, status_code = controller.process_hybrid_pdf()
    return jsonify(result), status_code


@pdf_hybrid_bp.route('/job/<job_id>', methods=['GET'])
def get_job_status(job_id: str):
    """
    Get the status of an async hybrid PDF job.

    Args:
        job_id: Celery task ID

    Returns: JSON with job status information
    """
    controller = get_pdf_hybrid_controller()
    result, status_code = controller.get_job_status(job_id)
    return jsonify(result), status_code


@pdf_hybrid_bp.route('/job/<job_id>/result', methods=['GET'])
def get_job_result(job_id: str):
    """
    Get the result of a completed async hybrid PDF job.

    Args:
        job_id: Celery task ID

    Returns: JSON with job result (if completed) or status (if still processing)
    """
    controller = get_pdf_hybrid_controller()
    result, status_code = controller.get_job_result(job_id)
    return jsonify(result), status_code

