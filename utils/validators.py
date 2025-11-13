"""
Validation Utilities - Input validation helpers
"""

import re
from typing import Tuple, Optional


# Celery task ID format: UUID-like string (e.g., "abc123-def456-ghi789")
CELERY_TASK_ID_PATTERN = re.compile(r'^[a-f0-9-]{36}$')


def validate_job_id(job_id: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Celery job ID format.

    Args:
        job_id: Job ID to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not job_id:
        return False, "Job ID cannot be empty"

    if not isinstance(job_id, str):
        return False, "Job ID must be a string"

    # Celery task IDs are typically UUID-like strings
    # Allow alphanumeric with hyphens, length between 32-40 chars
    if len(job_id) < 32 or len(job_id) > 40:
        return False, "Invalid job ID format: length must be between 32-40 characters"

    if not re.match(r'^[a-f0-9-]+$', job_id):
        return False, "Invalid job ID format: must contain only lowercase hex characters and hyphens"

    return True, None


def validate_dpi(dpi: int, min_dpi: int = 72, max_dpi: int = 600) -> Tuple[bool, Optional[str]]:
    """
    Validate DPI value.

    Args:
        dpi: DPI value to validate
        min_dpi: Minimum allowed DPI
        max_dpi: Maximum allowed DPI

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(dpi, int):
        return False, "DPI must be an integer"

    if dpi < min_dpi or dpi > max_dpi:
        return False, f"DPI must be between {min_dpi} and {max_dpi}"

    return True, None

