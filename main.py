"""
Main entry point for PlacePilot application.
Initializes all components and starts the application.
"""

import asyncio
import sys
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core import setup_logging, get_logger, init_db, close_db, settings
from src.integrations import openai_client, foursquare_client
from src.agents import agent_registry

logger = get_logger(__name__)


async def startup():
    """Initialize application components."""
    logger.info("Starting PlacePilot application")
    
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")
        
        # Initialize agents
        await agent_registry.initialize_all()
        logger.info("Agent system initialized")
        
        # Health check external services
        openai_healthy = await openai_client.check_health()
        foursquare_healthy = await foursquare_client.check_health()
        
        logger.info(f"OpenAI API health: {openai_healthy}")
        logger.info(f"Foursquare API health: {foursquare_healthy}")
        
        if not openai_healthy or not foursquare_healthy:
            logger.warning("Some external services are not healthy")
        
        logger.info("PlacePilot started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start PlacePilot: {e}")
        raise


async def shutdown():
    """Cleanup application components."""
    logger.info("Shutting down PlacePilot application")
    
    try:
        # Cleanup agents
        await agent_registry.cleanup_all()
        logger.info("Agent system cleaned up")
        
        # Close database connections
        await close_db()
        logger.info("Database connections closed")
        
        # Close HTTP clients
        await foursquare_client.close()
        logger.info("HTTP clients closed")
        
        logger.info("PlacePilot shut down successfully")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


async def main():
    """Main application function."""
    try:
        # Setup logging first
        setup_logging()
        
        # Start application
        await startup()
        
        # Keep running
        logger.info("Application is running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Application error: {e}")
    finally:
        await shutdown()


if __name__ == "__main__":
    asyncio.run(main()) 