"""
Configuration settings for the OCR microservice
"""

import os
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

    # Performance settings
    MAX_WORKERS = int(os.getenv('MAX_WORKERS', 4))  # For future async processing
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
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    REDIS_CACHE_TTL = int(os.getenv('REDIS_CACHE_TTL', 3600))  # 1 hour default

    # Celery configuration
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', os.getenv('REDIS_URL', 'redis://localhost:6379/0'))

    # Rate limiting configuration
    RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', 10))

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
