#!/bin/bash

# OCR Server VPS Deployment Script
# Optimized for 8GB RAM VPS

set -e

echo "🚀 OCR Server VPS Deployment (8GB RAM Optimized)"
echo "================================================="

# Check system resources
echo "📊 System Resources:"
echo "RAM: $(free -h | grep '^Mem:' | awk '{print $2}')"
echo "CPU Cores: $(nproc)"
echo "Disk: $(df -h / | tail -1 | awk '{print $4}') available"
echo ""

# Update system
echo "🔄 Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker and Docker Compose
echo "🐳 Installing Docker and Docker Compose..."
sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker repository
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker compose-plugin

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add current user to docker group (optional)
sudo usermod -aG docker $USER

echo "✅ Docker installed successfully!"
echo ""

# Create deployment directory
echo "📁 Setting up deployment directory..."
mkdir -p ~/ocr-server
cd ~/ocr-server

# Download project files (you would replace this with your actual repo)
echo "📥 Downloading OCR server files..."
# wget https://github.com/your-repo/ocr-server/archive/main.zip
# unzip main.zip
# cd ocr-server-main

# For now, assuming files are already there
echo "📋 Copying VPS optimized configuration..."
cp vps-config.env .env

echo "🔧 Setting up firewall..."
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 5000/tcp
sudo ufw --force enable

echo "🚀 Starting OCR server..."
# docker compose up -d --build
docker compose --profile production up -d --build

echo ""
echo "✅ Deployment completed!"
echo ""
echo "🌐 Server URLs:"
echo "  - API: http://your-vps-ip:5000"
echo "  - Health Check: http://your-vps-ip:5000/health"
echo "  - Ready Check: http://your-vps-ip:5000/health/ready"
echo ""
echo "📊 Monitoring commands:"
echo "  - View logs: docker compose logs -f"
echo "  - Check status: docker compose ps"
echo "  - Restart: docker compose restart"
echo "  - Stop: docker compose down"
echo ""
echo "⚠️  Remember to:"
echo "  1. Update SECRET_KEY in .env"
echo "  2. Configure domain/reverse proxy if needed"
echo "  3. Set up SSL certificates"
echo "  4. Configure backup strategy"
echo ""
echo "🎉 OCR server is now running on your VPS!"
