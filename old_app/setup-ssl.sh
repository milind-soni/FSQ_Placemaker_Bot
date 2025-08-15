#!/bin/bash

# SSL Setup Script for Foursquare Placemaker Bot
set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <domain-name>"
    echo "Example: $0 mybot.example.com"
    exit 1
fi

DOMAIN=$1

echo "🔒 Setting up SSL certificates for domain: $DOMAIN"

# Install certbot if not installed
if ! command -v certbot &> /dev/null; then
    echo "📦 Installing certbot..."
    sudo apt update
    sudo apt install -y certbot
fi

# Stop any running web servers that might conflict
echo "🛑 Stopping potential conflicting services..."
sudo systemctl stop apache2 2>/dev/null || true
sudo systemctl stop nginx 2>/dev/null || true
docker-compose down 2>/dev/null || true

# Get SSL certificate
echo "📜 Obtaining SSL certificate for $DOMAIN..."
sudo certbot certonly \
    --standalone \
    --preferred-challenges http \
    --agree-tos \
    --register-unsafely-without-email \
    -d $DOMAIN

# Create SSL directory and copy certificates
echo "📁 Setting up SSL directory..."
mkdir -p ssl
sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem ssl/
sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem ssl/
sudo chown -R $USER:$USER ssl/

# Update nginx configuration
echo "⚙️  Updating nginx configuration..."
sed -i "s/your-domain.com/$DOMAIN/g" nginx.conf

# Update environment file if it exists
if [ -f .env ]; then
    echo "🔧 Updating .env file..."
    sed -i "s/WEBAPP_DOMAIN=.*/WEBAPP_DOMAIN=$DOMAIN/" .env
else
    echo "⚠️  .env file not found. Please create it from .env.example"
fi

# Setup auto-renewal
echo "🔄 Setting up certificate auto-renewal..."
(sudo crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet --deploy-hook 'docker-compose restart nginx'") | sudo crontab -

echo "✅ SSL setup completed for $DOMAIN!"
echo "📝 Next steps:"
echo "   1. Make sure your domain DNS points to this server"
echo "   2. Configure your .env file"
echo "   3. Run: ./deploy.sh" 