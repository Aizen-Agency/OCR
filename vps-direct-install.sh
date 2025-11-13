#!/bin/bash

# Direct VPS Installation (No Docker)
# Alternative to Docker deployment

set -e

echo "🔧 Direct OCR Server Installation (No Docker)"
echo "=============================================="

# Check system resources
echo "📊 System Resources:"
echo "RAM: $(free -h | grep '^Mem:' | awk '{print $2}')"
echo "CPU Cores: $(nproc)"
echo "Disk: $(df -h / | tail -1 | awk '{print $4}') available"
echo ""

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 curl

# Create application directory
echo "📁 Setting up application directory..."
sudo mkdir -p /opt/ocr-server
sudo chown $USER:$USER /opt/ocr-server
cd /opt/ocr-server

# Copy application files (you need to upload them first)
echo "📋 Copying application files..."
# cp -r /path/to/uploaded/files/* .

# Create virtual environment
echo "🐍 Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Copy configuration
echo "⚙️ Setting up configuration..."
cp vps-config.env .env

# Create systemd service
echo "🔧 Creating systemd service..."
sudo tee /etc/systemd/system/ocr-server.service > /dev/null <<EOF
[Unit]
Description=OCR Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/ocr-server
Environment=PATH=/opt/ocr-server/venv/bin
ExecStart=/opt/ocr-server/venv/bin/python app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
echo "🚀 Starting OCR server service..."
sudo systemctl daemon-reload
sudo systemctl enable ocr-server
sudo systemctl start ocr-server

# Configure firewall
echo "🔥 Configuring firewall..."
sudo ufw allow 5000/tcp
sudo ufw --force enable

echo ""
echo "✅ Direct installation completed!"
echo ""
echo "🌐 Server URLs:"
echo "  - API: http://your-vps-ip:5000"
echo "  - Health Check: http://your-vps-ip:5000/health"
echo ""
echo "📊 Management commands:"
echo "  - Status: sudo systemctl status ocr-server"
echo "  - Logs: sudo journalctl -u ocr-server -f"
echo "  - Restart: sudo systemctl restart ocr-server"
echo "  - Stop: sudo systemctl stop ocr-server"
echo ""
echo "🎉 OCR server is now running directly on your VPS!"
