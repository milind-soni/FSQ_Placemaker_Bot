# Foursquare Placemaker Telegram Bot 🗺️🤖

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Fused](https://img.shields.io/badge/Fused-udf-d1e550)](https://www.fused.io/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-✓-blue.svg)](https://core.telegram.org/bots/api)
[![Docker](https://img.shields.io/badge/Docker-compatible-blue.svg)](https://www.docker.com/)



A production-ready Telegram bot for the Foursquare Placemaker community that enables users to contribute to the global places database directly from their mobile devices. Now deployable on AWS EC2 with Docker support!

![Foursquare Placemaker Bot Banner](https://your-image-url-here.png)

## 🌟 About Foursquare Placemakers

> "Placemakers are the dedicated, passionate members of our global open source community who contribute to our shared understanding of places around the world. Welcome to our community of builders, developers, and local experts who help others unlock the best experiences, anywhere in the world."

This bot makes the process of adding and updating place data more accessible to the Placemaker community, allowing contributions from anywhere using Telegram.

## 🌆 Map Integration Web-App

The Mini App within the Telegram bot is served by [Fused](https://www.fused.io/):
1. Foursquare Location Data [UDF](https://github.com/fusedio/udfs/tree/main/public/Foursquare_Open_Source_Places)

## ✨ Features

- **Location-Based Entry**: Start by sharing your current location to add nearby places
- **Guided Place Submission**: Step-by-step process for complete place information
- **Category Selection**: Choose from common place categories or enter custom ones
- **Rich Place Attributes**: Add detailed information including:
  - Contact information (phone, website, email)
  - Operating hours
  - Chain status
  - Amenities (WiFi, parking, outdoor seating, etc.)
- **Photo Uploads**: Submit up to 3 photos of the place (storefront, interior, features)
- **Foursquare Map Integration**: Explore existing Foursquare location data through an embedded web app
- **Conversational Interface**: User-friendly keyboard buttons and inline options



## 🚀 Quick Deployment on AWS EC2

### Prerequisites

- AWS EC2 instance (t2.medium or larger recommended)
- Domain name with DNS pointed to your EC2 instance
- SSL certificate (Let's Encrypt recommended)
- A Telegram Bot Token from [@BotFather](https://t.me/botfather)
- OpenAI API Key
- Foursquare API Key

### One-Click Deployment

1. **SSH into your EC2 instance and clone the repository:**
   ```bash
   git clone https://github.com/yourusername/foursquare-placemaker-bot.git
   cd foursquare-placemaker-bot/old_app
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   nano .env
   ```
   
   Fill in your configuration:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   OPENAI_KEY=your_openai_api_key_here
   FOURSQUARE_API_KEY=your_foursquare_api_key_here
   WEBAPP_DOMAIN=yourdomain.com
   WEBAPP_PORT=8000
   USE_WEBHOOK=true
   WEBHOOK_PATH=/webhook
   ```

3. **Set up SSL certificates:**
   ```bash
   # Install certbot
   sudo apt install certbot
   
   # Get SSL certificate
   sudo certbot certonly --standalone -d yourdomain.com
   
   # Copy certificates to ssl directory
   sudo mkdir -p ssl
   sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/
   sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/
   sudo chown -R $USER:$USER ssl/
   ```

4. **Update nginx configuration:**
   ```bash
   sed -i 's/your-domain.com/yourdomain.com/g' nginx.conf
   ```

5. **Deploy with one command:**
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

That's it! Your bot will be live at `https://yourdomain.com` 🎉

## 🔧 Local Development

### Setup

1. **Clone and navigate:**
   ```bash
   git clone https://github.com/yourusername/foursquare-placemaker-bot.git
   cd foursquare-placemaker-bot/old_app
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure for local development:**
   ```bash
   cp .env.example .env
   nano .env
   ```
   
   Set `USE_WEBHOOK=false` for local development:
   ```env
   TELEGRAM_BOT_TOKEN=your_bot_token
   OPENAI_KEY=your_openai_key
   FOURSQUARE_API_KEY=your_foursquare_key
   WEBAPP_DOMAIN=localhost
   USE_WEBHOOK=false
   ```

4. **Start the local web server (in separate terminal):**
   ```bash
   python3 -m http.server 8000 --bind 0.0.0.0 --directory webapp
   ```

5. **Run the bot:**
   ```bash
   python conversational_search_bot.py
   ```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token from BotFather | - | ✅ |
| `OPENAI_KEY` | Your OpenAI API key | - | ✅ |
| `FOURSQUARE_API_KEY` | Your Foursquare API key | - | ✅ |
| `WEBAPP_DOMAIN` | Your domain name (no protocol) | `localhost` | ✅ |
| `WEBAPP_PORT` | Port for the web server | `8000` | ❌ |
| `USE_WEBHOOK` | Use webhook mode (true) or polling (false) | `false` | ❌ |
| `WEBHOOK_PATH` | Path for webhook endpoint | `/webhook` | ❌ |

### Deployment Modes

**Production (Webhook Mode):**
- Set `USE_WEBHOOK=true`
- Requires HTTPS domain
- Better performance and reliability
- Recommended for AWS EC2

**Development (Polling Mode):**
- Set `USE_WEBHOOK=false`
- Works with localhost
- Easier for testing
- Uses more resources

## 📱 Usage

1. Start a chat with your bot on Telegram
2. Use the `/start` command to begin
3. Choose to share your location or explore the Foursquare data
4. Follow the guided process to add a new place
5. Upload photos if available
6. Confirm the submission

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. Fork the repository
2. Create a new branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Commit your changes (`git commit -m 'Add some amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## 🔄 Workflow

The bot implements a conversation flow with 10 states:

1. LOCATION: User shares their location or accesses the web app
2. NAME: User enters the name of the place
3. CATEGORY: User selects or types a category
4. ADDRESS: User provides the full address
5. CONTACT: User enters contact information
6. HOURS: User specifies operating hours
7. CHAIN_STATUS: User indicates if the place is part of a chain
8. ATTRIBUTES: User selects applicable attributes
9. PHOTOS: User uploads photos (optional)
10. CONFIRM: User reviews and confirms the submission



## 🐳 Docker Commands

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild and restart
docker-compose down && docker-compose up -d --build
```

## 🔍 Monitoring & Troubleshooting

### Health Check
Your bot exposes a health endpoint at: `https://yourdomain.com/health`

### Common Issues

**Bot not responding:**
```bash
# Check if container is running
docker-compose ps

# Check logs
docker-compose logs placemaker-bot
```

**SSL Certificate Issues:**
```bash
# Renew certificates
sudo certbot renew

# Update certificates in container
sudo cp /etc/letsencrypt/live/yourdomain.com/*.pem ssl/
docker-compose restart
```

**Webhook not working:**
```bash
# Check webhook status
curl -X GET "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"

# Delete and reset webhook
curl -X GET "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/deleteWebhook"
docker-compose restart placemaker-bot
```

<p align="center">Made with ❤️ for the Placemaker community</p>
<p align="center">🚀 Ready for production deployment on AWS EC2!</p> 