#!/bin/bash

# VPS OCR Server Monitoring Script
# Run: ./monitor-vps.sh

echo "📊 OCR Server VPS Monitoring (8GB RAM)"
echo "========================================"

# System Resources
echo "🖥️  System Resources:"
echo "RAM Usage: $(free -h | grep '^Mem:' | awk '{print $3 "/" $2}')"
echo "RAM Percent: $(free | grep Mem | awk '{printf "%.1f%", $3/$2 * 100.0}')"
echo "CPU Load: $(uptime | awk -F'load average:' '{ print $2 }' | cut -d, -f1)"
echo "Disk Usage: $(df -h / | tail -1 | awk '{print $5 " used (" $3 "/" $4 ")"}')"
echo ""

# Docker Status
echo "🐳 Docker Status:"
if docker-compose ps | grep -q "Up"; then
    echo "✅ Services: $(docker-compose ps --services --filter "status=running" | wc -l) running"
    docker-compose ps --services --filter "status=running"
else
    echo "❌ No services running"
fi
echo ""

# OCR Server Health
echo "🏥 OCR Server Health:"
if curl -s http://localhost:5000/health > /dev/null 2>&1; then
    HEALTH=$(curl -s http://localhost:5000/health)
    STATUS=$(echo $HEALTH | jq -r '.status')
    MEMORY=$(echo $HEALTH | jq -r '.ocr_service.memory_usage.rss_mb')

    echo "✅ Status: $STATUS"
    echo "🧠 Memory: ${MEMORY}MB"

    if (( $(echo "$MEMORY > 3500" | bc -l) )); then
        echo "⚠️  WARNING: High memory usage!"
    fi
else
    echo "❌ Server not responding"
fi
echo ""

# Recent Logs
echo "📝 Recent Application Logs:"
docker-compose logs --tail=5 ocr-microservice 2>/dev/null || echo "No recent logs"
echo ""

# Network Connections
echo "🌐 Active Connections:"
netstat -tlnp 2>/dev/null | grep :5000 || echo "Port 5000 not listening"
echo ""

# Performance Tips
echo "💡 Performance Tips:"
MEMORY_PERCENT=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')

if [ "$MEMORY_PERCENT" -gt 85 ]; then
    echo "⚠️  HIGH MEMORY: Consider reducing MAX_WORKERS or file sizes"
elif [ "$MEMORY_PERCENT" -gt 70 ]; then
    echo "⚠️  ELEVATED MEMORY: Monitor closely"
else
    echo "✅ Memory usage normal"
fi

# Check if GPU is available
if command -v nvidia-smi &> /dev/null; then
    echo "🎮 GPU available - consider enabling USE_GPU=true for better performance"
fi

echo ""
echo "🔄 Run this script anytime: ./monitor-vps.sh"
