"""
Validation Utilities - File, path, and resource validation helpers
"""

import os
import logging
import shutil
from pathlib import Path
from typing import Tuple, Optional

from utils.exceptions import DiskSpaceError, PDFValidationError

logger = logging.getLogger(__name__)


def validate_file_path(file_path: str, must_exist: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate a file path.

    Args:
        file_path: Path to validate
        must_exist: Whether the file must exist

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        path = Path(file_path)
        
        # Check for path traversal attempts
        resolved = path.resolve()
        if str(resolved) != str(path.resolve()):
            return False, "Invalid file path: potential path traversal detected"
        
        # Check if file exists if required
        if must_exist and not path.exists():
            return False, f"File does not exist: {file_path}"
        
        # Check if it's a file (not a directory)
        if path.exists() and not path.is_file():
            return False, f"Path is not a file: {file_path}"
        
        return True, None
    except Exception as e:
        return False, f"Invalid file path: {str(e)}"


def check_disk_space(file_path: str, required_bytes: int, min_free_bytes: int = 100 * 1024 * 1024) -> Tuple[bool, Optional[str]]:
    """
    Check if there's enough disk space for a file operation.

    Args:
        file_path: Path where file will be written
        required_bytes: Bytes required for the operation
        min_free_bytes: Minimum free bytes to maintain (default: 100MB)

    Returns:
        Tuple of (has_space, error_message)
    """
    try:
        # Get disk usage for the directory containing the file
        dir_path = os.path.dirname(file_path) or os.getcwd()
        stat = shutil.disk_usage(dir_path)
        
        free_bytes = stat.free
        total_needed = required_bytes + min_free_bytes
        
        if free_bytes < total_needed:
            free_mb = free_bytes / (1024 * 1024)
            needed_mb = total_needed / (1024 * 1024)
            return False, (
                f"Insufficient disk space: {free_mb:.1f}MB free, "
                f"{needed_mb:.1f}MB needed (including {min_free_bytes / (1024 * 1024):.1f}MB buffer)"
            )
        
        return True, None
    except Exception as e:
        logger.warning(f"Error checking disk space: {str(e)}")
        # Don't fail on disk space check errors, but log them
        return True, None


def validate_pdf_file_size(pdf_data: bytes, max_size: int) -> Tuple[bool, Optional[str]]:
    """
    Validate PDF file size.

    Args:
        pdf_data: PDF file bytes
        max_size: Maximum allowed size in bytes

    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(pdf_data) > max_size:
        size_mb = len(pdf_data) / (1024 * 1024)
        max_mb = max_size / (1024 * 1024)
        return False, f"PDF file size ({size_mb:.1f}MB) exceeds maximum ({max_mb:.1f}MB)"
    
    if len(pdf_data) == 0:
        return False, "PDF file is empty"
    
    return True, None

