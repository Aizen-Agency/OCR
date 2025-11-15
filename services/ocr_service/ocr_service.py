"""
OCR Service - Main service class for handling OCR operations
"""

import logging
import gc
import psutil
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from PIL import Image

from paddleocr import PaddleOCR
from .helpers.image_processor import ImageProcessor
from .helpers.pdf_processor import PDFProcessor
from .helpers.text_extractor import TextExtractor

logger = logging.getLogger(__name__)


class OCRService:
    """
    Main OCR service class that handles PaddleOCR operations for images and PDFs.
    Implements singleton pattern for efficient resource management.
    """

    _instance: Optional['OCRService'] = None
    _initialized: bool = False

    def __new__(cls) -> 'OCRService':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.ocr: Optional[PaddleOCR] = None
            self.image_processor = ImageProcessor()
            self.pdf_processor = PDFProcessor()
            self.text_extractor = TextExtractor()
            self._initialized = True

    def initialize_ocr(self, lang: str = 'en', use_gpu: bool = False,
                      use_pp_ocr_v5_server: bool = True, 
                      use_angle_cls: bool = True,
                      det_limit_side_len: int = 1280,
                      rec_batch_num: int = 8,
                      **kwargs) -> None:
        """
        Initialize the PaddleOCR 3.x model with PP-OCRv5 (default in PaddleOCR 3.0).
        
        According to official docs: https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html
        PaddleOCR 3.x uses PP-OCRv5_server models by default with simplified API.

        Args:
            lang: Language for OCR (default: 'en'). Supported: ch, en, fr, de, japan, korean, etc.
            use_gpu: Reserved for future use (PaddleOCR 3.x auto-detects GPU)
            use_pp_ocr_v5_server: Reserved for compatibility (always True in PaddleOCR 3.x)
            use_angle_cls: Reserved for compatibility (configured via PaddleX config if needed)
            det_limit_side_len: Reserved for compatibility (configured via PaddleX config if needed)
            rec_batch_num: Reserved for compatibility (configured via PaddleX config if needed)
            **kwargs: Additional PaddleOCR initialization parameters
        """
        try:
            if self.ocr is None:
                logger.info("=" * 60)
                logger.info("Initializing PaddleOCR 3.x (PP-OCRv5)")
                logger.info(f"Language: {lang}")
                logger.info(f"Model: PP-OCRv5_server (default in PaddleOCR 3.0)")
                logger.info(f"Documentation: https://www.paddleocr.ai/")
                logger.info("=" * 60)

                # PaddleOCR 3.x uses simplified API - only 'lang' parameter is needed
                # PP-OCRv5_server models are used by default (best accuracy)
                # Ref: https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html
                self.ocr = PaddleOCR(lang=lang)
                
                logger.info("✓ PaddleOCR initialized successfully!")
                logger.info("  - Using PP-OCRv5_server_det (text detection)")
                logger.info("  - Using PP-OCRv5_server_rec (text recognition)")
                logger.info("  - CPU-optimized (auto-detected)")
                logger.info("  - First inference may take 3-5 minutes to download models")
                logger.info("=" * 60)
            else:
                logger.info("PaddleOCR already initialized")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {str(e)}")
            logger.error("Please check: https://www.paddleocr.ai/latest/en/version3.x/installation.html")
            raise RuntimeError(f"OCR initialization failed: {str(e)}")

    def process_image(self, image_data: bytes, filename: str = "") -> Dict[str, Any]:
        """
        Process a single image for OCR.

        Args:
            image_data: Raw image bytes
            filename: Optional filename for logging

        Returns:
            Dict containing OCR results with text and confidence scores
        """
        if self.ocr is None:
            raise RuntimeError("OCR service not initialized. Call initialize_ocr() first.")

        try:
            logger.info(f"Processing image: {filename}")

            # Process image
            image = self.image_processor.process_image_bytes(image_data)

            # Perform OCR
            result = self.ocr.ocr(np.array(image))

            # Debug: Log raw result
            logger.debug(f"Raw PaddleOCR result type: {type(result)}")
            logger.debug(f"Raw PaddleOCR result length: {len(result) if result else 0}")
            if result and len(result) > 0 and len(result[0]) > 0:
                logger.debug(f"First 3 OCR detections: {result[0][:3]}")

            # Extract text and confidence
            lines, full_text = self.text_extractor.extract_from_ocr_result(result)

            return {
                "text": full_text,
                "lines": lines,
                "success": True
            }

        except Exception as e:
            logger.error(f"Error processing image {filename}: {str(e)}")
            return {
                "text": "",
                "lines": [],
                "success": False,
                "error": str(e)
            }

    def process_pdf(self, pdf_data: bytes, filename: str = "", dpi: int = 300) -> Dict[str, Any]:
        """
        Process a PDF document for OCR.

        Args:
            pdf_data: Raw PDF bytes
            filename: Optional filename for logging
            dpi: DPI for PDF to image conversion (default: 300)

        Returns:
            Dict containing OCR results for all pages
        """
        if self.ocr is None:
            raise RuntimeError("OCR service not initialized. Call initialize_ocr() first.")

        try:
            logger.info(f"Processing PDF: {filename}")

            # Extract pages as images
            page_images = self.pdf_processor.process_pdf_bytes(pdf_data, dpi=dpi)

            pages = []
            total_text = []

            # Process each page
            for page_num, image in enumerate(page_images, 1):
                try:
                    logger.debug(f"Processing page {page_num}/{len(page_images)}")

                    # Perform OCR on page
                    result = self.ocr.ocr(np.array(image))

                    # Extract text and confidence
                    lines, page_text = self.text_extractor.extract_from_ocr_result(result)

                    pages.append({
                        "page": page_num,
                        "text": page_text,
                        "lines": lines,
                        "success": True
                    })

                    if page_text.strip():
                        total_text.append(page_text)

                except Exception as page_error:
                    logger.error(f"Error processing page {page_num}: {str(page_error)}")
                    pages.append({
                        "page": page_num,
                        "text": "",
                        "lines": [],
                        "success": False,
                        "error": str(page_error)
                    })

            full_text = "\n\n".join(total_text)

            return {
                "pages": pages,
                "full_text": full_text,
                "total_pages": len(pages),
                "success": True
            }

        except Exception as e:
            logger.error(f"Error processing PDF {filename}: {str(e)}")
            return {
                "pages": [],
                "full_text": "",
                "total_pages": 0,
                "success": False,
                "error": str(e)
            }

    def get_memory_usage(self) -> Dict[str, Any]:
        """
        Get current memory usage information.

        Returns:
            Dict with memory statistics
        """
        try:
            process = psutil.Process()
            memory_info = process.memory_info()

            return {
                "rss": memory_info.rss,  # Resident Set Size
                "vms": memory_info.vms,  # Virtual Memory Size
                "rss_mb": memory_info.rss / (1024 * 1024),
                "vms_mb": memory_info.vms / (1024 * 1024),
                "percent": process.memory_percent()
            }
        except Exception as e:
            logger.warning(f"Failed to get memory usage: {str(e)}")
            return {
                "error": str(e),
                "rss": 0,
                "vms": 0,
                "rss_mb": 0,
                "vms_mb": 0,
                "percent": 0
            }

    def cleanup_memory(self) -> None:
        """
        Force garbage collection to free memory.
        """
        try:
            gc.collect()
            logger.debug("Memory cleanup performed")
        except Exception as e:
            logger.warning(f"Memory cleanup failed: {str(e)}")

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the OCR service.

        Returns:
            Dict with health status information
        """
        memory_info = self.get_memory_usage()

        return {
            "service": "OCR Service",
            "initialized": self.ocr is not None,
            "paddleocr_available": self.ocr is not None,
            "status": "healthy" if self.ocr is not None else "unhealthy",
            "memory_usage": memory_info
        }
