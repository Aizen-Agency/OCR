#!/bin/bash

# Test OCR Server Locally
# Run after starting the server: ./test-local.sh

echo "🧪 Testing OCR Server Locally"
echo "============================="

BASE_URL="http://localhost:5000"

# Test 1: Health Check
echo "1️⃣ Testing Health Check..."
HEALTH_RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$BASE_URL/health")
HTTP_STATUS=$(echo "$HEALTH_RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
HEALTH_BODY=$(echo "$HEALTH_RESPONSE" | sed '/HTTP_STATUS:/d')

if [ "$HTTP_STATUS" -eq 200 ]; then
    echo "✅ Health check passed!"
    echo "📊 Status: $(echo $HEALTH_BODY | jq -r '.status' 2>/dev/null || echo 'OK')"
else
    echo "❌ Health check failed (HTTP $HTTP_STATUS)"
    echo "💡 Make sure server is running: python app.py"
    exit 1
fi

echo ""

# Test 2: API Info
echo "2️⃣ Checking API Information..."
echo "🌐 Server URL: $BASE_URL"
echo "📚 API Documentation: Check README.md"
echo ""

# Test 3: Check if endpoints are accessible
echo "3️⃣ Testing API Endpoints..."
ENDPOINTS=("/health" "/health/ready" "/health/alive")

for endpoint in "${ENDPOINTS[@]}"; do
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$endpoint")
    if [ "$RESPONSE" -eq 200 ]; then
        echo "✅ $endpoint - OK"
    else
        echo "❌ $endpoint - FAILED (HTTP $RESPONSE)"
    fi
done

echo ""

# Instructions for manual testing
echo "🎯 Manual Testing Instructions:"
echo "=============================="
echo ""
echo "📸 Test Image OCR:"
echo "curl -X POST -F \"file=@test-image.jpg\" $BASE_URL/ocr/image"
echo ""
echo "📄 Test PDF OCR:"
echo "curl -X POST -F \"file=@test-document.pdf\" $BASE_URL/ocr/pdf"
echo ""
echo "📦 Test Batch OCR:"
echo "curl -X POST -F \"files=@image1.jpg\" -F \"files=@document.pdf\" $BASE_URL/ocr/batch"
echo ""
echo "💡 Create test files:"
echo "  - Save any JPG/PNG image as 'test-image.jpg'"
echo "  - Save any PDF as 'test-document.pdf'"
echo "  - Run the curl commands above"
echo ""
echo "🎉 OCR server is ready for testing!"
