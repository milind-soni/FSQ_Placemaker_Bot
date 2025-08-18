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
from src.agents import agent_registry, initialize_agents
from src.models.pydantic_models import AgentRequest, AgentType

logger = get_logger(__name__)


async def startup():
    """Initialize application components."""
    logger.info(f"Starting PlacePilot v{settings.app_version}")
    logger.info(f"Environment: {settings.environment.value}")
    
    try:
        # Initialize database
        logger.info("Initializing database...")
        await init_db()
        logger.info("✅ Database initialized")
        
        # Initialize agents
        logger.info("Initializing agent system...")
        await agent_registry.initialize_all()
        logger.info(f"✅ {len(agent_registry.get_all_agents())} agents initialized")
        
        # List registered agents
        for agent in agent_registry.get_all_agents():
            logger.info(f"   - {agent.name} ({agent.agent_type.value})")
        
        # Health check external services (only if API keys are real)
        if settings.api.openai_api_key != "test-key-not-real":
            logger.info("Checking external API health...")
            
            openai_healthy = await openai_client.check_health()
            foursquare_healthy = await foursquare_client.check_health()
            
            logger.info(f"OpenAI API health: {'✅' if openai_healthy else '❌'}")
            logger.info(f"Foursquare API health: {'✅' if foursquare_healthy else '❌'}")
            
            if not openai_healthy or not foursquare_healthy:
                logger.warning("Some external services are not healthy")
        else:
            logger.info("Skipping API health checks (test environment)")
        
        logger.info("🚀 PlacePilot started successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to start PlacePilot: {e}")
        raise


async def shutdown():
    """Cleanup application components."""
    logger.info("Shutting down PlacePilot...")
    
    try:
        # Cleanup agents
        await agent_registry.cleanup_all()
        logger.info("✅ Agent system cleaned up")
        
        # Close database connections
        await close_db()
        logger.info("✅ Database connections closed")
        
        # Close HTTP clients
        await foursquare_client.close()
        logger.info("✅ HTTP clients closed")
        
        logger.info("👋 PlacePilot shut down successfully")
        
    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}")


async def demo_conversation():
    """Run a demo conversation to show agent system in action."""
    
    logger.info("🎭 Running demo conversation...")
    
    # Get supervisor agent
    supervisor = agent_registry.get_agent(AgentType.SUPERVISOR)
    if not supervisor:
        logger.error("Supervisor agent not found")
        return
    
    # Demo messages
    demo_messages = [
        "Hello! What can you do?",
        "I'm looking for coffee shops nearby",
        "I want to add a new restaurant",
        "Help me find the best pizza in town"
    ]
    
    for i, message in enumerate(demo_messages, 1):
        print(f"\n{'='*60}")
        print(f"Demo Message {i}: '{message}'")
        print("="*60)
        
        # Create request
        request = AgentRequest(
            agent_type=AgentType.SUPERVISOR,
            message=message,
            user_id=12345,
            conversation_id="demo-conversation",
            context={"latitude": 40.7128, "longitude": -74.0060}  # NYC coordinates
        )
        
        try:
            # Process request
            response = await supervisor.process_request(request)
            
            print(f"Agent: {response.agent_type.value}")
            print(f"Confidence: {response.confidence}")
            print(f"Response: {response.response}")
            
            if response.next_agent:
                print(f"Next Agent Suggested: {response.next_agent.value}")
            
            if response.actions:
                print(f"Actions: {len(response.actions)} available")
            
        except Exception as e:
            print(f"❌ Error processing message: {e}")
    
    print(f"\n{'='*60}")
    logger.info("🎉 Demo conversation completed!")


async def main():
    """Main application function."""
    try:
        # Setup logging first
        setup_logging()
        
        # Display startup banner
        print("""
╔══════════════════════════════════════════════════════════════╗
║                      🤖 PlacePilot                         ║
║                Your AI Location Companion                  ║
╚══════════════════════════════════════════════════════════════╝
""")
        
        # Start application
        startup_success = await startup()
        
        if not startup_success:
            logger.error("Failed to start application")
            return
        
        # Check if we should run in demo mode
        if len(sys.argv) > 1 and sys.argv[1] == "--demo":
            await demo_conversation()
        else:
            # Production mode - keep running
            logger.info("Application is running. Press Ctrl+C to stop.")
            print("\n🔄 PlacePilot is ready!")
            print("💡 Run with '--demo' flag to see agent system in action")
            print("🛑 Press Ctrl+C to stop\n")
            
            # Keep running until interrupted
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
        
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise
    finally:
        await shutdown()


if __name__ == "__main__":
    asyncio.run(main()) 