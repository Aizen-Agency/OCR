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
- **🔒 Production Ready**: Security headers, rate limiting, API key authentication, Fail2ban protection, health checks, proper logging
- **🛡️ Security Hardened**: Redis authentication, attack pattern filtering, connection resilience
- **🐳 Container Ready**: Docker, docker compose with nginx reverse proxy
- **📈 Monitoring**: Comprehensive health checks, memory usage tracking, processing metrics
- **🔄 RESTful API**: Clean REST endpoints with standardized responses

> **🔐 Security**: See [SECURITY.md](SECURITY.md) for production security configuration and best practices.

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
- **API Key Authentication**: X-Auth-Token header required for all `/ocr/*` endpoints
- **Fail2ban Protection**: Automatic IP banning for authentication failures and rate limit violations

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
docker compose up --build

# For production with nginx reverse proxy
docker compose --profile production up --build
```

### VPS Deployment (8GB RAM)

Perfect for VPS providers like DigitalOcean, Linode, Vultr, etc.

```bash
# One-command deployment
./deploy-vps.sh

# Or manual setup
cp vps-config.env .env
docker compose up -d --build
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

The API provides RESTful endpoints organized by blueprints. 

**Base URLs:**
- Local development: `http://localhost:5000`
- Production: `https://api.eusdr.com` (or your configured domain)

### Quick Reference

| Endpoint | Method | Auth Required | Description |
|----------|--------|---------------|-------------|
| `/health` | GET | No | Comprehensive health check |
| `/health/ready` | GET | No | Readiness probe (Kubernetes) |
| `/health/alive` | GET | No | Liveness probe (Kubernetes) |
| `/ocr/image` | POST | Yes | Create OCR job for image |
| `/ocr/pdf` | POST | Yes | Create OCR job for PDF |
| `/ocr/batch` | POST | Yes | Create batch OCR jobs |
| `/ocr/job/{job_id}` | GET | Yes | Get OCR job status |
| `/ocr/job/{job_id}/result` | GET | Yes | Get OCR job result |
| `/pdf/hybrid-extract` | POST | Yes | Create hybrid PDF extraction job |
| `/pdf/job/{job_id}` | GET | Yes | Get hybrid PDF job status |
| `/pdf/job/{job_id}/result` | GET | Yes | Get hybrid PDF job result |

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
X-Auth-Token: your-api-token-here

file: <image_file>
```

**Note:** All `/ocr/*` endpoints require the `X-Auth-Token` header. Health endpoints (`/health/*`) do not require authentication.

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
X-Auth-Token: your-api-token-here

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

### PDF Hybrid Extraction Endpoints

The PDF Hybrid service intelligently processes PDFs by using direct text extraction for text-based pages and OCR for image-based pages. This provides the best of both worlds: fast text extraction for native text PDFs and accurate OCR for scanned/image-based PDFs.

#### Create Hybrid PDF Extraction Job
```http
POST /pdf/hybrid-extract
Content-Type: multipart/form-data
X-Auth-Token: your-api-token-here

file: <pdf_file>
```

**Query/Form Parameters:**
- `dpi` (optional): DPI for rendering image pages (72-600, default: 300)
- `chunk_size` (optional): Number of pages per processing chunk (default: 50)
- `max_pages` (optional): Maximum pages to process (default: 5000)

**Response (202 Accepted):**
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "processing",
  "filename": "document.pdf",
  "file_size": 2048000,
  "total_pages": 150,
  "chunk_size": 50,
  "processing_dpi": 300,
  "message": "Hybrid PDF extraction job created successfully. Use GET /pdf/job/{job_id} to check status."
}
```

**How it works:**
- Each page is classified as either "text" (native text) or "image" (scanned/image-based)
- Text pages: Direct text extraction (fast, no OCR)
- Image pages: OCR processing (accurate, slower)
- Pages are processed in parallel chunks for optimal performance

#### Get Hybrid PDF Job Status
```http
GET /pdf/job/{job_id}
```

**Response (200 OK - Completed):**
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "completed",
  "ready": true,
  "successful": true,
  "failed": false,
  "progress": {
    "total_pages": 150,
    "pages_processed": 150,
    "percentage": 100.0
  }
}
```

**Response (202 Accepted - Processing):**
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "processing",
  "ready": false,
  "progress": {
    "total_pages": 150,
    "pages_processed": 75,
    "percentage": 50.0
  }
}
```

#### Get Hybrid PDF Job Result
```http
GET /pdf/job/{job_id}/result
```

**Response (200 OK - Completed):**
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "completed",
  "pages": [
    {
      "page": 1,
      "type": "text",
      "text": "Page 1 native text content...",
      "blocks": [
        {
          "text": "Block text",
          "bbox": [[10, 20], [100, 20], [100, 40], [10, 40]],
          "type": "text"
        }
      ],
      "success": true,
      "extraction_method": "direct"
    },
    {
      "page": 2,
      "type": "image",
      "text": "Page 2 OCR extracted text...",
      "lines": [
        {
          "text": "OCR line text",
          "confidence": 0.987,
          "bbox": [[10, 20], [100, 20], [100, 40], [10, 40]]
        }
      ],
      "success": true,
      "extraction_method": "ocr"
    }
  ],
  "full_text": "Complete document text from all pages...",
  "total_pages": 150,
  "pages_processed": 150,
  "text_pages": 100,
  "image_pages": 50,
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
  "progress": {
    "total_pages": 150,
    "pages_processed": 75,
    "percentage": 50.0
  },
  "message": "Job is still processing. Please check status again later."
}
```

**Note:** All `/pdf/*` endpoints require the `X-Auth-Token` header, same as `/ocr/*` endpoints.

### API Key Authentication

All `/ocr/*` endpoints require API key authentication via the `X-Auth-Token` header. Health check endpoints (`/health/*`) are excluded for monitoring purposes.

**Set the API token:**
```bash
export AUTH_TOKEN="your-api-token-here"
```

**Example requests:**
```bash
# OCR Image
curl -X POST https://api.eusdr.com/ocr/image \
  -H "X-Auth-Token: your-api-token-here" \
  -F "file=@image.jpg"

# OCR PDF
curl -X POST https://api.eusdr.com/ocr/pdf \
  -H "X-Auth-Token: your-api-token-here" \
  -F "file=@document.pdf"

# Hybrid PDF Extraction
curl -X POST https://api.eusdr.com/pdf/hybrid-extract \
  -H "X-Auth-Token: your-api-token-here" \
  -F "file=@document.pdf" \
  -F "dpi=300"
```

**Error responses:**
- **401 Unauthorized**: Missing or invalid `X-Auth-Token` header
- **403 Forbidden**: Invalid API token

**Protected endpoints:**
- All `/ocr/*` endpoints require authentication
- All `/pdf/*` endpoints require authentication
- Health endpoints (`/health/*`) do NOT require authentication

See [SECURITY.md](SECURITY.md) for detailed authentication configuration.

### Rate Limiting

The API implements rate limiting using Redis. Default limit: **10 requests per minute per IP address**.

**Rate Limit Headers:**
- `X-RateLimit-Limit`: Maximum requests allowed per minute
- `X-RateLimit-Remaining`: Remaining requests in current window

### Fail2ban Protection

Fail2ban automatically bans IP addresses that show malicious behavior:
- **Authentication failures**: Bans IPs after 5 failed authentication attempts (401/403)
- **Rate limit violations**: Bans IPs after 10 rate limit violations (429)

Ban durations:
- Authentication failures: 1 hour
- Rate limit violations: 30 minutes

See `fail2ban/README.md` for management commands.

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

#### OCR Image Flow
```bash
# 1. Submit image for OCR
curl -X POST https://api.eusdr.com/ocr/image \
  -H "X-Auth-Token: your-api-token-here" \
  -F "file=@image.jpg"

# Response: {"job_id": "abc123", "status": "processing", ...}

# 2. Poll for status (optional)
curl https://api.eusdr.com/ocr/job/abc123 \
  -H "X-Auth-Token: your-api-token-here"

# 3. Get result when ready
curl https://api.eusdr.com/ocr/job/abc123/result \
  -H "X-Auth-Token: your-api-token-here"

# Response: {"status": "completed", "text": "...", "lines": [...], ...}
```

#### Hybrid PDF Extraction Flow
```bash
# 1. Submit PDF for hybrid extraction
curl -X POST https://api.eusdr.com/pdf/hybrid-extract \
  -H "X-Auth-Token: your-api-token-here" \
  -F "file=@document.pdf" \
  -F "dpi=300"

# Response: {"job_id": "xyz789", "status": "processing", "total_pages": 150, ...}

# 2. Poll for status (shows progress)
curl https://api.eusdr.com/pdf/job/xyz789 \
  -H "X-Auth-Token: your-api-token-here"

# Response: {"status": "processing", "progress": {"pages_processed": 75, "total_pages": 150, ...}}

# 3. Get result when ready
curl https://api.eusdr.com/pdf/job/xyz789/result \
  -H "X-Auth-Token: your-api-token-here"

# Response: {"status": "completed", "pages": [...], "full_text": "...", ...}
```

## Client Examples

### Python Client

```python
import requests

API_BASE = "https://api.eusdr.com"  # or http://localhost:5000 for local
API_TOKEN = "your-api-token-here"

headers = {"X-Auth-Token": API_TOKEN}

# Image OCR
files = {'file': open('image.jpg', 'rb')}
response = requests.post(f'{API_BASE}/ocr/image', files=files, headers=headers)
result = response.json()
job_id = result['job_id']

# Get OCR result
result_response = requests.get(f'{API_BASE}/ocr/job/{job_id}/result', headers=headers)
ocr_result = result_response.json()

# PDF OCR
files = {'file': open('document.pdf', 'rb')}
response = requests.post(f'{API_BASE}/ocr/pdf?dpi=300', files=files, headers=headers)
result = response.json()

# Hybrid PDF Extraction (recommended for mixed PDFs)
files = {'file': open('document.pdf', 'rb')}
data = {'dpi': 300, 'chunk_size': 50}
response = requests.post(f'{API_BASE}/pdf/hybrid-extract', files=files, data=data, headers=headers)
result = response.json()
job_id = result['job_id']

# Get hybrid PDF result
result_response = requests.get(f'{API_BASE}/pdf/job/{job_id}/result', headers=headers)
pdf_result = result_response.json()

# Batch processing
files = [
    ('files', ('image1.jpg', open('image1.jpg', 'rb'), 'image/jpeg')),
    ('files', ('document.pdf', open('document.pdf', 'rb'), 'application/pdf'))
]
response = requests.post(f'{API_BASE}/ocr/batch', files=files, headers=headers)
result = response.json()
```

### cURL Examples

```bash
# Set your API token
export API_TOKEN="your-api-token-here"
export API_BASE="https://api.eusdr.com"  # or http://localhost:5000 for local

# Health check (no auth required)
curl $API_BASE/health

# Image OCR
curl -X POST \
  -H "X-Auth-Token: $API_TOKEN" \
  -F "file=@image.jpg" \
  $API_BASE/ocr/image

# PDF OCR with custom DPI
curl -X POST \
  -H "X-Auth-Token: $API_TOKEN" \
  -F "file=@document.pdf" \
  "$API_BASE/ocr/pdf?dpi=150"

# Hybrid PDF Extraction (recommended)
curl -X POST \
  -H "X-Auth-Token: $API_TOKEN" \
  -F "file=@document.pdf" \
  -F "dpi=300" \
  $API_BASE/pdf/hybrid-extract

# Get job status
curl -X GET \
  -H "X-Auth-Token: $API_TOKEN" \
  $API_BASE/ocr/job/{job_id}

# Get job result
curl -X GET \
  -H "X-Auth-Token: $API_TOKEN" \
  $API_BASE/ocr/job/{job_id}/result
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
