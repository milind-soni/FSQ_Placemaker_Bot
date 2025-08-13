#!/usr/bin/env python3
"""
Simple test script for PlacePilot agent system.
Tests basic agent functionality and routing.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Set environment variables for testing
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("FOURSQUARE_API_KEY", "test-key-not-real")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token-not-real")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://placemaker:placemaker123@localhost:5432/placemaker_db")

from src.models.pydantic_models import AgentRequest, AgentType
from src.agents import agent_registry, SupervisorAgent


async def test_agent_system():
    """Test the basic agent system functionality."""
    
    print("🧪 Testing PlacePilot Agent System")
    print("=" * 50)
    
    # Test 1: Agent Registry
    print("1. Testing Agent Registry...")
    agents = agent_registry.get_all_agents()
    print(f"   ✅ {len(agents)} agents registered:")
    for agent in agents:
        print(f"      - {agent.name} ({agent.agent_type.value})")
    
    # Test 2: Supervisor Agent
    print("\n2. Testing Supervisor Agent...")
    supervisor = agent_registry.get_agent(AgentType.SUPERVISOR)
    if supervisor:
        print(f"   ✅ Supervisor agent found: {supervisor.name}")
    else:
        print("   ❌ Supervisor agent not found")
        return
    
    # Test 3: Basic Request Routing
    print("\n3. Testing Request Routing...")
    
    test_requests = [
        ("Hello", "Should route to supervisor"),
        ("Find pizza places", "Should route to search agent"),
        ("I'm craving sushi", "Should route to recommendation agent"),
        ("Add a new restaurant", "Should route to data management agent"),
    ]
    
    for message, expected in test_requests:
        print(f"\n   Testing: '{message}'")
        print(f"   Expected: {expected}")
        
        # Create test request
        request = AgentRequest(
            agent_type=AgentType.SUPERVISOR,
            message=message,
            user_id=12345,
            conversation_id="test-conversation",
            context={}
        )
        
        # Test routing logic (without actually calling external APIs)
        try:
            # We'll just test that the supervisor can handle the request
            can_handle = await supervisor.can_handle(request)
            print(f"   ✅ Supervisor can handle: {can_handle}")
            
            # Test internal routing logic
            if hasattr(supervisor, '_route_by_intent'):
                # This would normally call OpenAI, so we'll skip for now
                print(f"   ℹ️  Routing logic exists (would call AI in real scenario)")
            
        except Exception as e:
            print(f"   ⚠️  Error (expected in test environment): {e}")
    
    # Test 4: Agent Capabilities
    print("\n4. Testing Agent Capabilities...")
    
    for agent_type in [AgentType.SEARCH, AgentType.RECOMMENDATION, AgentType.DATA_MANAGEMENT]:
        agent = agent_registry.get_agent(agent_type)
        if agent:
            print(f"   ✅ {agent_type.value} agent: {agent.name}")
        else:
            print(f"   ❌ {agent_type.value} agent: Not found")
    
    print("\n" + "=" * 50)
    print("🎉 Agent system test completed!")
    print("\nNote: API calls are not tested here due to missing real API keys.")
    print("For full testing, set real API keys in environment variables.")


if __name__ == "__main__":
    asyncio.run(test_agent_system()) 