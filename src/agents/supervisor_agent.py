"""
Supervisor Agent for PlacePilot.
Routes user requests to appropriate specialized agents and manages conversation flow.
"""

from typing import Dict, Any, Optional, List
import asyncio

from .base_agent import BaseAgent, agent_registry
from ..models.pydantic_models import AgentRequest, AgentResponse, AgentType, ConversationState
from ..core.exceptions import SupervisorAgentError
from ..integrations.openai_client import openai_client


class SupervisorAgent(BaseAgent):
    """
    Supervisor agent that coordinates all other agents.
    Routes requests, manages context, and orchestrates multi-agent workflows.
    """
    
    def __init__(self):
        super().__init__(AgentType.SUPERVISOR, "SupervisorAgent")
        self.routing_confidence_threshold = 0.7
        
    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """Process request by routing to appropriate specialist agent."""
        
        try:
            self.validate_request(request)
            session_id = self.start_session(request.conversation_id)
            
            self.log_with_context(
                "info",
                "Processing supervisor request",
                user_id=request.user_id,
                conversation_id=request.conversation_id,
                message_length=len(request.message)
            )
            
            # Determine current conversation state
            current_state = self._get_conversation_state(request)
            
            # Route request to appropriate agent
            target_agent_type = await self._route_request(request, current_state)
            
            if target_agent_type == AgentType.SUPERVISOR:
                # Handle directly (greeting, help, etc.)
                response = await self._handle_supervisor_request(request)
            else:
                # Delegate to specialist agent
                response = await self._delegate_to_agent(request, target_agent_type)
            
            # Update conversation context based on response
            response = await self._update_conversation_context(request, response, current_state)
            
            self.log_with_context(
                "info",
                "Supervisor request completed",
                user_id=request.user_id,
                target_agent=target_agent_type.value,
                confidence=response.confidence
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Supervisor agent error: {e}")
            return await self.handle_error(e, request)
        finally:
            self.end_session()
    
    async def can_handle(self, request: AgentRequest) -> bool:
        """Supervisor can handle all requests - it routes them appropriately."""
        return True
    
    async def _route_request(
        self, 
        request: AgentRequest, 
        current_state: Optional[ConversationState]
    ) -> AgentType:
        """Determine which agent should handle this request."""
        
        message = request.message.lower().strip()
        context = request.context or {}
        
        # State-based routing first
        if current_state:
            state_routing = self._route_by_state(current_state, message)
            if state_routing:
                return state_routing
        
        # Intent-based routing using AI
        return await self._route_by_intent(message, context)
    
    def _route_by_state(self, state: ConversationState, message: str) -> Optional[AgentType]:
        """Route based on current conversation state."""
        
        # Location sharing states -> Search Agent
        if state in [ConversationState.LOCATION, ConversationState.LOCATION_CHOICE]:
            return AgentType.SEARCH
        
        # Search and refinement states -> Search or Recommendation Agent  
        if state in [ConversationState.QUERY, ConversationState.REFINE]:
            # If user is asking for recommendations or expressing preferences
            if any(word in message for word in ["recommend", "suggest", "best", "good", "craving", "want", "looking"]):
                return AgentType.RECOMMENDATION
            return AgentType.SEARCH
        
        # Place contribution states -> Data Management Agent
        if state.value.startswith("contribute_"):
            return AgentType.DATA_MANAGEMENT
        
        return None
    
    async def _route_by_intent(self, message: str, context: Dict[str, Any]) -> AgentType:
        """Use AI to determine user intent and route accordingly."""
        
        intents = {
            "search": "User wants to find places (search, find, locate, show me, where)",
            "recommend": "User wants recommendations (recommend, suggest, best, good for, craving)",
            "contribute": "User wants to add/contribute place data (add, contribute, new place, submit)",
            "help": "User needs help or greeting (help, start, hello, what can you do)"
        }
        
        system_prompt = f"""
        Analyze the user's message and classify their intent. Choose the most appropriate intent:
        
        Available intents:
        {chr(10).join([f"- {intent}: {desc}" for intent, desc in intents.items()])}
        
        Respond with only the intent name.
        """
        
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User message: {message}"}
            ]
            
            completion = await openai_client.chat_completion(
                messages=messages,
                temperature=0.1,
                max_tokens=20
            )
            
            intent = completion.choices[0].message.content.strip().lower()
            
            # Map intents to agent types
            intent_mapping = {
                "search": AgentType.SEARCH,
                "recommend": AgentType.RECOMMENDATION,  
                "contribute": AgentType.DATA_MANAGEMENT,
                "help": AgentType.SUPERVISOR
            }
            
            return intent_mapping.get(intent, AgentType.SUPERVISOR)
            
        except Exception as e:
            self.logger.warning(f"Intent classification failed: {e}")
            # Fallback to keyword-based routing
            return self._fallback_routing(message)
    
    def _fallback_routing(self, message: str) -> AgentType:
        """Fallback routing using simple keyword matching."""
        
        message = message.lower()
        
        # Search keywords
        if any(word in message for word in ["find", "search", "where", "show me", "location"]):
            return AgentType.SEARCH
        
        # Recommendation keywords  
        if any(word in message for word in ["recommend", "suggest", "best", "good", "craving"]):
            return AgentType.RECOMMENDATION
        
        # Contribution keywords
        if any(word in message for word in ["add", "contribute", "new place", "submit"]):
            return AgentType.DATA_MANAGEMENT
        
        # Default to supervisor for help/general queries
        return AgentType.SUPERVISOR
    
    async def _delegate_to_agent(
        self, 
        request: AgentRequest, 
        target_agent_type: AgentType
    ) -> AgentResponse:
        """Delegate request to the appropriate specialist agent."""
        
        target_agent = agent_registry.get_agent(target_agent_type)
        if not target_agent:
            raise SupervisorAgentError(f"Agent {target_agent_type} not found in registry")
        
        # Check if target agent can handle the request
        can_handle = await target_agent.can_handle(request)
        if not can_handle:
            self.logger.warning(f"Agent {target_agent_type} cannot handle request, falling back")
            return await self._handle_supervisor_request(request)
        
        # Delegate to target agent
        self.log_with_context(
            "debug",
            f"Delegating to {target_agent_type.value}",
            user_id=request.user_id,
            target_agent=target_agent_type.value
        )
        
        return await target_agent.process_request(request)
    
    async def _handle_supervisor_request(self, request: AgentRequest) -> AgentResponse:
        """Handle requests that the supervisor manages directly."""
        
        message = request.message.lower().strip()
        
        # Greeting/start
        if any(word in message for word in ["start", "hello", "hi", "hey"]):
            return self._create_welcome_response()
        
        # Help
        if "help" in message:
            return self._create_help_response()
        
        # Status/info
        if any(word in message for word in ["status", "info", "about"]):
            return self._create_info_response()
        
        # Default response for unhandled messages
        return self._create_default_response()
    
    def _create_welcome_response(self) -> AgentResponse:
        """Create welcome response for new users."""
        
        welcome_text = """🤖 Welcome to PlacePilot!

I'm your AI-powered location companion. I can help you:

🔍 **Find Places**: Search for restaurants, cafes, shops, and more
🧠 **Get Recommendations**: Personalized suggestions based on your preferences  
📝 **Contribute Data**: Add new places and update information

To get started, just share your location or tell me what you're looking for!

Try saying: "I'm looking for coffee shops nearby" or "Find me a good burger place" """

        return self.create_response(
            response_text=welcome_text,
            confidence=1.0,
            context_updates={
                "conversation_state": ConversationState.LOCATION.value,
                "welcome_shown": True
            },
            actions=[
                {
                    "type": "request_location", 
                    "text": "Share your location to get started"
                }
            ]
        )
    
    def _create_help_response(self) -> AgentResponse:
        """Create help response."""
        
        help_text = """🆘 **PlacePilot Help**

**What I can do:**
• 🔍 Find places: "Show me pizza places nearby"
• 🎯 Recommendations: "I'm craving sushi, what's good?"
• ➕ Add places: "I want to add a new restaurant"
• 🗺️ Explore data: View places on interactive maps

**How to use me:**
1. Share your location (or I'll ask for it)
2. Tell me what you're looking for in natural language
3. I'll find relevant places and help you explore options

**Example queries:**
• "Find coffee shops within 500 meters"
• "What are the best burger joints open now?"
• "I want to add my favorite local restaurant"

Just talk to me naturally - I understand context and preferences!"""

        return self.create_response(
            response_text=help_text,
            confidence=1.0
        )
    
    def _create_info_response(self) -> AgentResponse:
        """Create info/about response."""
        
        info_text = """ℹ️ **About PlacePilot**

I'm an AI-powered location companion built with:
• 🤖 Advanced language understanding
• 🗺️ Foursquare's global places database (100M+ locations)
• 🎯 Personalized recommendations
• 🔄 Real-time data updates

**Powered by:**
• OpenAI GPT for natural language processing
• Foursquare Places API for location data
• Intelligent agent system for specialized tasks

**Privacy:** I only use your location to find relevant places. No personal data is stored without permission.

Ready to explore? Just tell me what you're looking for!"""

        return self.create_response(
            response_text=info_text,
            confidence=1.0
        )
    
    def _create_default_response(self) -> AgentResponse:
        """Create default response for unclear requests."""
        
        default_text = """🤔 I'm not sure what you're looking for. 

I can help you:
• Find places nearby
• Get personalized recommendations  
• Add new places to the database

Try being more specific, like:
• "Find Italian restaurants nearby"
• "I'm craving pizza, what's good?"
• "I want to add a new coffee shop"

Or just say "help" for more information!"""

        return self.create_response(
            response_text=default_text,
            confidence=0.3
        )
    
    def _get_conversation_state(self, request: AgentRequest) -> Optional[ConversationState]:
        """Extract conversation state from request context."""
        
        context = request.context or {}
        state_value = context.get("conversation_state")
        
        if state_value:
            try:
                return ConversationState(state_value)
            except ValueError:
                self.logger.warning(f"Invalid conversation state: {state_value}")
        
        return None
    
    async def _update_conversation_context(
        self, 
        request: AgentRequest, 
        response: AgentResponse, 
        current_state: Optional[ConversationState]
    ) -> AgentResponse:
        """Update conversation context based on agent response."""
        
        # Merge context updates from response
        context_updates = response.context_updates or {}
        
        # Add supervisor metadata
        context_updates.update({
            "last_agent": response.agent_type.value,
            "last_confidence": response.confidence,
            "supervisor_session_id": self.session_id
        })
        
        # Update response with merged context
        response.context_updates = context_updates
        
        return response 