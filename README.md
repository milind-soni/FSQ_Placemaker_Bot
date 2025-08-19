# Foursquare Placemaker Telegram Bot 🗺️🤖

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Fused](https://img.shields.io/badge/Fused-udf-d1e550)](https://www.fused.io/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-✓-blue.svg)](https://core.telegram.org/bots/api)
[![Docker](https://img.shields.io/badge/Docker-compatible-blue.svg)](https://www.docker.com/)


A production-ready Telegram bot for the Foursquare Placemaker community that enables users to contribute to the global places database directly from their mobile devices. Now with one-command setup using ngrok (no custom domain or SSL required).

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
- **Auto-ngrok + Auto-webhook**: Tunnel and webhook are configured automatically by Docker

## 🚀 Quick Start (ngrok, no SSL)

### Prerequisites

- Docker & Docker Compose
- A Telegram Bot Token from [@BotFather](https://t.me/botfather)
- OpenAI API Key
- Foursquare API Key
- ngrok account (to obtain `NGROK_AUTHTOKEN`)

### One-Command Deployment

1. Clone the repo and navigate:
```bash
git clone https://github.com/yourusername/foursquare-placemaker-bot.git
cd foursquare-placemaker-bot
```

2. **Configure environment variables:**
```bash
cp example-env .env
nano .env
```

Fill in your configuration:
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OPENAI_KEY=your_openai_api_key_here
FOURSQUARE_API_KEY=your_foursquare_api_key_here
NGROK_AUTHTOKEN=your_ngrok_authtoken
WEBAPP_PORT=8000
USE_WEBHOOK=true
WEBHOOK_PATH=/webhook
AUTO_SET_WEBHOOK=true

# Optional: Structured logging
APP_ENV=dev
SERVICE_NAME=conversation_bot
LOG_LEVEL=INFO
LOG_TO_FILE=false
LOG_FILE=logs/placemaker_bot.log
LOG_ROTATE_WHEN=midnight
LOG_ROTATE_INTERVAL=1
LOG_BACKUP_COUNT=7
```

3. Deploy with one command:
```bash
chmod +x deploy.sh
./deploy.sh
```

The script will:
- Start the bot and an ngrok tunnel (Docker Compose)
- Discover the public `https://*.ngrok.io` URL
- Automatically register your Telegram webhook to `https://<ngrok>/webhook`

To view the ngrok dashboard: `http://localhost:4040`

## 🔧 Local Development

You can also run without webhooks using polling:

1. Set in `.env`:
```env
USE_WEBHOOK=false
```

2. Start containers (ngrok service is optional in this mode):
```bash
docker-compose up -d --build
```

The bot will use long polling; ngrok/webhook is not required.

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token from BotFather | - | ✅ |
| `OPENAI_KEY` | Your OpenAI API key | - | ✅ |
| `FOURSQUARE_API_KEY` | Your Foursquare API key | - | ✅ |
| `NGROK_AUTHTOKEN` | ngrok auth token (enables public https URL) | - | ✅ (webhook mode) |
| `WEBAPP_PORT` | Port for the Flask web server | `8000` | ❌ |
| `USE_WEBHOOK` | Use webhook mode (true) or polling (false) | `true` | ❌ |
| `WEBHOOK_PATH` | Path for webhook endpoint | `/webhook` | ❌ |
| `AUTO_SET_WEBHOOK` | Auto-discover ngrok URL and set webhook | `true` | ❌ |
| `APP_ENV` | Deployment environment name for logs | `dev` | ❌ |
| `SERVICE_NAME` | Service name added to logs | `conversation_bot` | ❌ |
| `LOG_LEVEL` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` | ❌ |
| `LOG_TO_FILE` | Enable file logging in addition to stdout | `false` | ❌ |
| `LOG_FILE` | File path for logs when `LOG_TO_FILE=true` | `logs/placemaker_bot.log` | ❌ |
| `LOG_ROTATE_WHEN` | Rotation schedule for logs | `midnight` | ❌ |
| `LOG_ROTATE_INTERVAL` | Rotation interval (units depend on `when`) | `1` | ❌ |
| `LOG_BACKUP_COUNT` | Number of rotated files to keep | `7` | ❌ |

## 📱 Usage

1. Start a chat with your bot on Telegram
2. Use the `/start` command to begin
3. Share your location or explore the Foursquare data
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

- Health endpoint (inside the tunnel): `GET /health`
- ngrok dashboard: `http://localhost:4040`
- Logs are JSON-formatted to stdout by default; enable file logging with rotation via `LOG_TO_FILE=true` and `LOG_FILE`/rotation vars
- Correlated requests: send `X-Request-ID` header to the webhook, or a UUID will be generated and included in responses
- Check webhook status:
  ```bash
  curl -X GET "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
  ```
- Reset webhook:
  ```bash
  curl -X GET "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/deleteWebhook"
  ```

<p align="center">Made with ❤️ for the Placemaker community</p>
<p align="center">🚀 ngrok-enabled, one-command setup!</p> 