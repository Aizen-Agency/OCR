"""
Block Extractor - Extracts structured text blocks with bounding boxes from PDF pages
"""

import logging
from typing import List, Dict, Any
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def extract_text_blocks(page: fitz.Page) -> List[Dict[str, Any]]:
    """
    Extract structured text blocks with bounding boxes from a PDF page.

    Args:
        page: PyMuPDF Page object

    Returns:
        List of block dictionaries with type, text, and bbox
    """
    blocks = []
    try:
        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # Text block (type 0 = text, type 1 = image)
                block_text = ""
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        block_text += span.get("text", "")
                
                if block_text.strip():
                    bbox = block.get("bbox", [0, 0, 0, 0])
                    blocks.append({
                        "type": "text",
                        "text": block_text.strip(),
                        "bbox": bbox
                    })
    except Exception as e:
        logger.warning(f"Error extracting blocks from page: {str(e)}")
        # Return empty list on error - extraction can continue without blocks
    
    return blocks

