#!/bin/bash

# Deployment script for AWS EC2
set -e

echo "🚀 Starting Foursquare Placemaker Bot deployment..."

# Update system packages
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker and Docker Compose if not installed
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Create logs directory
mkdir -p logs

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

# Pull latest images and build
echo "🔧 Building and starting services..."
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo "✅ Deployment successful!"
    echo "🌐 Your bot should be accessible at https://$(grep WEBAPP_DOMAIN .env | cut -d '=' -f2)"
    echo "📋 View logs with: docker-compose logs -f"
else
    echo "❌ Deployment failed. Check logs with: docker-compose logs"
    exit 1
fi 