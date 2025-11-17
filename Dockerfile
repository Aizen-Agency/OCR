# SECURITY: Use specific Python version for reproducibility and security
# Use Python 3.9 slim image for smaller footprint
FROM python:3.9-slim

# Add metadata
LABEL maintainer="OCR Service Team" \
      description="Production-ready OCR microservice using PaddleOCR" \
      version="1.0.0"

# Create non-root user for security with home directory
RUN groupadd -r ocruser && \
    useradd -r -g ocruser -m -d /home/ocruser ocruser && \
    mkdir -p /home/ocruser/.paddlex && \
    chown -R ocruser:ocruser /home/ocruser

# Set working directory
WORKDIR /app

# SECURITY: Install system dependencies and security updates
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \
    curl \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# SECURITY: Install Python dependencies with pinned versions when possible
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip cache purge

# Copy application code with proper ownership
COPY --chown=ocruser:ocruser . .

# Copy and set up entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create upload directory with proper permissions
RUN mkdir -p /tmp/ocr_uploads && \
    chown -R ocruser:ocruser /tmp/ocr_uploads && \
    chmod 755 /tmp/ocr_uploads

# Keep as root for entrypoint (will switch to ocruser in entrypoint script)
# USER ocruser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_ENV=production \
    USE_PP_OCR_V5_SERVER=true \
    HOME=/home/ocruser

# Pre-download PP-OCRv5 models for faster startup (optional)
# Note: Models will be downloaded on first run and cached in /tmp
# Commented out during build to avoid build-time issues
# RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='en', show_log=False)" || true

# Expose port
EXPOSE 5000

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/health/ready || exit 1

# Use entrypoint to fix permissions before running command
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Run the application with proper signal handling
CMD ["python", "app.py"]
