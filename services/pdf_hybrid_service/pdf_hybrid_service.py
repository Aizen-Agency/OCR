"""
PDF Hybrid Service - Handles hybrid PDF text extraction with intelligent page classification
"""

import os
import logging
import uuid
import time
import signal
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path

import fitz  # PyMuPDF

from config import get_config
from services.page_classifier import classify_page
from services.ocr_service.ocr_service import OCRService
from services.pdf_hybrid_service.helpers.pdf_extractor import extract_page_content as extract_page_content_helper
from utils.resource_cleanup import pdf_document_context, cleanup_temp_file
from utils.exceptions import PDFValidationError, DiskSpaceError, JobCreationError
from utils.validation import validate_file_path, check_disk_space, validate_pdf_file_size

# Lazy import to avoid circular dependency - celery_app imports services
# This import is only used in create_hybrid_job method
try:
    from celery_app import celery_app
except ImportError:
    celery_app = None

logger = logging.getLogger(__name__)


class PDFHybridService:
    """
    Service for hybrid PDF text extraction that intelligently uses
    PDF text extraction for text pages and OCR for image pages.
    """

    def __init__(self):
        self.config = get_config()
        # Ensure temp directory exists
        os.makedirs(self.config.PDF_HYBRID_TEMP_DIR, exist_ok=True)

    def chunk_pages(self, page_count: int, chunk_size: int) -> List[Tuple[int, int]]:
        """
        Split page indices into chunks.

        Args:
            page_count: Total number of pages
            chunk_size: Number of pages per chunk

        Returns:
            List of (start_page, end_page) tuples (end is exclusive)
        """
        chunks = []
        for start in range(0, page_count, chunk_size):
            end = min(start + chunk_size, page_count)
            chunks.append((start, end))
        return chunks

    def extract_page_content(
        self,
        page: fitz.Page,
        page_index: int,
        classification: str,
        dpi: int,
        ocr_service: OCRService,
        filename: str = ""
    ) -> Dict[str, Any]:
        """
        Extract content from a PDF page based on its classification.

        This method delegates to the helper function for actual extraction logic,
        maintaining separation of concerns.

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
        return extract_page_content_helper(
            page=page,
            page_index=page_index,
            classification=classification,
            dpi=dpi,
            ocr_service=ocr_service,
            filename=filename
        )

    def create_hybrid_job(
        self,
        pdf_data: bytes,
        filename: str,
        options: Dict[str, Any]
    ) -> str:
        """
        Create a hybrid PDF extraction job.

        Args:
            pdf_data: Raw PDF bytes
            filename: Original filename
            options: Processing options (dpi, chunk_size, max_pages, etc.)

        Returns:
            Master job_id (Celery task ID for aggregation)

        Raises:
            ValueError: If PDF is invalid or exceeds limits
        """
        temp_path = None
        try:
            logger.info(f"create_hybrid_job: Starting for file {filename}, size={len(pdf_data)} bytes")
            
            # Validate PDF file size first
            max_size = self.config.MAX_PDF_SIZE
            logger.info(f"create_hybrid_job: Validating PDF file size (max={max_size} bytes)")
            is_valid_size, size_error = validate_pdf_file_size(pdf_data, max_size)
            if not is_valid_size:
                raise PDFValidationError(size_error or "Invalid PDF file size")
            
            # Validate PDF using context manager for automatic cleanup
            # Add timeout to prevent hanging on corrupted or complex PDFs
            logger.info("create_hybrid_job: Opening PDF document (this may take time for large/corrupted PDFs)")
            
            def timeout_handler(signum, frame):
                raise TimeoutError("PDF parsing timed out after 30 seconds")
            
            # Set up 30 second timeout for PDF parsing
            old_handler = None
            try:
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)  # 30 second timeout
                
                try:
                    with pdf_document_context(pdf_data=pdf_data) as doc:
                        logger.info("create_hybrid_job: PDF document opened, counting pages")
                        page_count = len(doc)
                        logger.info(f"create_hybrid_job: PDF has {page_count} pages")
                        
                        # Check max pages limit
                        max_pages = options.get("max_pages", self.config.PDF_HYBRID_MAX_PAGES)
                        if page_count > max_pages:
                            raise PDFValidationError(
                                f"PDF has {page_count} pages, which exceeds maximum of {max_pages} pages"
                            )

                        if page_count == 0:
                            raise PDFValidationError("PDF has no pages")

                        if doc.is_encrypted:
                            raise PDFValidationError("Encrypted PDFs are not supported")
                finally:
                    # Cancel alarm and restore old handler
                    signal.alarm(0)
                    if old_handler is not None:
                        signal.signal(signal.SIGALRM, old_handler)
                        
            except TimeoutError:
                # Clean up signal handler
                signal.alarm(0)
                if old_handler is not None:
                    signal.signal(signal.SIGALRM, old_handler)
                logger.error("PDF parsing timed out after 30 seconds - file may be corrupted or too complex")
                raise PDFValidationError("PDF parsing timed out. The file may be corrupted, too complex, or too large. Please try a different PDF.")
            except PDFValidationError:
                # Clean up signal handler
                signal.alarm(0)
                if old_handler is not None:
                    signal.signal(signal.SIGALRM, old_handler)
                # Re-raise validation errors as-is
                raise
            except Exception as e:
                # Clean up signal handler
                signal.alarm(0)
                if old_handler is not None:
                    signal.signal(signal.SIGALRM, old_handler)
                # Catch any other exceptions during PDF parsing (corrupted files, etc.)
                logger.error(f"PDF parsing failed: {str(e)} (type: {type(e).__name__})")
                raise PDFValidationError(f"Failed to parse PDF file. The file may be corrupted or invalid: {str(e)}")

            # Get processing options
            dpi = options.get("dpi", self.config.PDF_HYBRID_DEFAULT_DPI)
            chunk_size = options.get("chunk_size", self.config.PDF_HYBRID_DEFAULT_CHUNK_SIZE)
            text_threshold = options.get("text_threshold", self.config.PDF_HYBRID_TEXT_THRESHOLD)
            image_area_threshold = options.get(
                "image_area_threshold",
                self.config.PDF_HYBRID_IMAGE_AREA_THRESHOLD
            )

            # Split into chunks
            chunks = self.chunk_pages(page_count, chunk_size)
            total_chunks = len(chunks)

            # Check if celery_app is available
            if celery_app is None:
                raise RuntimeError("Celery app not available - cannot create async jobs")

            # Create a temporary job_id first (will be replaced by aggregate task ID)
            temp_job_id = str(uuid.uuid4())
            
            # Save PDF to temporary file using temp_job_id
            temp_filename = f"{temp_job_id}_{filename}"
            temp_path = os.path.join(self.config.PDF_HYBRID_TEMP_DIR, temp_filename)
            
            # Check disk space before writing
            has_space, space_error = check_disk_space(temp_path, len(pdf_data))
            if not has_space:
                raise DiskSpaceError(space_error or "Insufficient disk space")
            
            # Validate temp directory path
            temp_dir = self.config.PDF_HYBRID_TEMP_DIR
            is_valid_dir, dir_error = validate_file_path(temp_dir, must_exist=False)
            if not is_valid_dir:
                # Try to create directory
                try:
                    os.makedirs(temp_dir, exist_ok=True)
                except Exception as create_error:
                    raise JobCreationError(f"Failed to create temp directory: {str(create_error)}")
            
            try:
                with open(temp_path, 'wb') as f:
                    f.write(pdf_data)
                
                logger.info(f"Saved PDF to temp file: {temp_path} ({len(pdf_data)} bytes, {page_count} pages)")
            except (IOError, OSError) as file_error:
                logger.error(f"Failed to save PDF to temp file: {str(file_error)}")
                raise JobCreationError(f"Failed to save PDF file: {str(file_error)}")

            # Enqueue aggregation task first to get the real job_id
            # Note: The aggregate task will use self.request.id as the master job_id
            aggregate_task = celery_app.send_task(
                'tasks.aggregate_pdf_chunks',
                args=[],
                kwargs={
                    "job_id": temp_job_id,  # Not used, but kept for compatibility
                    "total_chunks": total_chunks,
                    "page_count": page_count,
                    "filename": filename,
                    "pdf_path": temp_path
                }
            )
            
            # Use aggregate task ID as the master job_id
            master_job_id = aggregate_task.id

            logger.info(
                f"Created hybrid PDF job: {master_job_id}, "
                f"{page_count} pages, {total_chunks} chunks, "
                f"chunk_size={chunk_size}, dpi={dpi}"
            )

            # Enqueue chunk processing tasks with master_job_id
            chunk_tasks = []
            for chunk_id, (start_page, end_page) in enumerate(chunks):
                # Use celery_app.send_task to avoid direct import
                chunk_task = celery_app.send_task(
                    'tasks.process_pdf_chunk',
                    args=[],
                    kwargs={
                        "pdf_path": temp_path,
                        "job_id": master_job_id,  # Use master job_id for consistency
                        "chunk_id": chunk_id,
                        "start_page": start_page,
                        "end_page": end_page,
                        "options": {
                            "dpi": dpi,
                            "text_threshold": text_threshold,
                            "image_area_threshold": image_area_threshold,
                            "filename": filename
                        }
                    }
                )
                chunk_tasks.append(chunk_task.id)
                logger.debug(f"Enqueued chunk {chunk_id}: pages {start_page}-{end_page}")

            logger.info(f"Hybrid PDF job created: master_job_id={master_job_id}, chunks={len(chunk_tasks)}")

            # Return the aggregation task ID as the master job_id
            return master_job_id

        except (PDFValidationError, DiskSpaceError, JobCreationError):
            # Re-raise custom exceptions as-is
            if temp_path and os.path.exists(temp_path):
                cleanup_temp_file(temp_path)
            raise
        except Exception as e:
            logger.error(f"Error creating hybrid PDF job: {str(e)}")
            # Cleanup temp file if it was created but job creation failed
            if temp_path and os.path.exists(temp_path):
                cleanup_temp_file(temp_path)
            raise JobCreationError(f"Failed to create hybrid PDF job: {str(e)}")

