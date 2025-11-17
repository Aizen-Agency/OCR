"""
Custom Exceptions for the OCR Microservice
"""


class OCRServiceError(Exception):
    """Base exception for OCR service errors."""
    pass


class PDFProcessingError(OCRServiceError):
    """Exception raised for PDF processing errors."""
    pass


class PDFValidationError(PDFProcessingError):
    """Exception raised for PDF validation errors."""
    pass


class DiskSpaceError(OCRServiceError):
    """Exception raised when disk space is insufficient."""
    pass


class ResourceLimitError(OCRServiceError):
    """Exception raised when resource limits are exceeded."""
    pass


class JobCreationError(OCRServiceError):
    """Exception raised when job creation fails."""
    pass

