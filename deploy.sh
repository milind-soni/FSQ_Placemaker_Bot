#!/bin/bash

# Deployment script for ngrok-based setup
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
    echo "⚠️  .env file not found. Please copy example-env to .env and configure it."
    exit 1
fi

# Export env vars
set -a
source .env
set +a

# Pull latest images and build
echo "🔧 Building and starting services..."
docker-compose down || true
docker-compose build --no-cache
docker-compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 8

# Try to discover ngrok public URL
NGROK_API="http://localhost:4040/api/tunnels"
PUBLIC_URL=""
for i in {1..30}; do
    if curl -sf "$NGROK_API" >/dev/null; then
        PUBLIC_URL=$(curl -s "$NGROK_API" | grep -oP '"public_url":"https://[^"]+' | head -n1 | cut -d '"' -f4)
        if [ -n "$PUBLIC_URL" ]; then
            break
        fi
    fi
    sleep 1
done

if [ -z "$PUBLIC_URL" ]; then
    echo "⚠️  Could not discover ngrok public URL from $NGROK_API."
    echo "   You can check manually at: http://localhost:4040"
else
    echo "🌐 ngrok URL: $PUBLIC_URL"
fi

# Auto-register Telegram webhook if possible and configured
if [ "${USE_WEBHOOK}" = "true" ] && [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$PUBLIC_URL" ]; then
    echo "🔗 Registering Telegram webhook..."
    set -e
    RES=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" -d "url=${PUBLIC_URL}${WEBHOOK_PATH}")
    echo "Telegram response: $RES"
else
    echo "ℹ️ Skipping webhook registration. Conditions not met (USE_WEBHOOK, token, or ngrok URL)."
fi

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo "✅ Deployment successful!"
    if [ -n "$PUBLIC_URL" ]; then
        echo "🌐 Your bot should be accessible via webhook at ${PUBLIC_URL}${WEBHOOK_PATH}"
    fi
    echo "📋 View logs with: docker-compose logs -f"
else
    echo "❌ Deployment failed. Check logs with: docker-compose logs"
    exit 1
fi 