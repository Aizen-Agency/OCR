"""
Encoding Utilities - Base64 and other encoding operations
"""

import base64
import hashlib
from typing import Union


def encode_base64(data: bytes) -> str:
    """
    Encode bytes to base64 string.

    Args:
        data: Raw bytes to encode

    Returns:
        Base64 encoded string
    """
    return base64.b64encode(data).decode('utf-8')


def decode_base64(encoded_data: str) -> bytes:
    """
    Decode base64 string to bytes.

    Args:
        encoded_data: Base64 encoded string

    Returns:
        Decoded bytes

    Raises:
        ValueError: If the input is not valid base64
    """
    try:
        return base64.b64decode(encoded_data)
    except Exception as e:
        raise ValueError(f"Invalid base64 data: {str(e)}") from e


def generate_file_hash(file_data: bytes) -> str:
    """
    Generate SHA256 hash for file data.
    
    This is a centralized utility to ensure consistent hashing across the codebase.

    Args:
        file_data: Raw file bytes

    Returns:
        SHA256 hash string
    """
    return hashlib.sha256(file_data).hexdigest()


def mask_redis_url(url: str) -> str:
    """
    Mask password in Redis URL for secure logging.
    
    Converts: redis://:password@host:port -> redis://:***@host:port

    Args:
        url: Redis URL with potential password

    Returns:
        Redis URL with masked password
    """
    if '@' in url:
        parts = url.split('@')
        if len(parts) == 2:
            auth_part = parts[0]
            if ':' in auth_part and auth_part.count(':') >= 2:
                # redis://:password -> redis://:***
                auth_parts = auth_part.rsplit(':', 1)
                return f"{auth_parts[0]}:***@{parts[1]}"
    return url

