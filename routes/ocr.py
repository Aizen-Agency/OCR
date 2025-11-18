"""
OCR Blueprint - Routes for OCR operations
"""

from flask import Blueprint, jsonify, current_app
from controllers.ocr_controller import OCRController

# Create blueprint
ocr_bp = Blueprint('ocr', __name__, url_prefix='/ocr')


def get_ocr_controller() -> OCRController:
    """Get OCR controller instance (uses service manager internally)."""
    return OCRController()


@ocr_bp.route('/image', methods=['POST'])
def ocr_image():
    """
    Create an async job for OCR on an uploaded image file.

    Expected: multipart/form-data with 'file' field containing image
    Returns: JSON with job_id and status
    """
    controller = get_ocr_controller()
    result, status_code = controller.process_image()
    return jsonify(result), status_code


@ocr_bp.route('/pdf', methods=['POST'])
def ocr_pdf():
    """
    Create an async job for OCR on an uploaded PDF file.

    Expected: multipart/form-data with 'file' field containing PDF
    Optional query params: dpi (default: 300)
    Returns: JSON with job_id and status
    """
    controller = get_ocr_controller()
    result, status_code = controller.process_pdf()
    return jsonify(result), status_code


@ocr_bp.route('/batch', methods=['POST'])
def ocr_batch():
    """
    Create async jobs for OCR on multiple uploaded files (images and PDFs).

    Expected: multipart/form-data with multiple 'files' fields
    Returns: JSON with job_ids and status for each file
    """
    controller = get_ocr_controller()
    result, status_code = controller.process_batch()
    return jsonify(result), status_code


@ocr_bp.route('/job/<job_id>', methods=['GET'])
def get_job_status(job_id: str):
    """
    Get the status of an async OCR job.

    Args:
        job_id: Celery task ID

    Returns: JSON with job status information
    """
    controller = get_ocr_controller()
    result, status_code = controller.get_job_status(job_id)
    return jsonify(result), status_code


@ocr_bp.route('/job/<job_id>/result', methods=['GET'])
def get_job_result(job_id: str):
    """
    Get the result of a completed async OCR job.

    Args:
        job_id: Celery task ID

    Returns: JSON with job result (if completed) or status (if still processing)
    """
    controller = get_ocr_controller()
    result, status_code = controller.get_job_result(job_id)
    return jsonify(result), status_code
