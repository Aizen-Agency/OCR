"""
PDF Processor Helper - Handles PDF validation, page extraction, and conversion to images
"""

import logging
from typing import List, Optional, Tuple
from PIL import Image
import io
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class PDFProcessor:
    """
    Helper class for processing PDF files and converting pages to images for OCR.
    """

    # Maximum file size (50MB for PDFs)
    MAX_FILE_SIZE = 50 * 1024 * 1024

    # Maximum number of pages to process
    MAX_PAGES = 100

    # Default DPI for PDF to image conversion
    DEFAULT_DPI = 300

    # Maximum DPI to prevent memory issues
    MAX_DPI = 600

    def validate_pdf_file(self, pdf_data: bytes, filename: str = "") -> Tuple[bool, str]:
        """
        Validate PDF file format and basic properties.

        Args:
            pdf_data: Raw PDF bytes
            filename: Optional filename for logging

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check file size
            if len(pdf_data) > self.MAX_FILE_SIZE:
                return False, f"PDF file size exceeds maximum limit of {self.MAX_FILE_SIZE // (1024*1024)}MB"

            # Try to open as PDF
            doc = fitz.open(stream=pdf_data, filetype="pdf")

            # Check number of pages
            num_pages = len(doc)
            if num_pages > self.MAX_PAGES:
                doc.close()
                return False, f"PDF has too many pages: {num_pages}. Maximum allowed: {self.MAX_PAGES}"

            if num_pages == 0:
                doc.close()
                return False, "PDF has no pages"

            # Check if PDF is encrypted/locked
            if doc.is_encrypted:
                doc.close()
                return False, "Encrypted PDFs are not supported"

            doc.close()
            return True, ""

        except Exception as e:
            logger.error(f"PDF validation failed for {filename}: {str(e)}")
            return False, f"Invalid PDF file: {str(e)}"

    def process_pdf_bytes(self, pdf_data: bytes, dpi: int = DEFAULT_DPI) -> List[Image.Image]:
        """
        Process PDF bytes and convert each page to a PIL Image.

        Args:
            pdf_data: Raw PDF bytes
            dpi: DPI for conversion (default: 300)

        Returns:
            List of PIL Images, one per page

        Raises:
            ValueError: If PDF processing fails
        """
        try:
            # Validate DPI
            if dpi > self.MAX_DPI:
                logger.warning(f"DPI {dpi} exceeds maximum {self.MAX_DPI}, using {self.MAX_DPI}")
                dpi = self.MAX_DPI
            elif dpi < 72:
                logger.warning(f"DPI {dpi} is too low, using 72")
                dpi = 72

            # Open PDF
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            num_pages = len(doc)

            logger.info(f"Processing PDF with {num_pages} pages at {dpi} DPI")

            page_images = []

            for page_num in range(num_pages):
                try:
                    page = doc.load_page(page_num)

                    # Convert page to image
                    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB)

                    # Convert to PIL Image
                    img_bytes = pix.tobytes("png")
                    image = Image.open(io.BytesIO(img_bytes))

                    # Ensure RGB mode
                    if image.mode != 'RGB':
                        image = image.convert('RGB')

                    page_images.append(image)

                    logger.debug(f"Processed page {page_num + 1}/{num_pages}")

                except Exception as page_error:
                    logger.error(f"Failed to process page {page_num + 1}: {str(page_error)}")
                    # Continue with other pages instead of failing completely
                    continue

            doc.close()

            if not page_images:
                raise ValueError("No pages could be processed from the PDF")

            logger.info(f"Successfully processed {len(page_images)} pages")
            return page_images

        except Exception as e:
            logger.error(f"Failed to process PDF: {str(e)}")
            raise ValueError(f"PDF processing failed: {str(e)}")

    def process_pdf_file(self, file_path: str, dpi: int = DEFAULT_DPI) -> List[Image.Image]:
        """
        Process a PDF file from disk.

        Args:
            file_path: Path to PDF file
            dpi: DPI for conversion

        Returns:
            List of PIL Images, one per page
        """
        try:
            with open(file_path, 'rb') as f:
                pdf_data = f.read()

            return self.process_pdf_bytes(pdf_data, dpi)

        except Exception as e:
            logger.error(f"Failed to read PDF file {file_path}: {str(e)}")
            raise ValueError(f"PDF file reading failed: {str(e)}")

    def get_pdf_info(self, pdf_data: bytes) -> dict:
        """
        Get basic information about a PDF.

        Args:
            pdf_data: Raw PDF bytes

        Returns:
            Dict with PDF information
        """
        try:
            doc = fitz.open(stream=pdf_data, filetype="pdf")

            info = {
                "page_count": len(doc),
                "is_encrypted": doc.is_encrypted,
                "metadata": doc.metadata,
                "valid": True
            }

            doc.close()
            return info

        except Exception as e:
            logger.error(f"Failed to get PDF info: {str(e)}")
            return {
                "page_count": 0,
                "is_encrypted": False,
                "metadata": {},
                "valid": False,
                "error": str(e)
            }

    def extract_page_as_image(self, pdf_data: bytes, page_num: int, dpi: int = DEFAULT_DPI) -> Optional[Image.Image]:
        """
        Extract a specific page from PDF as an image.

        Args:
            pdf_data: Raw PDF bytes
            page_num: Page number (0-indexed)
            dpi: DPI for conversion

        Returns:
            PIL Image or None if page doesn't exist
        """
        try:
            doc = fitz.open(stream=pdf_data, filetype="pdf")

            if page_num >= len(doc):
                doc.close()
                return None

            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB)

            img_bytes = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_bytes))

            doc.close()

            return image.convert('RGB')

        except Exception as e:
            logger.error(f"Failed to extract page {page_num}: {str(e)}")
            return None
