"""
Pydantic models for PlacePilot API.
Defines request/response schemas and data validation models.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


class MessageType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AgentType(str, Enum):
    SUPERVISOR = "supervisor"
    SEARCH = "search"
    RECOMMENDATION = "recommendation"
    DATA_MANAGEMENT = "data_management"


class ConversationState(str, Enum):
    LOCATION = "location"
    LOCATION_CHOICE = "location_choice"
    QUERY = "query"
    REFINE = "refine"
    PLACE_DETAILS = "place_details"
    CONTRIBUTE_NAME = "contribute_name"
    CONTRIBUTE_CATEGORY = "contribute_category"
    CONTRIBUTE_ADDRESS = "contribute_address"
    CONTRIBUTE_CONTACT = "contribute_contact"
    CONTRIBUTE_HOURS = "contribute_hours"
    CONTRIBUTE_ATTRIBUTES = "contribute_attributes"
    CONTRIBUTE_PHOTOS = "contribute_photos"
    CONTRIBUTE_CONFIRM = "contribute_confirm"


# Base models
class BaseResponse(BaseModel):
    success: bool = Field(..., description="Whether the request was successful")
    message: Optional[str] = Field(None, description="Response message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class ErrorResponse(BaseResponse):
    success: bool = Field(default=False)
    error_code: Optional[str] = Field(None, description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")


# User models
class UserCreate(BaseModel):
    telegram_id: int = Field(..., description="Telegram user ID")
    username: Optional[str] = Field(None, description="Telegram username")
    first_name: Optional[str] = Field(None, description="User's first name")
    last_name: Optional[str] = Field(None, description="User's last name")
    language_code: Optional[str] = Field(None, description="User's language code")


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, description="Telegram username")
    first_name: Optional[str] = Field(None, description="User's first name")
    last_name: Optional[str] = Field(None, description="User's last name")
    preferred_radius: Optional[int] = Field(None, description="Preferred search radius in meters")
    preferred_price_range: Optional[str] = Field(None, description="Preferred price range")


class User(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    language_code: Optional[str]
    is_active: bool
    preferred_radius: int
    preferred_price_range: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Location models
class Location(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")


# Search models
class SearchFilters(BaseModel):
    open_now: Optional[bool] = Field(None, description="Filter for places open now")
    radius: Optional[int] = Field(None, ge=1, le=50000, description="Search radius in meters")
    min_price: Optional[int] = Field(None, ge=1, le=4, description="Minimum price level")
    max_price: Optional[int] = Field(None, ge=1, le=4, description="Maximum price level")
    categories: Optional[List[str]] = Field(None, description="Category filters")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    location: Location = Field(..., description="Search location")
    filters: Optional[SearchFilters] = Field(None, description="Additional search filters")
    limit: Optional[int] = Field(default=10, ge=1, le=50, description="Maximum number of results")


class PlaceSearchParams(BaseModel):
    """GPT-parsed search parameters for Foursquare API."""
    query: str = Field(description="The core search keyword")
    open_now: Optional[bool] = Field(default=None, description="Whether to filter for places open now")
    radius: Optional[int] = Field(default=None, description="Radius in meters")
    limit: Optional[int] = Field(default=None, description="Number of results to return")
    fsq_category_ids: Optional[str] = Field(default=None, description="Foursquare category IDs")
    min_price: Optional[int] = Field(default=None, description="Minimum price level")
    max_price: Optional[int] = Field(default=None, description="Maximum price level")
    search_now: bool = Field(default=False, description="True if user wants to trigger search now")
    explanation: str = Field(description="Explanation of how the query was parsed")


# Place models
class PlaceHours(BaseModel):
    open_now: Optional[bool] = Field(None, description="Whether the place is currently open")
    display: Optional[str] = Field(None, description="Human-readable hours display")


class PlacePhoto(BaseModel):
    url: str = Field(..., description="Photo URL")
    width: Optional[int] = Field(None, description="Photo width")
    height: Optional[int] = Field(None, description="Photo height")


class Place(BaseModel):
    fsq_place_id: Optional[str] = Field(None, description="Foursquare place ID")
    name: str = Field(..., description="Place name")
    distance: Optional[int] = Field(None, description="Distance from search location in meters")
    rating: Optional[float] = Field(None, ge=0, le=10, description="Place rating out of 10")
    price: Optional[int] = Field(None, ge=1, le=4, description="Price level 1-4")
    hours: Optional[PlaceHours] = Field(None, description="Operating hours")
    image_url: Optional[str] = Field(None, description="Main image URL")
    categories: Optional[List[str]] = Field(None, description="Place categories")


class SearchResponse(BaseResponse):
    places: List[Place] = Field(..., description="List of found places")
    total_count: int = Field(..., description="Total number of results")
    search_params: PlaceSearchParams = Field(..., description="Search parameters used")


# Contribution models
class PlaceContribution(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Place name")
    category: Optional[str] = Field(None, max_length=100, description="Place category")
    location: Location = Field(..., description="Place location")
    address: Optional[str] = Field(None, max_length=1000, description="Place address")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    website: Optional[str] = Field(None, max_length=500, description="Website URL")
    email: Optional[str] = Field(None, max_length=255, description="Email address")
    hours: Optional[str] = Field(None, description="Operating hours")
    is_24_7: bool = Field(default=False, description="Whether place is open 24/7")
    attributes: Optional[List[str]] = Field(None, description="Place attributes")
    is_chain: bool = Field(default=False, description="Whether place is part of a chain")
    
    @validator('email')
    def validate_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v
    
    @validator('website')
    def validate_website(cls, v):
        if v and not (v.startswith('http://') or v.startswith('https://') or v.startswith('www.')):
            v = f"https://{v}"
        return v


# Conversation models
class ConversationMessage(BaseModel):
    id: int
    message_type: MessageType
    content: str
    agent_name: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: datetime
    
    class Config:
        from_attributes = True


class Conversation(BaseModel):
    id: int
    conversation_id: str
    user_id: int
    current_state: Optional[ConversationState]
    context_data: Optional[Dict[str, Any]]
    latitude: Optional[float]
    longitude: Optional[float]
    is_active: bool
    created_at: datetime
    messages: Optional[List[ConversationMessage]]
    
    class Config:
        from_attributes = True


class ConversationUpdate(BaseModel):
    current_state: Optional[ConversationState] = Field(None, description="New conversation state")
    context_data: Optional[Dict[str, Any]] = Field(None, description="Context data to update")
    latitude: Optional[float] = Field(None, description="User's latitude")
    longitude: Optional[float] = Field(None, description="User's longitude")


# Agent models
class AgentRequest(BaseModel):
    agent_type: AgentType = Field(..., description="Type of agent to invoke")
    message: str = Field(..., description="User message")
    context: Optional[Dict[str, Any]] = Field(None, description="Conversation context")
    user_id: int = Field(..., description="User ID")
    conversation_id: str = Field(..., description="Conversation ID")


class AgentResponse(BaseModel):
    agent_type: AgentType = Field(..., description="Agent that processed the request")
    response: str = Field(..., description="Agent response")
    next_agent: Optional[AgentType] = Field(None, description="Next agent to invoke")
    context_updates: Optional[Dict[str, Any]] = Field(None, description="Context updates")
    actions: Optional[List[Dict[str, Any]]] = Field(None, description="Actions to perform")
    confidence: float = Field(..., ge=0, le=1, description="Confidence in the response")


# Contact information parsing
class ContactInfo(BaseModel):
    is_valid: bool = Field(description="Whether the contact info is valid")
    phone: str = Field(description="Extracted phone number")
    website: str = Field(description="Extracted website")
    email: str = Field(description="Extracted email")
    explanation: str = Field(description="Explanation of the parsing result")


class HoursInfo(BaseModel):
    is_valid: bool = Field(description="Whether the hours are valid")
    normalized_hours: str = Field(description="Normalized hours string")
    explanation: str = Field(description="Explanation of the parsing result")


# Health check
class HealthCheck(BaseModel):
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(..., description="Application version")
    database: bool = Field(..., description="Database health")
    redis: bool = Field(..., description="Redis health")
    apis: Dict[str, bool] = Field(..., description="External API health")


# Webhook models
class TelegramUpdate(BaseModel):
    update_id: int
    message: Optional[Dict[str, Any]] = None
    callback_query: Optional[Dict[str, Any]] = None
    
    class Config:
        extra = "allow"  # Allow extra fields from Telegram API 