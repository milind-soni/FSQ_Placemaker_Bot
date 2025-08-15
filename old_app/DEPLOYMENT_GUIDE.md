# 🚀 AWS EC2 Deployment Guide - Foursquare Placemaker Bot

## ✅ What Was Done

Your bot has been successfully prepared for production deployment! Here's what was updated:

### 📁 New Files Created
- `Dockerfile` - Container configuration
- `docker-compose.yml` - Multi-service orchestration
- `nginx.conf` - Reverse proxy and SSL termination
- `.env.example` - Environment variables template
- `deploy.sh` - One-click deployment script
- `setup-ssl.sh` - SSL certificate automation
- `placemaker-bot.service` - Systemd service (alternative to Docker)

### 🔧 Code Changes Made
- ✅ Removed hardcoded local IP addresses (`192.168.1.44:8000`)
- ✅ Added environment variable support
- ✅ Implemented webhook mode for production
- ✅ Added Flask web server for webapp hosting
- ✅ Added health check endpoint (`/health`)
- ✅ Maintained backward compatibility for local development

### 📦 Dependencies Added
- `flask==3.0.3` - Web server for webapp and webhooks
- `pydantic==2.10.4` - Data validation (was missing)

## 🎯 Quick Start (5 Minutes to Production!)

### 1. Prepare Your Server
```bash
# SSH into your EC2 instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# Clone the repository
git clone https://github.com/yourusername/foursquare-placemaker-bot.git
cd foursquare-placemaker-bot/old_app
```

### 2. Configure Environment
```bash
# Copy and edit environment variables
cp .env.example .env
nano .env
```

Fill in your values:
```env
TELEGRAM_BOT_TOKEN=1234567890:ABCDEF...
OPENAI_KEY=sk-...
FOURSQUARE_API_KEY=fsq_...
WEBAPP_DOMAIN=yourdomain.com
USE_WEBHOOK=true
```

### 3. Setup SSL (One Command!)
```bash
./setup-ssl.sh yourdomain.com
```

### 4. Deploy (One Command!)
```bash
./deploy.sh
```

Done! Your bot is now live at `https://yourdomain.com` 🎉

## 🔧 Architecture Overview

```
Internet → CloudFlare/Route53 → AWS EC2 → nginx → Docker Container
                                    ↓
                              [Placemaker Bot + WebApp]
                                    ↓
                          [Telegram Webhook + Health Check]
```

### Production Features
- **HTTPS/SSL Encryption** - Secure communication
- **Webhook Mode** - Better performance than polling
- **Health Monitoring** - `/health` endpoint for load balancers
- **Auto-Restart** - Docker restarts on failures
- **Log Management** - Centralized logging
- **Static File Serving** - Webapp served directly

## 📋 Pre-Deployment Checklist

### AWS EC2 Setup
- [ ] EC2 instance running (t2.medium+ recommended)
- [ ] Security group allows ports 80, 443, 22
- [ ] Elastic IP assigned (optional but recommended)

### Domain & DNS
- [ ] Domain name registered
- [ ] DNS A record points to your EC2 IP
- [ ] Domain resolves correctly (`dig yourdomain.com`)

### Bot Configuration
- [ ] Telegram bot token from @BotFather
- [ ] OpenAI API key
- [ ] Foursquare API key
- [ ] Bot commands configured in BotFather:
  ```
  start - Start the bot
  cancel - Cancel current operation
  ```

### SSL Certificate
- [ ] Port 80 accessible (for Let's Encrypt validation)
- [ ] No conflicting web servers running

## 🔍 Verification Steps

After deployment, verify everything is working:

```bash
# 1. Check services are running
docker-compose ps

# 2. Test health endpoint
curl https://yourdomain.com/health

# 3. Check bot webhook status
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo"

# 4. Test bot in Telegram
# Send /start to your bot
```

Expected responses:
- Health endpoint: `{"status": "healthy", "service": "placemaker-bot"}`
- Webhook info: Should show your domain with `pending_update_count: 0`
- Bot: Should respond with location/search options

## 🎛️ Management Commands

```bash
# View real-time logs
docker-compose logs -f

# Restart services
docker-compose restart

# Update and redeploy
git pull
docker-compose down
docker-compose up -d --build

# Check SSL certificate expiry
openssl x509 -noout -dates -in ssl/fullchain.pem
```

## 🆘 Troubleshooting

### Common Issues

**"Bot not responding"**
```bash
docker-compose logs placemaker-bot | tail -50
```

**"SSL certificate error"**
```bash
./setup-ssl.sh yourdomain.com
docker-compose restart nginx
```

**"Webhook not receiving updates"**
```bash
# Reset webhook
curl "https://api.telegram.org/bot<YOUR_TOKEN>/deleteWebhook"
docker-compose restart placemaker-bot
```

**"Memory issues"**
```bash
# Monitor resources
docker stats
free -h
```

## 💡 Production Tips

1. **Monitor Disk Space**: Set up alerts for `/var/lib/docker`
2. **SSL Renewal**: Certificates auto-renew via cron job
3. **Backup Strategy**: Regular backups of configuration files
4. **Log Rotation**: Docker handles this automatically
5. **Updates**: Keep dependencies updated regularly

## 🎉 Success!

Your Foursquare Placemaker Bot is now ready for production! The team can access it at:

- **Bot**: Search for your bot name in Telegram
- **WebApp**: `https://yourdomain.com`
- **Health Check**: `https://yourdomain.com/health`

Share the bot username with your team and they can start using it immediately! 🚀 