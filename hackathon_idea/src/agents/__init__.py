"""Agent framework for PlacePilot."""

from .base_agent import BaseAgent, StatefulAgent, AgentRegistry, agent_registry
from .supervisor_agent import SupervisorAgent
from .search_agent import SearchAgent
from .recommendation_agent import RecommendationAgent
from .data_management_agent import DataManagementAgent


def initialize_agents() -> None:
    """Initialize and register all agents."""
    
    # Create agent instances
    supervisor = SupervisorAgent()
    search = SearchAgent()
    recommendation = RecommendationAgent()
    data_management = DataManagementAgent()
    
    # Register agents
    agent_registry.register_agent(supervisor)
    agent_registry.register_agent(search)
    agent_registry.register_agent(recommendation)
    agent_registry.register_agent(data_management)


# Initialize agents when module is imported
initialize_agents()


__all__ = [
    "BaseAgent",
    "StatefulAgent", 
    "AgentRegistry",
    "agent_registry",
    "SupervisorAgent",
    "SearchAgent",
    "RecommendationAgent",
    "DataManagementAgent",
    "initialize_agents"
] 