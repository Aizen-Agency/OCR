"""
Resource Cleanup Utilities - Context managers and cleanup helpers
"""

import os
import logging
import gc
from contextlib import contextmanager
from typing import Optional
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


@contextmanager
def pdf_document_context(pdf_data: Optional[bytes] = None, pdf_path: Optional[str] = None):
    """
    Context manager for PyMuPDF document that ensures proper cleanup.

    Args:
        pdf_data: Raw PDF bytes (if opening from memory)
        pdf_path: Path to PDF file (if opening from disk)

    Yields:
        fitz.Document object

    Example:
        with pdf_document_context(pdf_data=bytes) as doc:
            # Use doc here
            pass
        # doc is automatically closed
    """
    doc = None
    try:
        if pdf_data is not None:
            doc = fitz.open(stream=pdf_data, filetype="pdf")
        elif pdf_path is not None:
            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            doc = fitz.open(pdf_path)
        else:
            raise ValueError("Either pdf_data or pdf_path must be provided")

        yield doc
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception as e:
                logger.warning(f"Error closing PDF document: {str(e)}")


def cleanup_temp_file(file_path: str) -> bool:
    """
    Safely remove a temporary file.

    Args:
        file_path: Path to file to remove

    Returns:
        True if file was removed, False otherwise
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Removed temp file: {file_path}")
            return True
        return False
    except Exception as e:
        logger.warning(f"Error removing temp file {file_path}: {str(e)}")
        return False


def force_memory_cleanup():
    """
    Force garbage collection to free memory.

    This should be called after processing large objects or batches.
    """
    try:
        gc.collect()
        logger.debug("Memory cleanup performed")
    except Exception as e:
        logger.warning(f"Memory cleanup failed: {str(e)}")

