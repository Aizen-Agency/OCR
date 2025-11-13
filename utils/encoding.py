"""
Encoding Utilities - Base64 and other encoding operations
"""

import base64
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

