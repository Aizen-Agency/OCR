"""
PDF Hybrid Blueprint - Routes for hybrid PDF text extraction operations
"""

from flask import Blueprint, jsonify, current_app, request
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
    import logging
    import sys
    logger = logging.getLogger(__name__)
    
    # Force flush to ensure logs appear immediately
    print("=" * 80, file=sys.stderr, flush=True)
    print("HYBRID EXTRACT ENDPOINT CALLED - REQUEST RECEIVED", file=sys.stderr, flush=True)
    print("=" * 80, file=sys.stderr, flush=True)
    
    try:
        print("STEP 1: Accessing request.method", file=sys.stderr, flush=True)
        method = request.method
        print(f"STEP 1 DONE: method={method}", file=sys.stderr, flush=True)
        
        print("STEP 2: Accessing request.path", file=sys.stderr, flush=True)
        path = request.path
        print(f"STEP 2 DONE: path={path}", file=sys.stderr, flush=True)
        
        print("STEP 3: Getting controller instance", file=sys.stderr, flush=True)
        controller = get_pdf_hybrid_controller()
        print("STEP 3 DONE: Controller obtained", file=sys.stderr, flush=True)
        
        print("STEP 4: Calling process_hybrid_pdf", file=sys.stderr, flush=True)
        result, status_code = controller.process_hybrid_pdf()
        print(f"STEP 4 DONE: process_hybrid_pdf completed with status {status_code}", file=sys.stderr, flush=True)
        
        print("STEP 5: Returning response", file=sys.stderr, flush=True)
        return jsonify(result), status_code
    except Exception as e:
        print(f"EXCEPTION IN HYBRID EXTRACT: {str(e)}", file=sys.stderr, flush=True)
        print(f"Exception type: {type(e).__name__}", file=sys.stderr, flush=True)
        import traceback
        print(traceback.format_exc(), file=sys.stderr, flush=True)
        logger.error(f"Exception in hybrid_extract route: {str(e)}", exc_info=True)
        raise


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

