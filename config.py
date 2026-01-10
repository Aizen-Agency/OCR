"""
Configuration settings for the OCR microservice
"""

import os
from urllib.parse import quote_plus
from typing import Dict, Any


class Config:
    """Base configuration class."""

    # Flask settings
    SECRET_KEY = 'dev-secret-key-for-local-development'

    # Server settings
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'

    # File upload settings
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))  # 50MB
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/tmp/ocr_uploads')

    # OCR settings
    OCR_LANG = os.getenv('OCR_LANG', 'en')
    USE_GPU = os.getenv('USE_GPU', 'false').lower() == 'true'

    # OCR Model settings - PP-OCRv5_server_det for production
    DET_MODEL_DIR = os.getenv('DET_MODEL_DIR', None)  # Text detection model
    REC_MODEL_DIR = os.getenv('REC_MODEL_DIR', None)  # Text recognition model
    CLS_MODEL_DIR = os.getenv('CLS_MODEL_DIR', None)  # Text classification model

    # Use PP-OCRv5 server model by default
    USE_PP_OCR_V5_SERVER = os.getenv('USE_PP_OCR_V5_SERVER', 'true').lower() == 'true'
    
    # PaddleOCR v5 performance settings (optimized for 24GB VPS)
    USE_ANGLE_CLS = os.getenv('USE_ANGLE_CLS', 'true').lower() == 'true'  # Enable angle classification
    DET_LIMIT_SIDE_LEN = int(os.getenv('DET_LIMIT_SIDE_LEN', 1280))  # Detection limit (higher = more accurate)
    REC_BATCH_NUM = int(os.getenv('REC_BATCH_NUM', 8))  # Batch size (higher = faster with more RAM)
    DET_DB_THRESH = float(os.getenv('DET_DB_THRESH', 0.3))  # Detection threshold
    DET_DB_BOX_THRESH = float(os.getenv('DET_DB_BOX_THRESH', 0.6))  # Box threshold
    DROP_SCORE = float(os.getenv('DROP_SCORE', 0.5))  # Minimum confidence score

    # PDF processing settings
    DEFAULT_DPI = int(os.getenv('DEFAULT_DPI', 300))
    MAX_DPI = int(os.getenv('MAX_DPI', 600))
    MIN_DPI = int(os.getenv('MIN_DPI', 72))

    # Performance settings - Optimized for 24GB RAM VPS
    MAX_WORKERS = int(os.getenv('MAX_WORKERS', 2))  # Optimized for 24GB RAM - balance parallelism and memory
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', 300))  # 5 minutes

    # File size limits
    MAX_IMAGE_SIZE = int(os.getenv('MAX_IMAGE_SIZE', 10 * 1024 * 1024))  # 10MB
    MAX_PDF_SIZE = int(os.getenv('MAX_PDF_SIZE', 50 * 1024 * 1024))  # 50MB
    MAX_PDF_PAGES = int(os.getenv('MAX_PDF_PAGES', 100))

    # Image processing limits
    MAX_IMAGE_WIDTH = int(os.getenv('MAX_IMAGE_WIDTH', 4096))
    MAX_IMAGE_HEIGHT = int(os.getenv('MAX_IMAGE_HEIGHT', 4096))

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # OCR confidence settings
    MIN_CONFIDENCE = float(os.getenv('MIN_CONFIDENCE', 0.0))

    # Redis configuration
    # Support both direct connection parameters and URL-based connection
    # Direct connection parameters (preferred):
    REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
    REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
    REDIS_USERNAME = os.getenv('REDIS_USERNAME', 'default')
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
    REDIS_DB = int(os.getenv('REDIS_DB', '0'))
    
    # URL-based connection (fallback for backward compatibility)
    REDIS_URL = os.getenv('REDIS_URL', '')
    
    # Build Redis URL from individual parameters if URL not provided
    # This ensures backward compatibility and provides URL for Celery
    if not REDIS_URL:
        if REDIS_PASSWORD:
            # URL-encode password to handle special characters (/, =, etc.)
            encoded_password = quote_plus(REDIS_PASSWORD)
            if REDIS_USERNAME and REDIS_USERNAME != 'default':
                REDIS_URL = f'redis://{quote_plus(REDIS_USERNAME)}:{encoded_password}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
            else:
                REDIS_URL = f'redis://:{encoded_password}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
        else:
            # No password - insecure but allows local dev
            REDIS_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
    
    REDIS_CACHE_TTL = int(os.getenv('REDIS_CACHE_TTL', 3600))  # 1 hour default

    # Celery configuration
    # Use centralized Redis connection manager to get connection URL
    # This ensures both broker and backend use the same authentication credentials
    # Priority: CELERY_BROKER_URL/CELERY_RESULT_BACKEND env vars > centralized REDIS_URL
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', REDIS_URL)
    
    # Celery worker concurrency - optimized for 24GB RAM VPS
    # Higher concurrency = more parallel processing but higher memory usage
    # Recommended: 4-6 for 24GB RAM, 2-3 for 8GB RAM
    CELERY_WORKER_CONCURRENCY = int(os.getenv('CELERY_WORKER_CONCURRENCY', 5))

    # Celery task time limits (in seconds)
    # Global defaults for regular OCR tasks (images, small PDFs)
    CELERY_TASK_TIME_LIMIT = int(os.getenv('CELERY_TASK_TIME_LIMIT', 600))  # 10 minutes hard limit
    CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', 540))  # 9 minutes soft limit
    
    # PDF Hybrid specific time limits (for large PDFs)
    # Chunk processing: 50 pages per chunk
    CELERY_PDF_CHUNK_TIME_LIMIT = int(os.getenv('CELERY_PDF_CHUNK_TIME_LIMIT', 1800))  # 30 minutes
    CELERY_PDF_CHUNK_SOFT_TIME_LIMIT = int(os.getenv('CELERY_PDF_CHUNK_SOFT_TIME_LIMIT', 1620))  # 27 minutes
    # Aggregation: waits for all chunks to complete (for 5000-page PDFs)
    CELERY_PDF_AGGREGATE_TIME_LIMIT = int(os.getenv('CELERY_PDF_AGGREGATE_TIME_LIMIT', 14400))  # 4 hours
    CELERY_PDF_AGGREGATE_SOFT_TIME_LIMIT = int(os.getenv('CELERY_PDF_AGGREGATE_SOFT_TIME_LIMIT', 12600))  # 3.5 hours
    PDF_AGGREGATE_MAX_WAIT_TIME = int(os.getenv('PDF_AGGREGATE_MAX_WAIT_TIME', 14400))  # 4 hours max wait for chunks

    # Rate limiting configuration
    RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', 10))
    # Separate rate limit for hybrid PDF endpoint (can be more restrictive)
    PDF_HYBRID_RATE_LIMIT_PER_MINUTE = int(os.getenv('PDF_HYBRID_RATE_LIMIT_PER_MINUTE', 20))
    
    # Dynamic rate limiting based on PDF size
    RATE_LIMIT_SMALL_PDF = int(os.getenv('RATE_LIMIT_SMALL_PDF', 20))  # req/min for <10MB PDFs
    RATE_LIMIT_MEDIUM_PDF = int(os.getenv('RATE_LIMIT_MEDIUM_PDF', 10))  # req/min for 10-100MB PDFs
    RATE_LIMIT_LARGE_PDF = int(os.getenv('RATE_LIMIT_LARGE_PDF', 5))  # req/min for >100MB PDFs
    
    # Queue management
    MAX_QUEUE_SIZE = int(os.getenv('MAX_QUEUE_SIZE', 100))  # Max jobs in queue before rejecting
    QUEUE_REJECTION_ENABLED = os.getenv('QUEUE_REJECTION_ENABLED', 'true').lower() == 'true'  # Enable queue size limits
    
    # API Key Authentication
    # SECURITY: API key required for /ocr/* endpoints (health endpoints excluded)
    AUTH_TOKEN = os.getenv('AUTH_TOKEN', '')
    
    # Warn if AUTH_TOKEN is not set in production
    if os.getenv('FLASK_ENV', 'development') == 'production' and not AUTH_TOKEN:
        import warnings
        warnings.warn("AUTH_TOKEN not set in production - API authentication is disabled", UserWarning)

    # Hybrid PDF processing settings
    PDF_HYBRID_MAX_PAGES = int(os.getenv('PDF_HYBRID_MAX_PAGES', 5000))
    PDF_HYBRID_DEFAULT_DPI = int(os.getenv('PDF_HYBRID_DEFAULT_DPI', 300))
    PDF_HYBRID_MAX_DPI = int(os.getenv('PDF_HYBRID_MAX_DPI', 600))
    PDF_HYBRID_DEFAULT_CHUNK_SIZE = int(os.getenv('PDF_HYBRID_DEFAULT_CHUNK_SIZE', 50))
    PDF_HYBRID_TEMP_DIR = os.getenv('PDF_HYBRID_TEMP_DIR', '/tmp/pdf_hybrid_uploads')
    PDF_HYBRID_TEXT_THRESHOLD = int(os.getenv('PDF_HYBRID_TEXT_THRESHOLD', 30))
    PDF_HYBRID_IMAGE_AREA_THRESHOLD = float(os.getenv('PDF_HYBRID_IMAGE_AREA_THRESHOLD', 0.0))

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Convert config to dictionary for health checks."""
        return {
            'host': cls.HOST,
            'port': cls.PORT,
            'debug': cls.DEBUG,
            'max_content_length': cls.MAX_CONTENT_LENGTH,
            'ocr_lang': cls.OCR_LANG,
            'use_gpu': cls.USE_GPU,
            'default_dpi': cls.DEFAULT_DPI,
            'max_workers': cls.MAX_WORKERS,
            'request_timeout': cls.REQUEST_TIMEOUT
        }


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    LOG_LEVEL = 'WARNING'
    # Use a more secure secret key for production (can be overridden via env)
    SECRET_KEY = os.getenv('SECRET_KEY', 'prod-secret-key-change-this-in-production')


# Configuration selector
def get_config() -> Config:
    """Get the appropriate configuration based on environment."""
    env = os.getenv('FLASK_ENV', 'development')

    if env == 'production':
        return ProductionConfig()
    else:
        return DevelopmentConfig()


# Global config instance
config = get_config()
