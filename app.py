"""
Flask OCR Microservice - Application Factory and Entry Point
"""

import os
import logging
from flask import Flask

from config import config, get_config
from routes.ocr import ocr_bp
from routes.health import health_bp
from middleware.error_handler import register_error_handlers
from middleware.rate_limiter import register_rate_limiter
from services.ocr_service.ocr_service import OCRService
from services.redis_service import RedisService
from services.job_service import JobService

logger = logging.getLogger(__name__)


def create_app(config_name: str = None) -> Flask:
    """
    Application factory function.

    Args:
        config_name: Configuration environment name

    Returns:
        Configured Flask application instance
    """
    # Determine configuration
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    # Get configuration object
    app_config = get_config()

    # Create Flask app instance
    app = Flask(__name__)

    # Configure app from config object
    app.config['SECRET_KEY'] = app_config.SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = app_config.MAX_CONTENT_LENGTH
    app.config['UPLOAD_FOLDER'] = app_config.UPLOAD_FOLDER

    # Set up logging
    _setup_logging(app, app_config)

    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Register components
    _register_services(app)  # Must be first to initialize Redis/Celery
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_rate_limiter(app)

    # Log app creation
    logger = logging.getLogger(__name__)
    logger.info(f"OCR Microservice created with config: {config_name}")
    logger.info(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    logger.info(f"Max content length: {app.config['MAX_CONTENT_LENGTH'] // (1024*1024)}MB")

    return app


def _setup_logging(app: Flask, app_config) -> None:
    """
    Set up logging configuration.

    Args:
        app: Flask application instance
        app_config: Configuration object
    """
    # Set logging level
    log_level = getattr(logging, app_config.LOG_LEVEL.upper(), logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=app_config.LOG_FORMAT,
        handlers=[
            logging.StreamHandler(),
            # Could add file handler here for production
        ]
    )

    # Reduce noise from third-party libraries
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('paddleocr').setLevel(logging.WARNING)


def _register_blueprints(app: Flask) -> None:
    """
    Register all blueprints with the application.

    Args:
        app: Flask application instance
    """
    app.register_blueprint(health_bp)
    app.register_blueprint(ocr_bp)

    logger = logging.getLogger(__name__)
    logger.info("Blueprints registered: health, ocr")


def _register_error_handlers(app: Flask) -> None:
    """
    Register error handlers with the application.

    Args:
        app: Flask application instance
    """
    register_error_handlers(app)

    logger = logging.getLogger(__name__)
    logger.info("Error handlers registered")


def _register_services(app: Flask) -> None:
    """
    Initialize and register services.

    Args:
        app: Flask application instance
    """
    logger = logging.getLogger(__name__)

    try:
        # Initialize Redis service
        redis_service = RedisService()
        app.redis_service = redis_service

        # Initialize Job service
        job_service = JobService()
        app.job_service = job_service

        # Initialize OCR service with PaddleOCR 3.x simplified API
        ocr_service = OCRService()
        ocr_config = get_config()
        
        # Initialize OCR with PaddleOCR 3.x supported parameters
        ocr_service.initialize_ocr(
            lang=ocr_config.OCR_LANG,
            use_gpu=ocr_config.USE_GPU,
            use_angle_cls=ocr_config.USE_ANGLE_CLS
        )

        # Store service instances in app context for access by controllers
        app.ocr_service = ocr_service

        logger.info("Services initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        raise


def _register_rate_limiter(app: Flask) -> None:
    """
    Register rate limiting middleware.

    Args:
        app: Flask application instance
    """
    try:
        register_rate_limiter(app, app.redis_service)
        logger.info("Rate limiting middleware registered")
    except Exception as e:
        logger.warning(f"Failed to register rate limiter: {str(e)}")
        # Continue without rate limiting if Redis is unavailable


# Create default app instance for direct execution
app = create_app()


if __name__ == '__main__':
    # Run the Flask app using config
    app_config = get_config()
    logger = logging.getLogger(__name__)

    logger.info(f"Starting OCR microservice on {app_config.HOST}:{app_config.PORT} (debug={app_config.DEBUG})")
    app.run(host=app_config.HOST, port=app_config.PORT, debug=app_config.DEBUG)
