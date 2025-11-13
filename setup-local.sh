#!/bin/bash

# Local Development Setup for OCR Server
# Run: ./setup-local.sh

echo "🔧 Setting up OCR Server for Local Development"
echo "=============================================="

# Check Python version
echo "🐍 Checking Python version..."
python3 --version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

# Check system resources
echo "📊 System Resources:"
echo "RAM: $(free -h 2>/dev/null | grep '^Mem:' | awk '{print $2}' || echo 'N/A')"
echo "CPU Cores: $(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 'N/A')"
echo ""

# Create virtual environment
echo "🐍 Creating virtual environment..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "❌ Failed to create virtual environment. Install python3-venv:"
    echo "  Ubuntu/Debian: sudo apt-get install python3-venv"
    echo "  macOS: pip install virtualenv"
    exit 1
fi

# Activate virtual environment
echo "🚀 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📦 Installing dependencies (this may take several minutes)..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    echo "💡 Try installing system dependencies first:"
    echo "  Ubuntu/Debian:"
    echo "    sudo apt-get update"
    echo "    sudo apt-get install libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1"
    echo "  macOS:"
    echo "    brew install libglib2 libsm libxext xrender gcc"
    exit 1
fi

# Copy environment configuration
echo "⚙️ Setting up configuration..."
cp env.example .env

echo ""
echo "✅ Local setup completed!"
echo ""
echo "🚀 To start the server:"
echo "  source venv/bin/activate"
echo "  python app.py"
echo ""
echo "🌐 Server will be available at:"
echo "  - API: http://localhost:5000"
echo "  - Health Check: http://localhost:5000/health"
echo ""
echo "🛑 To stop the server: Ctrl+C"
echo ""
echo "📝 Useful commands:"
echo "  - View logs: (server will show logs in terminal)"
echo "  - Test API: curl http://localhost:5000/health"
echo "  - Stop server: Ctrl+C"
echo ""
echo "🎉 Ready to test your OCR server locally!"
