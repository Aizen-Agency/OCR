"""
Constants - Application-wide constants
"""

# Redis Key Prefixes
REDIS_KEY_PREFIX_OCR_RESULT = "ocr:result:"
REDIS_KEY_PREFIX_RATE_LIMIT = "rate_limit:"

# Cache Configuration
CACHE_KEY_SEPARATOR = ":"
CACHE_DPI_SUFFIX = "dpi"

# Rate Limiting
RATE_LIMIT_WINDOW_SECONDS = 60

# Job Status Messages
JOB_CREATED_MESSAGE = "OCR job created successfully. Use GET /ocr/job/{job_id} to check status."
BATCH_JOBS_CREATED_MESSAGE = "Batch jobs created successfully. Use GET /ocr/job/{job_id} to check status for each job."
JOB_PROCESSING_MESSAGE = "Job is still processing. Please check status again later."

# Error Messages
ERROR_NO_FILE = "No file provided"
ERROR_FILE_TOO_LARGE = "File too large"
ERROR_INVALID_DPI = "Invalid DPI"
ERROR_UNSUPPORTED_FILE_TYPE = "Unsupported file type"
ERROR_FILE_VALIDATION_FAILED = "File validation failed"
ERROR_INTERNAL_SERVER = "Internal server error"

# File Type Extensions
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.gif')
PDF_EXTENSIONS = ('.pdf',)

# DPI Limits
MIN_DPI = 72
MAX_DPI = 600
DEFAULT_DPI = 300

