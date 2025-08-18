"""
Base agent class for PlacePilot agentic AI system.
Defines the interface and common functionality for all specialized agents.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
import uuid

from ..core.logging import LoggerMixin
from ..models.pydantic_models import AgentRequest, AgentResponse, AgentType
from ..core.exceptions import AgentError


class BaseAgent(LoggerMixin, ABC):
    """Base class for all PlacePilot agents."""
    
    def __init__(self, agent_type: AgentType, name: str):
        self.agent_type = agent_type
        self.name = name
        self.session_id: Optional[str] = None
        self.started_at: Optional[datetime] = None
        
    @abstractmethod
    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """Process an incoming request and return a response."""
        pass
    
    @abstractmethod
    async def can_handle(self, request: AgentRequest) -> bool:
        """Check if this agent can handle the given request."""
        pass
    
    async def initialize(self) -> None:
        """Initialize the agent (called before first use)."""
        self.logger.info(f"Initializing agent: {self.name}")
        
    async def cleanup(self) -> None:
        """Cleanup resources when agent is no longer needed."""
        self.logger.info(f"Cleaning up agent: {self.name}")
    
    def start_session(self, conversation_id: str) -> str:
        """Start a new agent session."""
        self.session_id = f"{self.name}_{conversation_id}_{uuid.uuid4().hex[:8]}"
        self.started_at = datetime.utcnow()
        
        self.log_with_context(
            "info", 
            f"Started agent session",
            agent_name=self.name,
            session_id=self.session_id,
            conversation_id=conversation_id
        )
        
        return self.session_id
    
    def end_session(self) -> Optional[Dict[str, Any]]:
        """End the current agent session and return metrics."""
        if not self.session_id or not self.started_at:
            return None
            
        ended_at = datetime.utcnow()
        duration = (ended_at - self.started_at).total_seconds() * 1000  # milliseconds
        
        metrics = {
            "session_id": self.session_id,
            "agent_name": self.name,
            "started_at": self.started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "duration_ms": int(duration)
        }
        
        self.log_with_context(
            "info",
            f"Ended agent session",
            agent_name=self.name,
            session_id=self.session_id,
            duration_ms=int(duration)
        )
        
        # Reset session
        self.session_id = None
        self.started_at = None
        
        return metrics
    
    async def handle_error(self, error: Exception, request: AgentRequest) -> AgentResponse:
        """Handle errors that occur during request processing."""
        error_msg = f"Agent {self.name} encountered an error: {str(error)}"
        
        self.log_with_context(
            "error",
            error_msg,
            agent_name=self.name,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            error_type=type(error).__name__
        )
        
        # Return error response
        return AgentResponse(
            agent_type=self.agent_type,
            response="I encountered an error while processing your request. Please try again.",
            confidence=0.0,
            context_updates={"error": error_msg}
        )
    
    def validate_request(self, request: AgentRequest) -> None:
        """Validate incoming request."""
        if not request.message.strip():
            raise AgentError("Request message cannot be empty")
        
        if not request.user_id:
            raise AgentError("User ID is required")
        
        if not request.conversation_id:
            raise AgentError("Conversation ID is required")
    
    async def execute_with_timeout(self, coro, timeout_seconds: float = 30.0):
        """Execute a coroutine with timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            raise AgentError(f"Agent {self.name} timed out after {timeout_seconds} seconds")
    
    def extract_context_value(self, request: AgentRequest, key: str, default: Any = None) -> Any:
        """Extract a value from request context."""
        if not request.context:
            return default
        return request.context.get(key, default)
    
    def create_response(
        self,
        response_text: str,
        confidence: float = 1.0,
        next_agent: Optional[AgentType] = None,
        context_updates: Optional[Dict[str, Any]] = None,
        actions: Optional[List[Dict[str, Any]]] = None
    ) -> AgentResponse:
        """Create a standardized agent response."""
        return AgentResponse(
            agent_type=self.agent_type,
            response=response_text,
            confidence=max(0.0, min(1.0, confidence)),  # Clamp between 0 and 1
            next_agent=next_agent,
            context_updates=context_updates or {},
            actions=actions or []
        )


class StatefulAgent(BaseAgent):
    """Base class for agents that maintain state across requests."""
    
    def __init__(self, agent_type: AgentType, name: str):
        super().__init__(agent_type, name)
        self._state: Dict[str, Any] = {}
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a value from agent state."""
        return self._state.get(key, default)
    
    def set_state(self, key: str, value: Any) -> None:
        """Set a value in agent state."""
        self._state[key] = value
    
    def clear_state(self) -> None:
        """Clear all agent state."""
        self._state.clear()
    
    def update_state(self, updates: Dict[str, Any]) -> None:
        """Update multiple state values."""
        self._state.update(updates)


class AgentRegistry:
    """Registry for managing agent instances."""
    
    def __init__(self):
        self._agents: Dict[AgentType, BaseAgent] = {}
        self._initialized = False
    
    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent instance."""
        self._agents[agent.agent_type] = agent
    
    def get_agent(self, agent_type: AgentType) -> Optional[BaseAgent]:
        """Get an agent by type."""
        return self._agents.get(agent_type)
    
    def get_all_agents(self) -> List[BaseAgent]:
        """Get all registered agents."""
        return list(self._agents.values())
    
    async def initialize_all(self) -> None:
        """Initialize all registered agents."""
        if self._initialized:
            return
            
        for agent in self._agents.values():
            await agent.initialize()
        
        self._initialized = True
    
    async def cleanup_all(self) -> None:
        """Cleanup all registered agents."""
        for agent in self._agents.values():
            await agent.cleanup()
        
        self._initialized = False
    
    def list_agent_types(self) -> List[AgentType]:
        """List all registered agent types."""
        return list(self._agents.keys())


# Global agent registry
agent_registry = AgentRegistry() 