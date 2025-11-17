"""
Page Classifier - Classifies PDF pages as text-based or image-based
"""

import logging
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def classify_page(
    page: fitz.Page,
    text_threshold: int = 30,
    image_area_threshold: float = 0.0
) -> str:
    """
    Classify a PDF page as text-based or image-based.

    Simplified classification logic:
    - text: No images AND has extractable text (>= text_threshold chars)
    - image: Has images OR no extractable text (< text_threshold chars)

    Args:
        page: PyMuPDF Page object
        text_threshold: Minimum number of characters to consider as text page (default: 30)
        image_area_threshold: Minimum image area ratio to trigger OCR (default: 0.0 = any image)

    Returns:
        "text" or "image"
    """
    try:
        # Extract text from page
        raw_text = page.get_text("text").strip()
        text_len = len(raw_text)

        # Get image information
        images = page.get_images()
        has_images = len(images) > 0

        # For simplified classification: if any image exists, use OCR
        # (We can enhance this later to calculate image area ratio if needed)
        # For now, image_area_threshold of 0.0 means any image triggers OCR
        
        # Classification logic:
        # - If has images OR no sufficient text -> "image"
        # - If no images AND has sufficient text -> "text"
        if has_images or text_len < text_threshold:
            logger.debug(
                f"Page classified as 'image': text_len={text_len}, "
                f"has_images={has_images}, image_count={len(images)}"
            )
            return "image"
        else:
            logger.debug(
                f"Page classified as 'text': text_len={text_len}, "
                f"has_images={has_images}, image_count={len(images)}"
            )
            return "text"

    except Exception as e:
        logger.error(f"Error classifying page: {str(e)}")
        # On error, default to "image" to be safe (will use OCR)
        return "image"

