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
        logger.debug(f"OCR result type: {type(ocr_result)}, length: {len(ocr_result) if ocr_result else 0}")

        if not ocr_result:
            return [], ""

        lines = []
        text_parts = []

        try:
            logger.debug(f"Full OCR result structure: {ocr_result}")

            detections = []

            # Handle PaddleOCR Pipeline API format - list containing dict with OCR results
            if isinstance(ocr_result, list) and len(ocr_result) == 1 and isinstance(ocr_result[0], dict):
                logger.debug("Detected Pipeline API list[dict] result format")
                ocr_result = ocr_result[0]  # Extract the single dict

            # Handle PaddleOCR Pipeline API format - direct dict
            if isinstance(ocr_result, dict) and 'rec_texts' in ocr_result and 'rec_scores' in ocr_result:
                # Pipeline API format: {'rec_texts': [...], 'rec_scores': [...], 'dt_polys': array(...)}
                logger.debug("Detected Pipeline API dict result format")
                rec_texts = ocr_result.get('rec_texts', [])
                rec_scores = ocr_result.get('rec_scores', [])
                dt_polys = ocr_result.get('dt_polys', [])

                for i, (text, score) in enumerate(zip(rec_texts, rec_scores)):
                    if score >= min_confidence:
                        # Convert polygon to bounding box format
                        bbox = []
                        if i < len(dt_polys):
                            poly = dt_polys[i]
                            if hasattr(poly, 'tolist'):  # numpy array
                                poly = poly.tolist()
                            # Convert polygon to simple bbox [x1,y1,x2,y2,x3,y3,x4,y4]
                            bbox = [coord for point in poly for coord in point]

                        lines.append({
                            "text": text,
                            "confidence": float(score),
                            "bbox": bbox
                        })
                        text_parts.append(text)

            # Handle Pipeline API list format (result objects with methods)
            elif isinstance(ocr_result, list) and ocr_result and hasattr(ocr_result[0], 'print'):
                logger.debug("Detected Pipeline API list result format (objects with methods)")
                for result_obj in ocr_result:
                    # Try to extract data from result object
                    try:
                        # Access the result data - might be in result_obj.res or similar
                        if hasattr(result_obj, 'res'):
                            res_data = result_obj.res
                            if isinstance(res_data, dict):
                                rec_texts = res_data.get('rec_texts', [])
                                rec_scores = res_data.get('rec_scores', [])
                                dt_polys = res_data.get('dt_polys', [])

                                for i, (text, score) in enumerate(zip(rec_texts, rec_scores)):
                                    if score >= min_confidence:
                                        bbox = []
                                        if i < len(dt_polys):
                                            poly = dt_polys[i]
                                            if hasattr(poly, 'tolist'):
                                                poly = poly.tolist()
                                            bbox = [coord for point in poly for coord in point]

                                        lines.append({
                                            "text": text,
                                            "confidence": float(score),
                                            "bbox": bbox
                                        })
                                        text_parts.append(text)
                    except Exception as e:
                        logger.warning(f"Failed to extract data from result object: {e}")
                        continue

            # Normalize result into a flat list of detections:
            # each detection should look like [bbox_coords, (text, score)]
            elif isinstance(ocr_result, list):
                first = ocr_result[0]

                # Case 1: nested shape: [ [ [bbox, (text,score)], ... ] ]
                if isinstance(first, list) and first and isinstance(first[0], (list, tuple)) and len(first[0]) >= 2:
                    detections = first

                # Case 2: flat shape: [ [bbox, (text,score)], ... ]
                elif isinstance(first, (list, tuple)) and len(first) >= 2 and isinstance(first[1], (list, tuple)):
                    detections = ocr_result

                # Case 3: dict-based: [ {"points": ..., "text": ..., "score": ...}, ... ]
                elif isinstance(first, dict):
                    for d in ocr_result:
                        pts = d.get("points") or d.get("box") or d.get("bbox")
                        txt = d.get("text")
                        score = d.get("score", 1.0)
                        if txt is None:
                            continue
                        detections.append([pts, (txt, score)])
                else:
                    logger.warning(f"Unrecognized OCR result structure: {repr(ocr_result)[:500]}")
                    return [], ""

            else:
                logger.warning(f"OCR result is not a list: {type(ocr_result)}")
                return [], ""

            # Now parse normalized detections
            for item in detections:
                try:
                    if not isinstance(item, (list, tuple)) or len(item) < 2:
                        logger.warning(f"Unexpected detection item format: {item}")
                        continue

                    bbox_coords = item[0]
                    text_info = item[1]

                    # text_info should be (text, confidence)
                    if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                        text = str(text_info[0])
                        confidence = float(text_info[1])
                    elif isinstance(text_info, str):
                        text = text_info
                        confidence = 1.0
                    else:
                        logger.warning(f"Unexpected text_info format: {text_info}")
                        continue

                    if confidence < min_confidence:
                        continue

                    # Flatten bbox
                    if isinstance(bbox_coords, list):
                        bbox_flat = []
                        for coord in bbox_coords:
                            if isinstance(coord, (list, tuple)) and len(coord) >= 2:
                                bbox_flat.extend([float(coord[0]), float(coord[1])])
                            else:
                                bbox_flat.extend([0.0, 0.0])
                        bbox = bbox_flat
                    else:
                        bbox = [0.0, 0.0, 0.0, 0.0]

                    line_data = {
                        "text": text,
                        "confidence": confidence,
                        "bbox": bbox,
                    }
                    lines.append(line_data)

                    if text.strip():
                        text_parts.append(text)

                except Exception as e:
                    logger.warning(f"Error parsing OCR item: {str(e)}, item data: {item}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing OCR result structure: {str(e)}")
            return [], ""

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
