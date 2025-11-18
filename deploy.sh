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

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo "Please create .env file from vps-config.env or env.example"
    echo "Example: cp vps-config.env .env"
    echo "Then edit .env with your actual credentials (REDIS_PASSWORD, AUTH_TOKEN, SECRET_KEY, etc.)"
    exit 1
fi

echo -e "${GREEN}✓ .env file found - Docker Compose will load all variables from .env${NC}"
echo "  All environment variables (REDIS_HOST, REDIS_PASSWORD, AUTH_TOKEN, etc.) will be loaded automatically"
echo "  No need to export variables manually - docker-compose handles it via env_file: .env"

# Source .env to get AUTH_TOKEN for example commands (optional - just for display)
# Docker Compose will load .env automatically, this is just for script display purposes
if [ -f ".env" ]; then
    # Safely source .env (only export variables, ignore comments and empty lines)
    set -a
    source .env 2>/dev/null || true
    set +a
fi

# Verify docker compose is available
if ! command -v docker &> /dev/null || ! docker compose version &> /dev/null 2>&1; then
    echo -e "${RED}Error: docker compose not found${NC}"
    echo "Please ensure Docker is installed and docker compose is available"
    exit 1
fi

echo "Using Docker Compose: docker compose"

echo ""
echo -e "${GREEN}Step 1: Stopping existing containers${NC}"
echo "----------------------------------------"
docker compose --profile production down || true
echo "✓ Containers stopped"

echo ""
echo -e "${GREEN}Step 2: Cleaning up Docker resources${NC}"
echo "----------------------------------------"

# Remove old containers (if any)
echo "Removing old containers..."
docker compose --profile production rm -f || true

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
echo "Removing unused volumes (except redis_data and fail2ban_data)..."
docker volume ls -q 2>/dev/null | grep -vE "redis_data|fail2ban_data" | while read -r vol; do
    [ -n "$vol" ] && docker volume rm "$vol" 2>/dev/null || true
done

# Re-enable exit on error for critical steps
set -e

echo "✓ Cleanup completed"

echo ""
echo -e "${GREEN}Step 3: Building fresh images${NC}"
echo "----------------------------------------"
docker compose --profile production build --no-cache
echo "✓ Images built successfully"

echo ""
echo -e "${GREEN}Step 4: Starting services${NC}"
echo "----------------------------------------"
docker compose --profile production up -d
echo "✓ Services started"

echo ""
echo -e "${GREEN}Step 5: Waiting for services to be ready${NC}"
echo "----------------------------------------"
sleep 10

echo ""
echo -e "${GREEN}Step 6: Checking service status${NC}"
echo "----------------------------------------"
docker compose --profile production ps

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
    echo "   Check logs: docker compose --profile production logs ocr-microservice"
fi

# Check Fail2ban status if running
echo "Checking Fail2ban status..."
if docker compose --profile production ps fail2ban 2>/dev/null | grep -q "Up"; then
    echo -e "${GREEN}✓ Fail2ban is running${NC}"
    echo "   Check banned IPs: docker exec ocr-fail2ban-1 fail2ban-client status nginx-auth"
else
    echo -e "${YELLOW}⚠ Fail2ban not running (check if it's in production profile)${NC}"
fi

echo ""
echo -e "${GREEN}Step 8: Viewing logs${NC}"
echo "----------------------------------------"
echo "Recent logs (last 20 lines):"
docker compose --profile production logs --tail=20

# Get server IP address
SERVER_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "YOUR_SERVER_IP")
if [ -z "$SERVER_IP" ] || [ "$SERVER_IP" = "YOUR_SERVER_IP" ]; then
    # Try alternative method
    SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s icanhazip.com 2>/dev/null || echo "YOUR_SERVER_IP")
fi

echo ""
echo "=========================================="
echo -e "${GREEN}Deployment Complete!${NC}"
echo "=========================================="
echo ""
echo "Useful commands:"
echo "  View logs:        docker compose --profile production logs -f"
echo "  Check status:     docker compose --profile production ps"
echo "  Stop services:    docker compose --profile production down"
echo "  Restart service:  docker compose --profile production restart <service-name>"
echo ""
echo "Security commands:"
echo "  Check Fail2ban:   docker exec ocr-fail2ban-1 fail2ban-client status nginx-auth"
echo "  View banned IPs: docker exec ocr-fail2ban-1 fail2ban-client status nginx-auth | grep 'Banned IP'"
echo "  Unban IP:         docker exec ocr-fail2ban-1 fail2ban-client set nginx-auth unbanip <IP>"
echo ""
echo "Service URLs (from server):"
echo "  Health check:     http://localhost/health/ready"
echo "  OCR endpoint:     http://localhost/ocr/image"
echo ""
if [ "$SERVER_IP" != "YOUR_SERVER_IP" ]; then
    echo -e "${GREEN}Service URLs (from external):${NC}"
    echo "  Health check:     http://${SERVER_IP}/health/ready"
    echo "  OCR endpoint:     http://${SERVER_IP}/ocr/image"
    echo ""
    echo -e "${YELLOW}⚠ IMPORTANT: OCR endpoints require X-Auth-Token header${NC}"
    echo "  Example: curl -X POST http://${SERVER_IP}/ocr/image \\"
    echo "    -H \"X-Auth-Token: ${AUTH_TOKEN}\" \\"
    echo "    -F \"file=@image.jpg\""
    echo ""
else
    echo -e "${YELLOW}Service URLs (from external):${NC}"
    echo "  Health check:     http://YOUR_SERVER_IP/health/ready"
    echo "  OCR endpoint:     http://YOUR_SERVER_IP/ocr/image"
    echo ""
    echo -e "${YELLOW}⚠ IMPORTANT: OCR endpoints require X-Auth-Token header${NC}"
    echo "  Example: curl -X POST http://YOUR_SERVER_IP/ocr/image \\"
    echo "    -H \"X-Auth-Token: ${AUTH_TOKEN}\" \\"
    echo "    -F \"file=@image.jpg\""
    echo ""
    echo -e "${YELLOW}To find your server IP, run: hostname -I or curl ifconfig.me${NC}"
fi
echo ""

