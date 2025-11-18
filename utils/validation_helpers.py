"""
Validation Helpers - Centralized validation utilities

Consolidates all validation logic from controllers to eliminate duplication
and ensure consistent validation across the application.
"""

from typing import Dict, Any, Tuple, Optional, List
from flask import request, current_app
from utils.validators import validate_dpi as base_validate_dpi
from utils.constants import MIN_DPI, MAX_DPI, DEFAULT_DPI


def validate_dpi_with_error(
    dpi: Any,
    min_dpi: int = MIN_DPI,
    max_dpi: int = MAX_DPI,
    default: int = DEFAULT_DPI
) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Validate DPI value with error message generation.
    
    Args:
        dpi: DPI value to validate (can be int, string, or None)
        min_dpi: Minimum allowed DPI
        max_dpi: Maximum allowed DPI
        default: Default DPI if dpi is None or invalid
    
    Returns:
        tuple: (is_valid, validated_dpi, error_message)
               On success: (True, validated_dpi, None)
               On error: (False, default, error_message)
    """
    # Handle None or empty string
    if dpi is None or dpi == '':
        return True, default, None
    
    # Try to convert to int
    try:
        dpi_int = int(dpi)
    except (ValueError, TypeError):
        return False, default, f"DPI must be an integer between {min_dpi} and {max_dpi}"
    
    # Validate range
    is_valid, error_msg = base_validate_dpi(dpi_int, min_dpi, max_dpi)
    if not is_valid:
        return False, default, error_msg or f"DPI must be between {min_dpi} and {max_dpi}"
    
    return True, dpi_int, None


def validate_request_params(
    params: Dict[str, Any],
    schema: Dict[str, Dict[str, Any]]
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Generic request parameter validation.
    
    Args:
        params: Dictionary of parameters to validate
        schema: Validation schema with format:
                {
                    'param_name': {
                        'type': type or tuple of types,
                        'required': bool,
                        'default': default_value,
                        'min': min_value (for numbers),
                        'max': max_value (for numbers),
                        'validator': callable (optional custom validator)
                    }
                }
    
    Returns:
        tuple: (is_valid, error_message, validated_params)
               On success: (True, None, validated_params_dict)
               On error: (False, error_message, {})
    """
    validated = {}
    
    for param_name, param_schema in schema.items():
        param_value = params.get(param_name)
        
        # Check required
        if param_schema.get('required', False) and param_value is None:
            return False, f"Required parameter '{param_name}' is missing", {}
        
        # Use default if not provided
        if param_value is None and 'default' in param_schema:
            param_value = param_schema['default']
        
        # Skip validation if None and not required
        if param_value is None:
            continue
        
        # Type validation
        expected_type = param_schema.get('type')
        if expected_type:
            if not isinstance(param_value, expected_type):
                # Try type conversion for common types
                try:
                    if expected_type == int:
                        param_value = int(param_value)
                    elif expected_type == float:
                        param_value = float(param_value)
                    elif expected_type == str:
                        param_value = str(param_value)
                    else:
                        return False, f"Parameter '{param_name}' must be of type {expected_type.__name__}", {}
                except (ValueError, TypeError):
                    return False, f"Parameter '{param_name}' must be of type {expected_type.__name__}", {}
        
        # Range validation for numbers
        if isinstance(param_value, (int, float)):
            if 'min' in param_schema and param_value < param_schema['min']:
                return False, f"Parameter '{param_name}' must be >= {param_schema['min']}", {}
            if 'max' in param_schema and param_value > param_schema['max']:
                return False, f"Parameter '{param_name}' must be <= {param_schema['max']}", {}
        
        # Custom validator
        if 'validator' in param_schema:
            is_valid, error_msg = param_schema['validator'](param_value)
            if not is_valid:
                return False, error_msg or f"Parameter '{param_name}' validation failed", {}
        
        validated[param_name] = param_value
    
    return True, None, validated


def extract_int_param(
    param_name: str,
    default: int,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None
) -> Tuple[int, Optional[str]]:
    """
    Extract and validate integer parameter from request (form or query).
    
    Args:
        param_name: Parameter name
        default: Default value if not provided
        min_value: Minimum allowed value
        max_value: Maximum allowed value
    
    Returns:
        tuple: (validated_value, error_message)
               On success: (value, None)
               On error: (default, error_message)
    """
    # Try form data first, then query params
    param_value = request.form.get(param_name) or request.args.get(param_name, default)
    
    try:
        value = int(param_value)
    except (ValueError, TypeError):
        return default, f"Parameter '{param_name}' must be an integer"
    
    if min_value is not None and value < min_value:
        return default, f"Parameter '{param_name}' must be >= {min_value}"
    
    if max_value is not None and value > max_value:
        return default, f"Parameter '{param_name}' must be <= {max_value}"
    
    return value, None


def validate_file_type(filename: str, allowed_types: List[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate file type based on extension.
    
    Args:
        filename: Filename to validate
        allowed_types: List of allowed file extensions (e.g., ['pdf', 'jpg', 'png'])
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not filename:
        return False, "Filename is required"
    
    # Get extension
    if '.' not in filename:
        return False, f"File must have an extension. Allowed types: {', '.join(allowed_types)}"
    
    ext = filename.rsplit('.', 1)[1].lower()
    
    if ext not in allowed_types:
        return False, f"Unsupported file type. Allowed types: {', '.join(allowed_types)}"
    
    return True, None


def validate_batch_files(files: List) -> Tuple[bool, Optional[str], int]:
    """
    Validate batch file upload.
    
    Args:
        files: List of file objects from request
    
    Returns:
        tuple: (is_valid, error_message, status_code)
    """
    if not files:
        return False, "No files provided", 400
    
    if all(file.filename == '' for file in files):
        return False, "No valid files selected", 400
    
    return True, None, 200

