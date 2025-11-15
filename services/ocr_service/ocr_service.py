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
        Initialize the PaddleOCR model with PP-OCRv5_server_det for production use.

        Args:
            lang: Language for OCR (default: 'en')
            use_gpu: Whether to use GPU for inference
            use_pp_ocr_v5_server: Whether to use PP-OCRv5 server model (default: True)
            use_angle_cls: Enable angle classification for rotated text (default: True)
            det_limit_side_len: Max side length for detection (default: 1280)
            rec_batch_num: Batch size for recognition (default: 8, optimized for 24GB VPS)
            **kwargs: Additional PaddleOCR initialization parameters
        """
        try:
            if self.ocr is None:
                logger.info(f"Initializing PaddleOCR with language: {lang}, PP-OCRv5: {use_pp_ocr_v5_server}")

                # Configure based on use case: development (fast) vs production (accurate)
                ocr_config = {
                    'lang': lang,
                }

                # GPU configuration - PaddleOCR auto-detects GPU availability
                # If GPU is needed, set CUDA_VISIBLE_DEVICES environment variable externally
                if use_gpu:
                    logger.info("GPU mode requested - ensure CUDA_VISIBLE_DEVICES is set if GPU is available")

                if use_pp_ocr_v5_server:
                    # PRODUCTION MODE: Use PP-OCRv5 server models (best accuracy, slower startup)
                    # PaddleOCR 3.x uses v5 server models by default when no version specified
                    logger.info("PRODUCTION MODE: Using PP-OCRv5 server models (high accuracy, 3-5 min startup)")
                    logger.info(f"  - Angle classification: {use_angle_cls}")
                    logger.info(f"  - Detection limit: {det_limit_side_len}px")
                    logger.info(f"  - Recognition batch: {rec_batch_num}")
                    
                    ocr_config.update({
                        'use_angle_cls': use_angle_cls,  # Enable angle classification for rotated text
                        'det_limit_side_len': det_limit_side_len,  # Higher detection limit for better accuracy
                        'rec_batch_num': rec_batch_num,  # Batch processing for better throughput (24GB VPS optimized)
                        'det_db_thresh': 0.3,  # Detection threshold (default: 0.3)
                        'det_db_box_thresh': 0.6,  # Box threshold (default: 0.6)
                        'use_space_char': True,  # Preserve spaces in recognized text
                        'drop_score': 0.5,  # Drop results below this confidence (default: 0.5)
                    })
                    
                    # GPU-specific optimizations
                    if use_gpu:
                        ocr_config.update({
                            'use_gpu': True,
                            'gpu_mem': 2000,  # Allocate 2GB GPU memory per process
                            'enable_mkldnn': False,  # Disable MKLDNN when using GPU
                        })
                        logger.info("  - GPU acceleration ENABLED with 2GB memory allocation")
                    else:
                        ocr_config.update({
                            'use_gpu': False,
                            'enable_mkldnn': True,  # Enable Intel MKL-DNN for CPU optimization
                            'cpu_threads': 4,  # Use 4 CPU threads (optimal for 24GB VPS)
                        })
                        logger.info("  - CPU mode with MKL-DNN optimization (4 threads)")
                else:
                    # DEVELOPMENT MODE: Use lightweight models (faster startup, good accuracy)
                    logger.info("DEVELOPMENT MODE: Using lightweight models (30-60 sec startup)")
                    ocr_config.update({
                        'use_angle_cls': False,  # Disable angle classification for faster processing
                        'det_limit_side_len': 960,  # Smaller detection size for speed
                        'rec_batch_num': 6,  # Smaller batch for lower memory usage
                    })

                # Merge with any additional kwargs
                ocr_config.update(kwargs)

                # Try to initialize PaddleOCR with error handling
                try:
                    self.ocr = PaddleOCR(**ocr_config)
                    logger.info("PaddleOCR with PP-OCRv5_server_det initialized successfully")
                except TypeError as param_error:
                    # If parameters are not supported, try with minimal config
                    logger.warning(f"Some parameters not supported: {param_error}. Trying minimal config.")
                    minimal_config = {'lang': lang}
                    minimal_config.update(kwargs)
                    self.ocr = PaddleOCR(**minimal_config)
                    logger.info("PaddleOCR initialized with minimal configuration")
            else:
                logger.info("PaddleOCR already initialized")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {str(e)}")
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
