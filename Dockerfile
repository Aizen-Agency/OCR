# Use Python 3.9 slim image for smaller footprint
FROM python:3.9-slim

# Add metadata
LABEL maintainer="OCR Service Team" \
      description="Production-ready OCR microservice using PaddleOCR" \
      version="1.0.0"

# Create non-root user for security
RUN groupadd -r ocruser && useradd -r -g ocruser ocruser

# Set working directory
WORKDIR /app

# Install system dependencies for PaddleOCR
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code with proper ownership
COPY --chown=ocruser:ocruser . .

# Create upload directory with proper permissions
RUN mkdir -p /tmp/ocr_uploads && \
    chown -R ocruser:ocruser /tmp/ocr_uploads && \
    chmod 755 /tmp/ocr_uploads

# Switch to non-root user
USER ocruser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_ENV=production \
    USE_PP_OCR_V5_SERVER=true

# Pre-download PP-OCRv5 models for faster startup (optional)
# This will cache the models in the Docker layer
RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='en', show_log=False)" || true

# Expose port
EXPOSE 5000

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/health/ready || exit 1

# Run the application with proper signal handling
CMD ["python", "app.py"]
