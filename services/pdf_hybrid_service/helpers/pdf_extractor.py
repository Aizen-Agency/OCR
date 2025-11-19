"""
PDF Extractor - Main extraction logic for PDF pages based on classification
"""

import logging
from typing import Dict, Any
import fitz  # PyMuPDF

from services.ocr_service.ocr_service import OCRService
from .block_extractor import extract_text_blocks
from .text_extractor import extract_text_from_page

logger = logging.getLogger(__name__)


def extract_page_content(
    page: fitz.Page,
    page_index: int,
    classification: str,
    dpi: int,
    ocr_service: OCRService,
    filename: str = ""
) -> Dict[str, Any]:
    """
    Extract content from a PDF page based on its classification.

    This is the main extraction function that routes to text extraction
    or OCR based on page classification.

    Args:
        page: PyMuPDF Page object
        page_index: 0-indexed page number
        classification: "text" or "image"
        dpi: DPI for rendering (used for OCR)
        ocr_service: OCRService instance
        filename: Optional filename for logging

    Returns:
        Dictionary with page content and metadata
    """
    try:
        if classification == "text":
            # Extract text directly from PDF
            text = extract_text_from_page(page, sort=True)
            
            # Get structured blocks with bounding boxes
            blocks = extract_text_blocks(page)

            return {
                "page_index": page_index,
                "classification": "text",
                "source": "pdf_text",
                "text": text,
                "blocks": blocks
            }

        else:  # classification == "image"
            # Render page to image
            pix = None
            try:
                pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB)
                png_bytes = pix.tobytes("png")
                
                # Note: Don't delete pix here - let finally block handle cleanup
                # This prevents "referenced before assignment" errors

                # Perform OCR
                ocr_result = ocr_service.process_image(
                    png_bytes,
                    f"{filename}_page_{page_index + 1}"
                )
                
                if ocr_result.get("success", False):
                    return {
                        "page_index": page_index,
                        "classification": "image",
                        "source": "ocr",
                        "text": ocr_result.get("text", ""),
                        "lines": ocr_result.get("lines", [])
                    }
                else:
                    # OCR failed, return empty result
                    logger.warning(
                        f"OCR failed for page {page_index}: "
                        f"{ocr_result.get('error', 'Unknown error')}"
                    )
                    return {
                        "page_index": page_index,
                        "classification": "image",
                        "source": "ocr",
                        "text": "",
                        "lines": [],
                        "error": ocr_result.get("error", "OCR processing failed")
                    }
            finally:
                # Ensure pixmap is freed even if OCR fails or exception occurs
                if pix is not None:
                    try:
                        pix = None
                        del pix
                    except Exception:
                        pass  # Ignore errors during cleanup

    except Exception as e:
        logger.error(f"Error extracting content from page {page_index}: {str(e)}")
        return {
            "page_index": page_index,
            "classification": classification,
            "source": "error",
            "text": "",
            "error": str(e)
        }

