"""
Text Extractor - Extracts plain text from PDF pages
"""

import logging
from typing import Optional
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def extract_text_from_page(page: fitz.Page, sort: bool = True) -> str:
    """
    Extract plain text from a PDF page.

    Args:
        page: PyMuPDF Page object
        sort: Whether to sort text blocks (default: True)

    Returns:
        Extracted text as string
    """
    try:
        text = page.get_text("text", sort=sort).strip()
        return text
    except Exception as e:
        logger.warning(f"Error extracting text from page: {str(e)}")
        return ""

