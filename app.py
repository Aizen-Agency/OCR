"""
Flask OCR Microservice - Application Factory and Entry Point
"""

import os
import logging
from flask import Flask

from config import config, get_config
from routes.ocr import ocr_bp
from routes.health import health_bp
from routes.pdf_hybrid import pdf_hybrid_bp
from routes.monitoring import monitoring_bp
from middleware.error_handler import register_error_handlers
from middleware.rate_limiter import register_rate_limiter
from middleware.auth_middleware import register_auth_middleware
from services.ocr_service.ocr_service import OCRService
from services.redis_service import RedisService
from services.job_service import JobService
from utils.service_manager import get_service_manager

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
    app.config['AUTH_TOKEN'] = app_config.AUTH_TOKEN  # Store AUTH_TOKEN in app config for middleware access

    # Set up logging
    _setup_logging(app, app_config)

    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Register components
    _register_services(app)  # Must be first to initialize Redis/Celery
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_auth_middleware(app)  # Register API key authentication
    _register_rate_limiter(app)
    _register_cleanup_handlers(app)  # Register cleanup on shutdown

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
    app.register_blueprint(pdf_hybrid_bp)
    app.register_blueprint(monitoring_bp)

    logger = logging.getLogger(__name__)
    logger.info("Blueprints registered: health, ocr, pdf_hybrid, monitoring")


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
        # Use service manager for centralized service initialization
        # This ensures all services use shared instances and proper initialization
        service_manager = get_service_manager()
        
        # Initialize services via service manager (lazy initialization)
        redis_service = service_manager.get_redis_service()
        job_service = service_manager.get_job_service()
        ocr_service = service_manager.get_ocr_service()
        
        # Store service instances in app context for backward compatibility
        # Controllers now use service manager internally, but some code may still access app.ocr_service
        app.redis_service = redis_service
        app.job_service = job_service
        app.ocr_service = ocr_service
        
        if redis_service and redis_service.is_connected():
            logger.info("Redis service initialized and connected via ServiceManager")
        else:
            logger.warning("Redis service initialized but not connected - will work without caching")
        
        logger.info("Services initialized successfully via ServiceManager")

    except Exception as e:
        logger.error(f"Failed to initialize critical services: {str(e)}", exc_info=True)
        # Only raise for critical failures (OCR service)
        if 'ocr' in str(e).lower():
            raise
        logger.warning("Non-critical service initialization failed - continuing anyway")


def _register_auth_middleware(app: Flask) -> None:
    """
    Register API key authentication middleware.

    Args:
        app: Flask application instance
    """
    try:
        register_auth_middleware(app)
        logger.info("API key authentication middleware registered")
    except Exception as e:
        logger.warning(f"Failed to register auth middleware: {str(e)}")
        # Continue without authentication if there's an error


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


def _register_cleanup_handlers(app: Flask) -> None:
    """
    Register cleanup handlers for proper resource cleanup on shutdown.

    Args:
        app: Flask application instance
    """
    @app.teardown_appcontext
    def cleanup_on_request_end(error):
        """Cleanup resources at the end of each request context."""
        # Request-level cleanup if needed
        pass

    @app.teardown_request
    def cleanup_on_request(error):
        """Cleanup resources after each request."""
        # Request-level cleanup if needed
        pass

    # Ensure Celery result backend connection is established when Flask is ready
    # Use a thread to establish connection after Flask starts
    import threading
    def ensure_celery_backend_connection():
        """Ensure Celery result backend connection is established when Flask starts."""
        import time
        time.sleep(3)  # Wait for Flask to fully start
        try:
            from celery_app import celery_app
            backend = celery_app.backend
            if hasattr(backend, 'client'):
                # Force connection establishment
                backend.client.ping()
                logger.info("Celery result backend connection established")
        except Exception as e:
            logger.warning(f"Failed to establish Celery result backend connection: {str(e)}")
            # Connection will be retried automatically when needed
    
    # Start connection establishment in background thread
    _backend_thread = threading.Thread(target=ensure_celery_backend_connection, daemon=True)
    _backend_thread.start()

    # Note: For application-level cleanup (on shutdown), we rely on
    # __del__ methods in service classes, which are called when
    # Python garbage collects the objects. For explicit cleanup,
    # you can add signal handlers for SIGTERM/SIGINT if needed.
    logger.info("Cleanup handlers registered")


# Create default app instance for direct execution
app = create_app()


if __name__ == '__main__':
    # Run the Flask app using config
    app_config = get_config()
    logger = logging.getLogger(__name__)

    logger.info(f"Starting OCR microservice on {app_config.HOST}:{app_config.PORT} (debug={app_config.DEBUG})")
    app.run(host=app_config.HOST, port=app_config.PORT, debug=app_config.DEBUG)
