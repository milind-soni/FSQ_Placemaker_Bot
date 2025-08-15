#!/usr/bin/env python3
"""
Telegram Bot launcher for PlacePilot - SIMPLIFIED VERSION
"""

import asyncio
import sys
import signal
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core import setup_logging, get_logger, init_db, close_db, settings
from src.integrations import telegram_client, openai_client, foursquare_client
from src.agents import agent_registry

logger = get_logger(__name__)


async def startup():
    """Initialize all components."""
    
    logger.info(f"🚀 Starting PlacePilot Bot v{settings.app_version}")
    logger.info(f"Environment: {settings.environment.value}")
    
    try:
        # Initialize database
        logger.info("📊 Initializing database...")
        await init_db()
        logger.info("✅ Database ready")
        
        # Initialize agents
        logger.info("🤖 Initializing agent system...")
        await agent_registry.initialize_all()
        logger.info(f"✅ {len(agent_registry.get_all_agents())} agents ready")
        
        # Health check external services (skip if test keys)
        if settings.api.openai_api_key != "test-key-not-real":
            logger.info("🔍 Checking external APIs...")
            
            try:
                openai_healthy = await openai_client.check_health()
                foursquare_healthy = await foursquare_client.check_health()
                
                logger.info(f"OpenAI API: {'✅' if openai_healthy else '❌'}")
                logger.info(f"Foursquare API: {'✅' if foursquare_healthy else '❌'}")
                
                if not openai_healthy and not foursquare_healthy:
                    logger.warning("⚠️ All external APIs unavailable - limited functionality")
                    
            except Exception as e:
                logger.warning(f"API health check failed: {e}")
        else:
            logger.info("⚠️ Using test API keys - full functionality unavailable")
        
        # Initialize Telegram client
        logger.info("📱 Initializing Telegram bot...")
        await telegram_client.initialize()
        logger.info("✅ Telegram bot ready")
        
        logger.info("🎉 PlacePilot Bot startup completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        return False


async def shutdown():
    """Cleanup all components."""
    
    logger.info("🛑 Shutting down PlacePilot Bot...")
    
    try:
        # Close Telegram client
        if telegram_client.application:
            await telegram_client.application.stop()
            await telegram_client.application.shutdown()
        logger.info("✅ Telegram bot closed")
        
        # Cleanup agents
        await agent_registry.cleanup_all()
        logger.info("✅ Agent system cleaned up")
        
        # Close external API clients
        await foursquare_client.close()
        logger.info("✅ API clients closed")
        
        # Close database
        await close_db()
        logger.info("✅ Database connections closed")
        
        logger.info("👋 PlacePilot Bot shutdown completed")
        
    except Exception as e:
        logger.error(f"❌ Shutdown error: {e}")


async def run_polling():
    """Run bot in polling mode."""
    
    logger.info("🔄 Starting bot in polling mode...")
    
    # Start the application
    await telegram_client.application.start()
    
    # Start polling
    await telegram_client.application.updater.start_polling()
    
    logger.info("✅ Bot is running in polling mode")
    
    # Keep running
    try:
        # Run forever until interrupted
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("👋 Polling cancelled")
    finally:
        # Stop polling
        await telegram_client.application.updater.stop()
        await telegram_client.application.stop()


async def run_webhook(webhook_url: str, port: int = 8443):
    """Run bot in webhook mode."""
    
    logger.info(f"🌐 Starting bot in webhook mode: {webhook_url}")
    
    # Start webhook server
    await telegram_client.start_webhook(webhook_url, port)


async def main():
    """Main application function."""
    
    # Setup logging
    setup_logging()
    
    # Display banner
    print("""
╔══════════════════════════════════════════════════════════════╗
║                  🤖 PlacePilot Bot                           ║
║             Your AI Location Companion                       ║
║                  Telegram Integration                        ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        # Startup
        startup_success = await startup()
        
        if not startup_success:
            logger.error("❌ Failed to start bot")
            return 1
        
        # Choose mode
        if settings.api.telegram_webhook_url:
            # Webhook mode
            print("\n🌐 Bot is running in webhook mode...")
            print("🛑 Press Ctrl+C to stop\n")
            
            webhook_port = int(settings.server.port)
            await run_webhook(settings.api.telegram_webhook_url, webhook_port)
            
        else:
            # Polling mode
            print("\n🔄 Bot is running in polling mode...")
            print("💡 Set TELEGRAM_WEBHOOK_URL for production webhook mode")
            print("🛑 Press Ctrl+C to stop\n")
            
            await run_polling()
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("👋 Received keyboard interrupt")
        return 0
    except Exception as e:
        logger.error(f"❌ Bot error: {e}")
        return 1
    finally:
        await shutdown()


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1) 