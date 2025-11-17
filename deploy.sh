#!/bin/bash
# OCR Microservice Deployment Script
# This script cleans up old Docker resources and deploys fresh containers

set -e  # Exit on any error

# Don't exit on error for cleanup commands (they may fail if nothing to clean)
set +e

echo "=========================================="
echo "OCR Microservice - Fresh Deployment"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if REDIS_PASSWORD is set
if [ -z "$REDIS_PASSWORD" ]; then
    echo -e "${YELLOW}Warning: REDIS_PASSWORD not set. Using default (INSECURE - change in production!)${NC}"
    export REDIS_PASSWORD="${REDIS_PASSWORD:-change-this-redis-password-in-production}"
fi

# Detect docker compose command (try V2 first, fallback to V1)
if command -v docker &> /dev/null && docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
    echo "Using Docker Compose V2 (docker compose)"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
    echo "Using Docker Compose V1 (docker-compose)"
else
    echo -e "${RED}Error: docker compose or docker-compose not found${NC}"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo ""
echo -e "${GREEN}Step 1: Stopping existing containers${NC}"
echo "----------------------------------------"
$DOCKER_COMPOSE --profile production down || true
echo "✓ Containers stopped"

echo ""
echo -e "${GREEN}Step 2: Cleaning up Docker resources${NC}"
echo "----------------------------------------"

# Remove old containers (if any)
echo "Removing old containers..."
$DOCKER_COMPOSE --profile production rm -f || true

# Remove old images (keeps space)
echo "Removing old OCR service images..."
# Use format to get only image IDs, handle errors gracefully
docker images --format "{{.ID}}" | while read -r img_id; do
    if docker inspect "$img_id" --format '{{.RepoTags}}' | grep -qE "paddleocr|ocr-microservice|ocr_server"; then
        docker rmi -f "$img_id" 2>/dev/null || true
    fi
done || true

# Prune unused Docker resources
echo "Pruning unused Docker resources..."
docker system prune -f || true

# Remove dangling images
echo "Removing dangling images..."
docker image prune -f || true

# Remove unused volumes (be careful - this removes all unused volumes)
echo "Removing unused volumes (except redis_data)..."
docker volume ls -q 2>/dev/null | grep -v redis_data | while read -r vol; do
    [ -n "$vol" ] && docker volume rm "$vol" 2>/dev/null || true
done

# Re-enable exit on error for critical steps
set -e

echo "✓ Cleanup completed"

echo ""
echo -e "${GREEN}Step 3: Building fresh images${NC}"
echo "----------------------------------------"
$DOCKER_COMPOSE --profile production build --no-cache
echo "✓ Images built successfully"

echo ""
echo -e "${GREEN}Step 4: Starting services${NC}"
echo "----------------------------------------"
$DOCKER_COMPOSE --profile production up -d
echo "✓ Services started"

echo ""
echo -e "${GREEN}Step 5: Waiting for services to be ready${NC}"
echo "----------------------------------------"
sleep 10

echo ""
echo -e "${GREEN}Step 6: Checking service status${NC}"
echo "----------------------------------------"
$DOCKER_COMPOSE --profile production ps

echo ""
echo -e "${GREEN}Step 7: Checking service health${NC}"
echo "----------------------------------------"
echo "Waiting for services to initialize..."
sleep 15

# Check if services are responding
echo "Checking OCR service health..."
if curl -f http://localhost/health/ready > /dev/null 2>&1; then
    echo -e "${GREEN}✓ OCR service is healthy${NC}"
else
    echo -e "${YELLOW}⚠ OCR service not ready yet (this is normal on first startup)${NC}"
    echo "   Check logs: $DOCKER_COMPOSE --profile production logs ocr-microservice"
fi

echo ""
echo -e "${GREEN}Step 8: Viewing logs${NC}"
echo "----------------------------------------"
echo "Recent logs (last 20 lines):"
$DOCKER_COMPOSE --profile production logs --tail=20

echo ""
echo "=========================================="
echo -e "${GREEN}Deployment Complete!${NC}"
echo "=========================================="
echo ""
echo "Useful commands:"
echo "  View logs:        $DOCKER_COMPOSE --profile production logs -f"
echo "  Check status:     $DOCKER_COMPOSE --profile production ps"
echo "  Stop services:    $DOCKER_COMPOSE --profile production down"
echo "  Restart service:  $DOCKER_COMPOSE --profile production restart <service-name>"
echo ""
echo "Service URLs:"
echo "  Health check:     http://localhost/health/ready"
echo "  OCR endpoint:     http://localhost/ocr/image"
echo ""

