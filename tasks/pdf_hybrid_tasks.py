"""
Celery Tasks for Hybrid PDF Processing

NOTE: Environment variables are set before imports because PaddleOCR/PaddleX
determines cache directories during import time. This must happen before
any PaddleOCR-related imports.
"""

import os
import logging
import time
import traceback
from typing import Dict, Any

# CRITICAL: Set HOME environment variable BEFORE any PaddleX imports
# PaddleX determines cache directory during import using Path.home()
os.environ['HOME'] = '/tmp'

# Configure PaddleOCR environment variables
# These must be set before importing PaddleOCR or related services
paddle_cache_dir = '/tmp/.paddlex'
os.makedirs(paddle_cache_dir, exist_ok=True)
os.environ['PADDLEPADDLE_CACHE_DIR'] = paddle_cache_dir
os.environ['XDG_CACHE_HOME'] = '/tmp/.cache'

# Now safe to import third-party libraries
from celery import Task, signals
import fitz  # PyMuPDF

# Local imports after environment setup
from celery_app import celery_app
from config import get_config
from services.ocr_service.ocr_service import OCRService
from services.redis_service import RedisService
from services.page_classifier import classify_page
from services.pdf_hybrid_service import PDFHybridService
from utils.resource_cleanup import pdf_document_context, cleanup_temp_file
from utils.validation import validate_file_path
from utils.service_manager import get_ocr_service, get_redis_service
from utils.resource_manager import cleanup_memory

logger = logging.getLogger(__name__)

# PDF hybrid service instance (not managed by service manager yet)
pdf_hybrid_service = None


@signals.worker_ready.connect
def preload_services(sender, **kwargs):
    """Pre-initialize services when worker starts."""
    global pdf_hybrid_service
    logger.info("Worker ready - pre-initializing services for hybrid PDF processing via ServiceManager...")
    try:
        # Initialize services via service manager
        get_redis_service()
        pdf_hybrid_service = PDFHybridService()
        # OCR service will be initialized on first use via service manager
        logger.info("Services pre-initialized successfully via ServiceManager")
    except Exception as e:
        logger.warning(f"Failed to pre-initialize services: {str(e)}")


def get_pdf_hybrid_service() -> PDFHybridService:
    """Get or initialize PDF hybrid service."""
    global pdf_hybrid_service
    if pdf_hybrid_service is None:
        pdf_hybrid_service = PDFHybridService()
    return pdf_hybrid_service

# Service access functions now use centralized service manager
# Imported from utils.service_manager for consistency


class HybridPDFTask(Task):
    """Base task class with error handling."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Task {task_id} failed: {str(exc)}")
        logger.error(f"Exception info: {einfo}")

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        logger.info(f"Task {task_id} completed successfully")


@celery_app.task(bind=True, base=HybridPDFTask, name='tasks.process_pdf_chunk')
def process_pdf_chunk(
    self,
    pdf_path: str,
    job_id: str,
    chunk_id: int,
    start_page: int,
    end_page: int,
    options: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process a chunk of PDF pages.

    Args:
        pdf_path: Path to PDF file on disk
        job_id: Job ID
        chunk_id: Chunk ID (0-indexed)
        start_page: Start page index (inclusive)
        end_page: End page index (exclusive)
        options: Processing options (dpi, text_threshold, image_area_threshold, filename)

    Returns:
        Dictionary with chunk processing summary
    """
    start_time = time.time()
    logger.info(
        f"Processing PDF chunk {chunk_id} for job {job_id}: "
        f"pages {start_page}-{end_page-1} (Task ID: {self.request.id})"
    )

    try:
        # Get services
        ocr_svc = get_ocr_service()
        redis_svc = get_redis_service()
        pdf_hybrid_svc = get_pdf_hybrid_service()

        # Extract options
        dpi = options.get("dpi", 300)
        text_threshold = options.get("text_threshold", 30)
        image_area_threshold = options.get("image_area_threshold", 0.0)
        filename = options.get("filename", "")

        # Validate PDF file path
        is_valid, path_error = validate_file_path(pdf_path, must_exist=True)
        if not is_valid:
            raise FileNotFoundError(path_error or f"PDF file not found: {pdf_path}")

        # Open PDF using context manager for automatic cleanup
        pages_processed = []
        total_pages = 0

        with pdf_document_context(pdf_path=pdf_path) as doc:
            total_pages = len(doc)
            
            # Process each page in the chunk
            for page_index in range(start_page, end_page):
                try:
                    page = doc.load_page(page_index)

                    # Classify page
                    classification = classify_page(
                        page,
                        text_threshold=text_threshold,
                        image_area_threshold=image_area_threshold
                    )

                    # Extract content
                    page_result = pdf_hybrid_svc.extract_page_content(
                        page=page,
                        page_index=page_index,
                        classification=classification,
                        dpi=dpi,
                        ocr_service=ocr_svc,
                        filename=filename
                    )

                    pages_processed.append(page_result)

                    # Update progress
                    pages_done = start_page + len(pages_processed)
                    redis_svc.update_progress(job_id, pages_done, total_pages)

                    logger.debug(
                        f"Processed page {page_index} ({classification}): "
                        f"{len(page_result.get('text', ''))} chars"
                    )

                    # Force memory cleanup after each page to prevent accumulation
                    cleanup_memory(force=False)

                except Exception as page_error:
                    logger.error(f"Error processing page {page_index}: {str(page_error)}")
                    # Add error page result
                    pages_processed.append({
                        "page_index": page_index,
                        "classification": "error",
                        "source": "error",
                        "text": "",
                        "error": str(page_error)
                    })
                    # Cleanup memory even on error
                    cleanup_memory(force=False)

        # Store chunk result in Redis
        chunk_result = {
            "chunk_id": chunk_id,
            "start_page": start_page,
            "end_page": end_page,
            "pages": pages_processed,
            "pages_count": len(pages_processed),
            "processing_time_seconds": round(time.time() - start_time, 2)
        }

        redis_svc.store_chunk_result(job_id, chunk_id, chunk_result)
        
        # Final memory cleanup after chunk processing
        cleanup_memory(force=False)

        logger.info(
            f"Completed chunk {chunk_id} for job {job_id}: "
            f"{len(pages_processed)} pages in {time.time() - start_time:.2f}s"
        )

        return {
            "success": True,
            "chunk_id": chunk_id,
            "pages_count": len(pages_processed),
            "processing_time_seconds": chunk_result["processing_time_seconds"]
        }

    except Exception as e:
        logger.error(f"Error in process_pdf_chunk: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return {
            "success": False,
            "chunk_id": chunk_id,
            "error": str(e),
            "job_id": job_id
        }
    finally:
        # Cleanup memory
        try:
            ocr_svc = get_ocr_service()
            if ocr_svc:
                ocr_svc.cleanup_memory()
        except Exception:
            pass  # Ignore cleanup errors


@celery_app.task(bind=True, base=HybridPDFTask, name='tasks.aggregate_pdf_chunks')
def aggregate_pdf_chunks(
    self,
    job_id: str,
    total_chunks: int,
    page_count: int,
    filename: str,
    pdf_path: str
) -> Dict[str, Any]:
    """
    Aggregate results from all chunks and create final result.

    Args:
        job_id: Job ID
        total_chunks: Total number of chunks
        page_count: Total number of pages
        filename: Original filename
        pdf_path: Path to PDF file (for cleanup)

    Returns:
        Final aggregated result dictionary
    """
    start_time = time.time()
    # Use self.request.id as the master job_id (this is the aggregate task ID)
    master_job_id = self.request.id
    logger.info(f"Aggregating chunks for job {master_job_id}: {total_chunks} chunks, {page_count} pages")

    try:
        redis_svc = get_redis_service()

        # Poll for all chunk results
        max_wait_time = 3600  # 1 hour max wait
        poll_interval = 2  # Check every 2 seconds
        waited = 0
        all_chunks = []

        while waited < max_wait_time:
            chunk_results = redis_svc.get_chunk_results(master_job_id)
            
            if len(chunk_results) >= total_chunks:
                all_chunks = chunk_results
                logger.info(f"All {total_chunks} chunks ready for aggregation")
                break

            logger.debug(
                f"Waiting for chunks: {len(chunk_results)}/{total_chunks} ready "
                f"(waited {waited}s)"
            )
            time.sleep(poll_interval)
            waited += poll_interval

        if len(all_chunks) < total_chunks:
            raise TimeoutError(
                f"Timeout waiting for chunks: only {len(all_chunks)}/{total_chunks} ready"
            )

        # Aggregate pages from all chunks in order
        all_pages = []
        pages_text = 0
        pages_ocr = 0

        for chunk_result in all_chunks:
            chunk_pages = chunk_result.get("pages", [])
            for page in chunk_pages:
                all_pages.append(page)
                classification = page.get("classification", "unknown")
                if classification == "text":
                    pages_text += 1
                elif classification == "image":
                    pages_ocr += 1

        # Sort pages by page_index to ensure correct order
        all_pages.sort(key=lambda x: x.get("page_index", 0))

        # Build final result
        duration_ms = int((time.time() - start_time) * 1000)

        final_result = {
            "job_id": self.request.id,
            "file_name": filename,
            "page_count": page_count,
            "pages": all_pages,
            "stats": {
                "pages_text": pages_text,
                "pages_ocr": pages_ocr,
                "duration_ms": duration_ms
            },
            "success": True
        }

        logger.info(
            f"Aggregation complete for job {master_job_id}: "
            f"{pages_text} text pages, {pages_ocr} OCR pages, "
            f"{duration_ms}ms total"
        )

        # Cleanup
        try:
            # Delete temp PDF file
            cleanup_temp_file(pdf_path)

            # Cleanup Redis chunk data
            redis_svc.cleanup_chunk_data(master_job_id)
            
            # Final memory cleanup
            cleanup_memory(force=False)
        except Exception as cleanup_error:
            logger.warning(f"Error during cleanup: {str(cleanup_error)}")

        return final_result

    except Exception as e:
        logger.error(f"Error in aggregate_pdf_chunks: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        
        # Cleanup on error
        try:
            master_job_id = self.request.id
            cleanup_temp_file(pdf_path)
            redis_svc = get_redis_service()
            redis_svc.cleanup_chunk_data(master_job_id)
            force_memory_cleanup()
        except Exception as cleanup_error:
            logger.warning(f"Error during error cleanup: {str(cleanup_error)}")

        return {
            "job_id": self.request.id,
            "file_name": filename,
            "page_count": page_count,
            "pages": [],
            "stats": {
                "pages_text": 0,
                "pages_ocr": 0,
                "duration_ms": 0
            },
            "success": False,
            "error": str(e)
        }

