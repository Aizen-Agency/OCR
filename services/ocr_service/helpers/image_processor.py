"""
Image Processor Helper - Handles image validation, preprocessing, and format conversion
"""

import logging
from typing import Optional, Tuple
from PIL import Image, ImageOps
import io
from werkzeug.datastructures import FileStorage

logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Helper class for processing and validating image files for OCR.
    """

    # Supported image formats
    SUPPORTED_FORMATS = {'JPEG', 'PNG', 'BMP', 'TIFF', 'WEBP', 'GIF'}

    # Maximum file size (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024

    # Maximum image dimensions (to prevent memory issues)
    MAX_WIDTH = 4096
    MAX_HEIGHT = 4096

    def validate_image_file(self, file_data: bytes, filename: str = "") -> Tuple[bool, str]:
        """
        Validate image file format and size.

        Args:
            file_data: Raw file bytes
            filename: Optional filename for logging

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check file size
            if len(file_data) > self.MAX_FILE_SIZE:
                return False, f"File size exceeds maximum limit of {self.MAX_FILE_SIZE // (1024*1024)}MB"

            # Try to open as image
            image = Image.open(io.BytesIO(file_data))

            # Check format
            if image.format not in self.SUPPORTED_FORMATS:
                return False, f"Unsupported image format: {image.format}. Supported formats: {', '.join(self.SUPPORTED_FORMATS)}"

            # Check dimensions
            width, height = image.size
            if width > self.MAX_WIDTH or height > self.MAX_HEIGHT:
                return False, f"Image dimensions too large: {width}x{height}. Maximum: {self.MAX_WIDTH}x{self.MAX_HEIGHT}"

            image.close()
            return True, ""

        except Exception as e:
            logger.error(f"Image validation failed for {filename}: {str(e)}")
            return False, f"Invalid image file: {str(e)}"

    def process_image_bytes(self, image_data: bytes) -> Image.Image:
        """
        Process raw image bytes into a PIL Image suitable for OCR.

        Args:
            image_data: Raw image bytes

        Returns:
            Processed PIL Image in RGB format

        Raises:
            ValueError: If image processing fails
        """
        try:
            # Open image
            image = Image.open(io.BytesIO(image_data))

            # Convert to RGB (removes alpha channel if present)
            if image.mode in ('RGBA', 'LA', 'P'):
                # Handle transparent images
                if image.mode == 'P':
                    image = image.convert('RGBA')
                # Create white background for transparency
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'RGBA':
                    background.paste(image, mask=image.split()[-1])  # Use alpha as mask
                else:
                    background.paste(image)
                image = background
            else:
                image = image.convert('RGB')

            # Auto-rotate based on EXIF data
            image = ImageOps.exif_transpose(image)

            # Ensure image is not too large for processing
            width, height = image.size
            if width > self.MAX_WIDTH or height > self.MAX_HEIGHT:
                # Calculate scaling factor
                scale = min(self.MAX_WIDTH / width, self.MAX_HEIGHT / height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logger.info(f"Resized image from {width}x{height} to {new_width}x{new_height}")

            return image

        except Exception as e:
            logger.error(f"Failed to process image: {str(e)}")
            raise ValueError(f"Image processing failed: {str(e)}")

    def process_uploaded_file(self, file: FileStorage) -> Tuple[Optional[Image.Image], str]:
        """
        Process an uploaded file from Flask/Werkzeug.

        Args:
            file: Werkzeug FileStorage object

        Returns:
            Tuple of (processed_image, error_message)
        """
        try:
            # Read file data
            file_data = file.read()

            # Validate
            is_valid, error_msg = self.validate_image_file(file_data, file.filename or "")
            if not is_valid:
                return None, error_msg

            # Process
            image = self.process_image_bytes(file_data)

            return image, ""

        except Exception as e:
            logger.error(f"Failed to process uploaded file {file.filename}: {str(e)}")
            return None, f"File processing failed: {str(e)}"

    def get_image_info(self, image: Image.Image) -> dict:
        """
        Get basic information about a PIL Image.

        Args:
            image: PIL Image object

        Returns:
            Dict with image information
        """
        return {
            "format": image.format,
            "mode": image.mode,
            "size": image.size,
            "width": image.size[0],
            "height": image.size[1]
        }
