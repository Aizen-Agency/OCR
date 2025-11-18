"""
File Upload Helpers - Centralized file upload validation and processing utilities

Provides reusable functions for file upload validation, reading, and size validation
to eliminate code duplication across controllers.
"""

import logging
from typing import Tuple, Optional
from flask import request
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

logger = logging.getLogger(__name__)


def validate_file_upload(file_field: str = 'file') -> Tuple[Optional[FileStorage], Optional[str], int]:
    """
    Validate file upload from request.
    
    Args:
        file_field: Name of the file field in the request (default: 'file')
    
    Returns:
        tuple: (file_object, filename, status_code)
               Returns (None, None, status_code) on error
               Returns (file, filename, 200) on success
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


def read_file_data(file: FileStorage) -> bytes:
    """
    Read file data from FileStorage object.
    
    Args:
        file: FileStorage object from Flask request
    
    Returns:
        File data as bytes
    """
    file.seek(0)  # Ensure we're at the beginning
    file_data = file.read()
    file.seek(0)  # Reset for potential reuse
    return file_data


def validate_file_size(file_data: bytes, max_size: int) -> Tuple[bool, int]:
    """
    Validate file size against maximum limit.
    
    Args:
        file_data: File data as bytes
        max_size: Maximum allowed size in bytes
    
    Returns:
        tuple: (is_valid, error_status_code)
               (True, 200) if valid
               (False, 413) if file too large
    """
    if len(file_data) > max_size:
        return False, 413
    return True, 200


def get_file_extension(filename: str) -> str:
    """
    Get file extension from filename (lowercase).
    
    Args:
        filename: Filename string
    
    Returns:
        File extension without dot (e.g., 'pdf', 'jpg')
    """
    if '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[1].lower()


def is_image_file(filename: str) -> bool:
    """
    Check if file is an image based on extension.
    
    Args:
        filename: Filename string
    
    Returns:
        True if file is an image, False otherwise
    """
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp', '.gif'}
    ext = get_file_extension(filename)
    return f'.{ext}' in image_extensions


def is_pdf_file(filename: str) -> bool:
    """
    Check if file is a PDF based on extension.
    
    Args:
        filename: Filename string
    
    Returns:
        True if file is a PDF, False otherwise
    """
    return get_file_extension(filename) == 'pdf'


def validate_and_read_file(file_field: str = 'file', max_size: Optional[int] = None) -> Tuple[Optional[bytes], Optional[str], Optional[int], Optional[str]]:
    """
    Combined validation and reading of file upload.
    
    Args:
        file_field: Name of the file field in the request
        max_size: Maximum file size in bytes (if None, uses Flask's MAX_CONTENT_LENGTH)
    
    Returns:
        tuple: (file_data, filename, status_code, error_message)
               On success: (bytes, filename, 200, None)
               On error: (None, None, status_code, error_message)
    """
    # Validate file upload
    file, filename, status_code = validate_file_upload(file_field)
    if status_code != 200:
        if status_code == 400:
            return None, None, 400, f"Please upload a file with the '{file_field}' field"
        return None, None, status_code, "File validation failed"
    
    # Read file data
    try:
        file_data = read_file_data(file)
    except Exception as e:
        logger.error(f"Error reading file data: {str(e)}")
        return None, None, 500, f"Error reading file: {str(e)}"
    
    # Validate file size if max_size provided
    if max_size is not None:
        is_valid, size_status_code = validate_file_size(file_data, max_size)
        if not is_valid:
            max_size_mb = max_size // (1024 * 1024)
            return None, None, size_status_code, f"File size exceeds maximum limit of {max_size_mb}MB"
    
    return file_data, filename, 200, None

