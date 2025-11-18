"""
Celery Tasks for OCR Processing
"""

import os
import logging
import time
import traceback
from typing import Dict, Any
from celery import Task, signals

# CRITICAL FIX: Set HOME environment variable BEFORE any PaddleX imports
# PaddleX determines cache directory during import using Path.home()
os.environ['HOME'] = '/tmp'

# Configure PaddleOCR environment (same as OCR service - ROOT CAUSE FIX)
paddle_cache_dir = '/tmp/.paddlex'
os.makedirs(paddle_cache_dir, exist_ok=True)
os.environ['PADDLEPADDLE_CACHE_DIR'] = paddle_cache_dir
os.environ['XDG_CACHE_HOME'] = '/tmp/.cache'

from celery_app import celery_app
from services.ocr_service.ocr_service import OCRService
from services.redis_service import RedisService
from utils.encoding import decode_base64, generate_file_hash
from utils.service_manager import get_ocr_service, get_redis_service
from utils.resource_manager import cleanup_memory

logger = logging.getLogger(__name__)


@signals.worker_ready.connect
def preload_ocr_service(sender, **kwargs):
    """Pre-initialize OCR service when worker starts to avoid delay on first task."""
    logger.info("Worker ready - pre-initializing OCR service via ServiceManager...")
    try:
        # Use service manager to get OCR service (will initialize if needed)
        ocr_service = get_ocr_service()
        logger.info("OCR service pre-initialized successfully via ServiceManager - ready to process tasks!")
    except Exception as e:
        logger.warning(f"Failed to pre-initialize OCR service: {str(e)}. Will initialize on first task.")


def _process_ocr_with_cache(
    ocr_svc: OCRService,
    redis_svc: RedisService,
    file_data: bytes,
    filename: str,
    processor_func,
    file_hash: str,
    *args,
    **kwargs
) -> Dict[str, Any]:
    """
    Process OCR with cache checking and result caching.

    Args:
        ocr_svc: OCR service instance
        redis_svc: Redis service instance
        file_data: Raw file bytes
        filename: Filename for logging
        processor_func: OCR processing function to call
        file_hash: File hash for cache key
        *args: Additional positional arguments for processor_func (e.g., DPI for PDF)
        **kwargs: Additional keyword arguments for processor_func

    Returns:
        OCR result dictionary
    """
    # Extract DPI from args if present (for PDF caching)
    dpi = args[0] if args and isinstance(args[0], int) else None

    # Check cache first
    cached_result = redis_svc.get_cached_result(file_hash, dpi)
    if cached_result:
        logger.info(f"Cache hit for file: {filename}")
        cached_result['cached'] = True
        return cached_result

    # Process OCR
    result = processor_func(file_data, filename, *args, **kwargs)

    if result.get('success', False):
        # Cache the result (with DPI if provided)
        redis_svc.set_cached_result(file_hash, result, dpi=dpi)
        result['cached'] = False
    else:
        logger.error(f"OCR processing failed for {filename}: {result.get('error', 'Unknown error')}")

    return result


# Service access functions now use centralized service manager
# Imported from utils.service_manager for consistency


class OCRTask(Task):
    """Base task class with error handling."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Task {task_id} failed: {str(exc)}")
        logger.error(f"Exception info: {einfo}")

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        logger.info(f"Task {task_id} completed successfully")


@celery_app.task(bind=True, base=OCRTask, name='tasks.process_image_task')
def process_image_task(self, image_data_b64: str, filename: str = "") -> Dict[str, Any]:
    """
    Process an image file for OCR asynchronously.

    Args:
        image_data_b64: Base64 encoded image data
        filename: Optional filename for logging

    Returns:
        Dict containing OCR results
    """
    try:
        start_time = time.time()
        logger.info(f"Processing image task: {filename} (Task ID: {self.request.id})")

        # Decode base64 image data
        decode_start = time.time()
        image_data = decode_base64(image_data_b64)
        logger.info(f"Decoded image in {time.time() - decode_start:.2f}s")

        # Get services
        service_start = time.time()
        ocr_svc = get_ocr_service()
        redis_svc = get_redis_service()
        service_time = time.time() - service_start
        logger.info(f"Got services in {service_time:.2f}s (OCR initialized: {ocr_svc.ocr is not None})")
        
        # If OCR not initialized, it will initialize now (slow)
        if ocr_svc.ocr is None:
            logger.warning("OCR not pre-initialized - initializing now (this will take 1-2 minutes)...")
            init_start = time.time()
            config = get_config()
            ocr_svc.initialize_ocr(
                lang=config.OCR_LANG,
                use_gpu=config.USE_GPU,
                use_angle_cls=config.USE_ANGLE_CLS
            )
            logger.info(f"OCR initialized in {time.time() - init_start:.2f}s")

        # Generate cache key (works even if Redis is unavailable)
        logger.info(f"Generating cache key for {filename}")
        # Use centralized hash function for consistency
        file_hash = generate_file_hash(image_data)
        logger.info(f"Cache key generated: {file_hash[:16]}...")

        # Process with cache (gracefully handles Redis unavailability)
        logger.info(f"Calling OCR processing for {filename}")
        if redis_svc and redis_svc.is_connected():
            result = _process_ocr_with_cache(
                ocr_svc, redis_svc, image_data, filename,
                ocr_svc.process_image, file_hash
            )
        else:
            # Process without cache if Redis is unavailable
            logger.warning("Redis unavailable, processing without cache")
            result = ocr_svc.process_image(image_data, filename)
            result['cached'] = False
        logger.info(f"OCR processing completed for {filename}, result success: {result.get('success', False)}")

        # Add metadata
        result['job_id'] = self.request.id
        result['filename'] = filename
        result['file_size'] = len(image_data)
        
        total_time = time.time() - start_time
        logger.info(f"Completed image task {filename} in {total_time:.2f}s total")

        return result

    except Exception as e:
        logger.error(f"Error in process_image_task: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "job_id": self.request.id,
            "filename": filename
        }
    finally:
        # Cleanup memory using resource manager
        cleanup_memory(force=False)
        ocr_svc = get_ocr_service()
        ocr_svc.cleanup_memory()


@celery_app.task(bind=True, base=OCRTask, name='tasks.process_pdf_task')
def process_pdf_task(self, pdf_data_b64: str, filename: str = "", dpi: int = 300) -> Dict[str, Any]:
    """
    Process a PDF file for OCR asynchronously.

    Args:
        pdf_data_b64: Base64 encoded PDF data
        filename: Optional filename for logging
        dpi: DPI for PDF to image conversion

    Returns:
        Dict containing OCR results for all pages
    """
    try:
        logger.info(f"Processing PDF task: {filename} at {dpi} DPI (Task ID: {self.request.id})")

        # Decode base64 PDF data
        pdf_data = decode_base64(pdf_data_b64)

        # Get services
        ocr_svc = get_ocr_service()
        redis_svc = get_redis_service()  # May be None if Redis unavailable

        # Generate cache key (with DPI) - works even if Redis is unavailable
        # Use centralized hash function for consistency
        file_hash = generate_file_hash(pdf_data)

        # Process with cache (gracefully handles Redis unavailability)
        if redis_svc and redis_svc.is_connected():
            result = _process_ocr_with_cache(
                ocr_svc, redis_svc, pdf_data, filename,
                ocr_svc.process_pdf, file_hash, dpi
            )
        else:
            # Process without cache if Redis is unavailable
            logger.warning("Redis unavailable, processing without cache")
            result = ocr_svc.process_pdf(pdf_data, filename, dpi)
            result['cached'] = False

        # Add metadata
        result['job_id'] = self.request.id
        result['filename'] = filename
        result['file_size'] = len(pdf_data)
        result['processing_dpi'] = dpi

        return result

    except Exception as e:
        logger.error(f"Error in process_pdf_task: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "job_id": self.request.id,
            "filename": filename,
            "total_pages": 0
        }
    finally:
        # Cleanup memory using resource manager
        cleanup_memory(force=False)
        ocr_svc = get_ocr_service()
        ocr_svc.cleanup_memory()
