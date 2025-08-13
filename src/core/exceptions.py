"""
Custom exceptions for PlacePilot application.
Provides structured error handling across all components.
"""

from typing import Optional, Dict, Any


class PlacePilotError(Exception):
    """Base exception class for PlacePilot application."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ConfigurationError(PlacePilotError):
    """Raised when there's a configuration issue."""
    pass


class DatabaseError(PlacePilotError):
    """Raised when there's a database-related error."""
    pass


class APIError(PlacePilotError):
    """Base class for API-related errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        self.status_code = status_code
        super().__init__(message, details)


class FoursquareAPIError(APIError):
    """Raised when Foursquare API returns an error."""
    pass


class OpenAIAPIError(APIError):
    """Raised when OpenAI API returns an error."""
    pass


class TelegramAPIError(APIError):
    """Raised when Telegram API returns an error."""
    pass


class AgentError(PlacePilotError):
    """Base class for agent-related errors."""
    pass


class SupervisorAgentError(AgentError):
    """Raised when supervisor agent encounters an error."""
    pass


class SearchAgentError(AgentError):
    """Raised when search agent encounters an error."""
    pass


class RecommendationAgentError(AgentError):
    """Raised when recommendation agent encounters an error."""
    pass


class DataManagementAgentError(AgentError):
    """Raised when data management agent encounters an error."""
    pass


class ValidationError(PlacePilotError):
    """Raised when data validation fails."""
    pass


class AuthenticationError(PlacePilotError):
    """Raised when authentication fails."""
    pass


class RateLimitError(PlacePilotError):
    """Raised when rate limit is exceeded."""
    pass


class ConversationError(PlacePilotError):
    """Raised when conversation handling fails."""
    pass


class WebhookError(PlacePilotError):
    """Raised when webhook processing fails."""
    pass 