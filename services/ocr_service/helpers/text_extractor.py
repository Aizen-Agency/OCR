"""
Text Extractor Helper - Processes OCR results and extracts text with confidence scores
"""

import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class TextExtractor:
    """
    Helper class for extracting and processing text from PaddleOCR results.
    """

    # Minimum confidence threshold for text extraction
    DEFAULT_MIN_CONFIDENCE = 0.0

    def extract_from_ocr_result(self, ocr_result: List, min_confidence: float = DEFAULT_MIN_CONFIDENCE) -> Tuple[List[Dict[str, Any]], str]:
        """
        Extract text and confidence scores from PaddleOCR result.

        Args:
            ocr_result: Raw OCR result from PaddleOCR
            min_confidence: Minimum confidence threshold (0.0 to 1.0)

        Returns:
            Tuple of (lines_list, full_text)
            lines_list: List of dicts with text, confidence, and bbox
            full_text: Concatenated text from all lines
        """
        # Debug logging to understand PaddleOCR 3.x output format
        logger.debug(f"OCR result type: {type(ocr_result)}")
        logger.debug(f"OCR result length: {len(ocr_result) if ocr_result else 0}")
        if ocr_result and len(ocr_result) > 0:
            logger.debug(f"OCR result[0] type: {type(ocr_result[0])}")
            logger.debug(f"OCR result[0] length: {len(ocr_result[0]) if ocr_result[0] else 0}")
            if ocr_result[0] and len(ocr_result[0]) > 0:
                logger.debug(f"First line sample: {ocr_result[0][0]}")
                logger.debug(f"First line type: {type(ocr_result[0][0])}")
        
        if not ocr_result or not ocr_result[0]:
            return [], ""

        lines = []
        text_parts = []

        try:
            for line in ocr_result[0]:
                try:
                    if len(line) >= 2:
                        bbox = line[0]
                        
                        # Handle different PaddleOCR 3.x output formats
                        if isinstance(line[1], (list, tuple)) and len(line[1]) == 2:
                            # Standard format: (text, confidence)
                            text, confidence = line[1]
                        elif isinstance(line[1], (list, tuple)) and len(line[1]) == 1:
                            # Single value format: just text
                            text = line[1][0] if line[1] else ""
                            confidence = 1.0  # Default confidence
                        elif isinstance(line[1], str):
                            # Direct string format
                            text = line[1]
                            confidence = 1.0  # Default confidence
                        else:
                            logger.warning(f"Unexpected line format: {line}")
                            continue

                        # Filter by confidence if specified
                        if confidence < min_confidence:
                            continue

                        line_data = {
                            "text": text,
                            "confidence": float(confidence),
                            "bbox": bbox  # Bounding box coordinates
                        }
                        lines.append(line_data)

                        if text.strip():
                            text_parts.append(text)
                            
                except (IndexError, TypeError, ValueError) as e:
                    logger.warning(f"Error parsing OCR line: {str(e)}, line data: {line}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing OCR result structure: {str(e)}")
            return [], ""

        # Join text parts with newlines
        full_text = "\n".join(text_parts)

        return lines, full_text

    def filter_by_confidence(self, lines: List[Dict[str, Any]], min_confidence: float) -> List[Dict[str, Any]]:
        """
        Filter OCR lines by minimum confidence score.

        Args:
            lines: List of line dictionaries from extract_from_ocr_result
            min_confidence: Minimum confidence threshold

        Returns:
            Filtered list of lines
        """
        return [line for line in lines if line.get('confidence', 0) >= min_confidence]

    def get_text_statistics(self, lines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate statistics about the extracted text.

        Args:
            lines: List of line dictionaries

        Returns:
            Dict with text statistics
        """
        if not lines:
            return {
                "total_lines": 0,
                "total_characters": 0,
                "average_confidence": 0.0,
                "min_confidence": 0.0,
                "max_confidence": 0.0,
                "low_confidence_lines": 0
            }

        confidences = [line.get('confidence', 0) for line in lines]
        total_chars = sum(len(line.get('text', '')) for line in lines)
        low_confidence_lines = len([c for c in confidences if c < 0.5])

        return {
            "total_lines": len(lines),
            "total_characters": total_chars,
            "average_confidence": sum(confidences) / len(confidences),
            "min_confidence": min(confidences),
            "max_confidence": max(confidences),
            "low_confidence_lines": low_confidence_lines
        }

    def merge_similar_lines(self, lines: List[Dict[str, Any]], similarity_threshold: float = 0.8) -> List[Dict[str, Any]]:
        """
        Merge text lines that are very close spatially (basic implementation).

        Args:
            lines: List of line dictionaries with bbox
            similarity_threshold: Not used in basic implementation

        Returns:
            List of lines (currently unchanged, can be extended for advanced merging)
        """
        # Basic implementation - just return as is
        # Could be extended to merge lines that are on the same horizontal line
        # or very close vertically
        return lines

    def clean_text(self, text: str) -> str:
        """
        Clean and normalize extracted text.

        Args:
            text: Raw extracted text

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove excessive whitespace
        import re
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines to double
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces to single
        text = text.strip()

        return text

    def format_ocr_response(self, lines: List[Dict[str, Any]], full_text: str, include_bbox: bool = True) -> Dict[str, Any]:
        """
        Format OCR results into a standardized response format.

        Args:
            lines: List of line dictionaries
            full_text: Full extracted text
            include_bbox: Whether to include bounding box data

        Returns:
            Formatted response dictionary
        """
        # Clean the full text
        cleaned_text = self.clean_text(full_text)

        # Prepare lines data
        formatted_lines = []
        for line in lines:
            line_data = {
                "text": line.get("text", ""),
                "confidence": line.get("confidence", 0.0)
            }
            if include_bbox and "bbox" in line:
                line_data["bbox"] = line["bbox"]
            formatted_lines.append(line_data)

        # Get statistics
        stats = self.get_text_statistics(lines)

        return {
            "text": cleaned_text,
            "lines": formatted_lines,
            "statistics": stats,
            "success": True
        }
