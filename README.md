# OCR Microservice

A production-grade Flask-based microservice for Optical Character Recognition (OCR) using PaddleOCR. Built with enterprise-level architecture patterns including blueprints, controllers, middleware, and comprehensive error handling.

## 🏗️ Architecture

This service follows a **layered architecture** with clear separation of concerns:

```
paddleocr/
├── app.py                    # Application factory & entry point
├── celery_app.py            # Celery configuration
├── config.py                 # Configuration management
├── controllers/              # Business logic layer
│   ├── health_controller.py  # Health check operations
│   └── ocr_controller.py     # OCR operations
├── routes/                   # Blueprint definitions (Express.js style routers)
│   ├── health.py            # Health check endpoints
│   └── ocr.py               # OCR endpoints
├── middleware/              # Cross-cutting concerns
│   ├── error_handler.py     # Centralized error handling
│   └── rate_limiter.py      # Rate limiting middleware
├── services/                # Service layer (domain logic)
│   ├── ocr_service/         # OCR processing service
│   ├── redis_service.py     # Redis caching & rate limiting
│   └── job_service.py       # Async job management
├── tasks/                   # Celery tasks
│   └── ocr_tasks.py         # Async OCR processing tasks
├── utils/                   # Shared utilities
│   └── response_formatter.py # Response standardization
└── requirements.txt         # Dependencies
```

## ✨ Features

- **🏆 PP-OCRv5_server_det**: Latest Baidu OCR model with state-of-the-art accuracy
- **🏢 Enterprise Architecture**: Blueprints, controllers, middleware pattern (similar to Express.js routers)
- **🔧 Application Factory**: Proper Flask app initialization with dependency injection
- **📊 Multi-format Support**: Process images (JPEG, PNG, BMP, TIFF, WebP, GIF) and PDF documents
- **⚡ High Performance**: Optimized for processing multiple pages with memory management
- **🔒 Production Ready**: Security headers, rate limiting, health checks, proper logging
- **🐳 Container Ready**: Docker, docker-compose with nginx reverse proxy
- **📈 Monitoring**: Comprehensive health checks, memory usage tracking, processing metrics
- **🔄 RESTful API**: Clean REST endpoints with standardized responses

## 🏭 Production Practices Applied

### **Architecture Patterns**
- **Blueprints**: Modular routing (like Express.js routers)
- **Controllers**: Business logic separation
- **Middleware**: Cross-cutting concerns (error handling, logging)
- **Application Factory**: Proper Flask initialization with dependency injection

### **Security & Reliability**
- **Non-root containers**: Docker runs as dedicated user
- **Input validation**: File type, size, and content validation
- **Error handling**: Centralized error responses with proper HTTP codes
- **Health checks**: Kubernetes-ready liveness/readiness probes
- **Rate limiting**: Redis-based distributed rate limiting

### **Performance & Monitoring**
- **Memory management**: Automatic garbage collection after requests
- **Processing metrics**: Time tracking for all operations
- **Resource limits**: Configurable memory and CPU limits
- **Structured logging**: Configurable log levels and formats
- **Health monitoring**: Memory usage and service status tracking


## 🚀 Quick Start

### Local Development

```bash
# Clone the repository
git clone <repository-url>
cd ocr-microservice

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp env.example .env
# Edit .env with your settings

# Run the service
python app.py
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build

# For production with nginx reverse proxy
docker-compose --profile production up --build
```

### VPS Deployment (8GB RAM)

Perfect for VPS providers like DigitalOcean, Linode, Vultr, etc.

```bash
# One-command deployment
./deploy-vps.sh

# Or manual setup
cp vps-config.env .env
docker-compose up -d --build
```

**VPS Resource Allocation:**
- **Memory:** 4GB limit, 1GB reserved (optimized for 8GB VPS)
- **CPU:** 2 cores limit, 1 core reserved
- **Concurrent Requests:** 10-15 simultaneous OCR operations

### Kubernetes Deployment

Use the included `k8s/` manifests for Kubernetes deployment with:
- Rolling updates
- Health checks
- Resource limits
- ConfigMaps for configuration
- Persistent volumes for uploads

## ⚙️ Configuration

The service uses environment-based configuration. Copy `env.example` to `.env` and customize:

| Category | Variable | Default | Description |
|----------|----------|---------|-------------|
| **Flask** | `FLASK_ENV` | development | Environment (development/production) |
| | `SECRET_KEY` | dev-secret-key | Flask secret key (change in production!) |
| | `DEBUG` | false | Enable debug mode |
| **Server** | `HOST` | 0.0.0.0 | Server bind address |
| | `PORT` | 5000 | Server port |
| **OCR** | `OCR_LANG` | en | OCR language |
| | `USE_GPU` | false | GPU mode (auto-detects CUDA) |
| **Files** | `MAX_CONTENT_LENGTH` | 52428800 | Max file size (50MB) |
| | `UPLOAD_FOLDER` | /tmp/ocr_uploads | Upload directory |
| **Limits** | `MAX_IMAGE_WIDTH` | 4096 | Max image width |
| | `MAX_IMAGE_HEIGHT` | 4096 | Max image height |
| | `MAX_PDF_PAGES` | 100 | Max PDF pages |
| **Performance** | `DEFAULT_DPI` | 300 | Default PDF DPI |
| | `MAX_DPI` | 600 | Maximum PDF DPI |
| | `REQUEST_TIMEOUT` | 300 | Request timeout (seconds) |
| **Logging** | `LOG_LEVEL` | INFO | Logging level |

Example:
```bash
export PORT=8000
export OCR_LANG=en
export USE_GPU=true
# For GPU usage, also set: export CUDA_VISIBLE_DEVICES=0
python app.py
```

**GPU Usage Note:** PaddleOCR auto-detects GPU availability. Set `CUDA_VISIBLE_DEVICES=0` (or your GPU ID) to enable GPU acceleration.

## 🔌 API Reference

The API provides RESTful endpoints organized by blueprints. Base URL: `http://localhost:5000`

### Health Endpoints

#### Comprehensive Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "OCR Microservice",
  "timestamp": "2025-01-13T10:30:00.000Z",
  "version": "1.0.0",
  "ocr_service": {
    "service": "OCR Service",
    "initialized": true,
    "paddleocr_available": true,
    "status": "healthy",
    "memory_usage": {
      "rss": 123456789,
      "vms": 234567890,
      "rss_mb": 117.8,
      "vms_mb": 223.7,
      "percent": 5.2
    }
  },
  "checks": {
    "ocr_service_initialized": true,
    "paddleocr_available": true,
    "memory_usage": {...},
    "configuration_loaded": true
  },
  "details": {
    "service_status": "operational",
    "recommendations": ["All systems operational."]
  }
}
```

#### Readiness Check (Kubernetes)
```http
GET /health/ready
```

#### Liveness Check (Kubernetes)
```http
GET /health/alive
```

### OCR Endpoints (Async Processing)

All OCR endpoints use asynchronous processing with Celery. You'll receive a `job_id` immediately and can poll for results.

#### Create Image OCR Job
```http
POST /ocr/image
Content-Type: multipart/form-data

file: <image_file>
```

**Response (202 Accepted):**
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "processing",
  "filename": "example.jpg",
  "file_size": 1024000,
  "message": "OCR job created successfully. Use GET /ocr/job/{job_id} to check status."
}
```

#### Create PDF OCR Job
```http
POST /ocr/pdf?dpi=300
Content-Type: multipart/form-data

file: <pdf_file>
```

**Query Parameters:**
- `dpi` (optional): DPI for PDF rendering (72-600, default: 300)

**Response (202 Accepted):**
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "processing",
  "filename": "document.pdf",
  "file_size": 2048000,
  "processing_dpi": 300,
  "message": "OCR job created successfully. Use GET /ocr/job/{job_id} to check status."
}
```

#### Create Batch OCR Jobs
```http
POST /ocr/batch
Content-Type: multipart/form-data

files: <multiple_files>
```

**Response (202 Accepted):**
```json
{
  "jobs": [
    {
      "filename": "image1.jpg",
      "job_id": "job-1-id",
      "status": "processing",
      "type": "image",
      "file_size": 1024000
    },
    {
      "filename": "document.pdf",
      "job_id": "job-2-id",
      "status": "processing",
      "type": "pdf",
      "file_size": 2048000
    }
  ],
  "summary": {
    "total_files": 2,
    "jobs_created": 2,
    "failed_files": 0,
    "success": true
  },
  "message": "Batch jobs created successfully. Use GET /ocr/job/{job_id} to check status for each job."
}
```

#### Get Job Status
```http
GET /ocr/job/{job_id}
```

**Response (200 OK - Completed):**
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "completed",
  "ready": true,
  "successful": true,
  "failed": false
}
```

**Response (202 Accepted - Processing):**
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "processing",
  "ready": false,
  "successful": null,
  "failed": null
}
```

#### Get Job Result
```http
GET /ocr/job/{job_id}/result
```

**Response (200 OK - Image Result):**
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "completed",
  "text": "Extracted text content...",
  "lines": [
    {
      "text": "Hello World",
      "confidence": 0.987,
      "bbox": [[10, 20], [100, 20], [100, 40], [10, 40]]
    }
  ],
  "success": true,
  "filename": "example.jpg",
  "file_size": 1024000,
  "cached": false
}
```

**Response (200 OK - PDF Result):**
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "completed",
  "pages": [
    {
      "page": 1,
      "text": "Page 1 content...",
      "lines": [...],
      "success": true
    }
  ],
  "full_text": "Complete document text...",
  "total_pages": 2,
  "success": true,
  "filename": "document.pdf",
  "file_size": 2048000,
  "processing_dpi": 300,
  "cached": false
}
```

**Response (202 Accepted - Still Processing):**
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "processing",
  "ready": false,
  "message": "Job is still processing. Please check status again later."
}
```

### Rate Limiting

The API implements rate limiting using Redis. Default limit: **10 requests per minute per IP address**.

**Rate Limit Headers:**
- `X-RateLimit-Limit`: Maximum requests allowed per minute
- `X-RateLimit-Remaining`: Remaining requests in current window

**Rate Limit Exceeded (429 Too Many Requests):**
```json
{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Limit: 10 per minute",
  "retry_after": 60,
  "remaining": 0
}
```

### Caching

OCR results are automatically cached in Redis based on file content hash. Identical files will return cached results instantly without re-processing.

- Cache TTL: 1 hour (configurable via `REDIS_CACHE_TTL`)
- Cache key includes file hash and DPI (for PDFs)
- Cached results include `"cached": true` in response

### Example: Complete Async Flow

```bash
# 1. Submit image for OCR
curl -X POST http://localhost:5000/ocr/image \
  -F "file=@image.jpg"

# Response: {"job_id": "abc123", "status": "processing", ...}

# 2. Poll for status (optional)
curl http://localhost:5000/ocr/job/abc123

# 3. Get result when ready
curl http://localhost:5000/ocr/job/abc123/result

# Response: {"status": "completed", "text": "...", "lines": [...], ...}
      "full_text": "PDF content...",
      "success": true,
      "file_size": 2048000,
      "processing_time_seconds": 4.56
    }
  ],
  "summary": {
    "total_files": 2,
    "processed_files": 2,
    "failed_files": 0,
    "success": true
  }
}
```

## Client Examples

### Python Client

```python
import requests

# Image OCR
files = {'file': open('image.jpg', 'rb')}
response = requests.post('http://localhost:5000/ocr/image', files=files)
result = response.json()

# PDF OCR
files = {'file': open('document.pdf', 'rb')}
response = requests.post('http://localhost:5000/ocr/pdf', files=files)
result = response.json()

# Batch processing
files = [
    ('files', ('image1.jpg', open('image1.jpg', 'rb'), 'image/jpeg')),
    ('files', ('document.pdf', open('document.pdf', 'rb'), 'application/pdf'))
]
response = requests.post('http://localhost:5000/ocr/batch', files=files)
result = response.json()
```

### cURL Examples

```bash
# Image OCR
curl -X POST -F "file=@image.jpg" http://localhost:5000/ocr/image

# PDF OCR with custom DPI
curl -X POST -F "file=@document.pdf" "http://localhost:5000/ocr/pdf?dpi=150"

# Health check
curl http://localhost:5000/health
```

## Error Handling

The API returns appropriate HTTP status codes and error messages:

- `200`: Success
- `400`: Bad Request (missing file, invalid parameters)
- `413`: File Too Large
- `422`: Processing Failed (OCR errors, invalid file format)
- `500`: Internal Server Error

Error response format:
```json
{
  "error": "Error type",
  "message": "Detailed error message",
  "filename": "optional_filename"
}
```

## Performance Optimization

### Memory Management
- Automatic garbage collection after each request
- Memory usage monitoring and reporting
- Efficient image processing with size limits

### Processing Limits
- Maximum file sizes (configurable)
- Image dimension limits to prevent memory issues
- PDF page limits for batch processing
- DPI validation for PDF processing

### Best Practices
- Process files sequentially to manage memory usage
- Use appropriate DPI settings (higher DPI = better accuracy but slower processing)
- Monitor memory usage via health check endpoint
- Scale horizontally for high-throughput requirements

## Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
```

Build and run:

```bash
docker build -t ocr-microservice .
docker run -p 5000:5000 ocr-microservice
```

## Architecture

```
ocr-microservice/
├── app.py                 # Flask application
├── config.py             # Configuration management
├── requirements.txt      # Python dependencies
├── services/
│   └── ocr_service/      # OCR business logic
│       ├── __init__.py
│       ├── ocr_service.py
│       └── helpers/      # Specialized helpers
│           ├── __init__.py
│           ├── image_processor.py
│           ├── pdf_processor.py
│           └── text_extractor.py
└── README.md
```

### Service Layer Architecture

- **OCR Service**: Main service orchestrating OCR operations
- **Image Processor**: Handles image validation, preprocessing, and format conversion
- **PDF Processor**: Manages PDF parsing and page extraction
- **Text Extractor**: Processes OCR results and extracts structured text data

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]
