# 🚀 Deployment Guide - Foursquare Placemaker Bot (ngrok-based)

## ✅ What's Included

- `Dockerfile` - Container configuration
- `docker-compose.yml` - Bot + ngrok services
- `deploy.sh` - One-command deployment (build, run, auto-register webhook)
- `example-env` - Environment variables template

## 🎯 Quick Start (5 Minutes)

### 1) Prepare your machine (local or server)
```bash
# Ensure Docker & Docker Compose are installed
# Then clone the repository
git clone https://github.com/yourusername/foursquare-placemaker-bot.git
cd foursquare-placemaker-bot
```

### 2) Configure environment
```bash
cp example-env .env
nano .env
```

Fill in your values:
```env
TELEGRAM_BOT_TOKEN=1234567890:ABCDEF...
OPENAI_KEY=sk-...
FOURSQUARE_API_KEY=fsq_...
NGROK_AUTHTOKEN=your-ngrok-auth-token
WEBAPP_PORT=8000
USE_WEBHOOK=true
WEBHOOK_PATH=/webhook
AUTO_SET_WEBHOOK=true
```

### 3) Deploy (one command)
```bash
chmod +x deploy.sh
./deploy.sh
```

The script will:
- Start the bot container and an ngrok tunnel
- Discover the public `https://*.ngrok.io` URL
- Automatically register your Telegram webhook to `https://<ngrok>/webhook`

### 4) Verify
```bash
# Check services are running
docker-compose ps

# View bot logs
docker-compose logs -f placemaker-bot | cat

# View ngrok dashboard
open http://localhost:4040

# Check webhook status
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" | jq
```

Expected responses:
- Webhook info should show your ngrok URL with `pending_update_count: 0`
- Bot should respond to `/start` in Telegram

## 🔧 Architecture

```
Internet → ngrok (container) → Docker network → placemaker-bot (Flask + Telegram webhook)
```

- No nginx / custom domain / SSL certificates needed
- HTTPS provided by ngrok

## 🎛️ Common Commands

```bash
# Start services
docker-compose up -d --build

# Stop services
docker-compose down

# Logs
docker-compose logs -f placemaker-bot | cat
docker-compose logs -f placemaker-ngrok | cat
```

## 🆘 Troubleshooting

- Webhook not set after deploy:
  - Ensure `.env` has `USE_WEBHOOK=true`, `AUTO_SET_WEBHOOK=true`, and valid `TELEGRAM_BOT_TOKEN`
  - Confirm ngrok dashboard is available at `http://localhost:4040`
  - Manually set webhook:
    ```bash
    curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" -d "url=$(curl -s http://localhost:4040/api/tunnels | grep -oP '"public_url":"https://[^\"]+' | head -n1 | cut -d '"' -f4)/webhook"
    ```

- Switch to polling (no webhook/tunnel):
  - Set `USE_WEBHOOK=false` in `.env` and restart containers
