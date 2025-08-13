"""
SQLAlchemy database models for PlacePilot.
Defines the database schema for users, places, conversations, and related entities.
"""

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime, 
    ForeignKey, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from ..core.database import Base


class User(Base):
    """User model for Telegram users."""
    
    __tablename__ = "users"
    
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    language_code = Column(String(10), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # User preferences
    preferred_radius = Column(Integer, default=1000)  # in meters
    preferred_price_range = Column(String(10), nullable=True)  # e.g., "1-3"
    
    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    search_history = relationship("SearchHistory", back_populates="user", cascade="all, delete-orphan")
    contributed_places = relationship("Place", back_populates="contributor", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username={self.username})>"


class Conversation(Base):
    """Conversation model for tracking user conversations."""
    
    __tablename__ = "conversations"
    
    conversation_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Conversation state
    current_state = Column(String(50), nullable=True)
    context_data = Column(JSON, nullable=True)  # Store conversation context
    
    # Location context
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Conversation(id={self.conversation_id}, user_id={self.user_id})>"


class ConversationMessage(Base):
    """Individual messages within a conversation."""
    
    __tablename__ = "conversation_messages"
    
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    message_type = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    agent_name = Column(String(50), nullable=True)  # Which agent handled this message
    
    # Message metadata
    message_metadata = Column(JSON, nullable=True)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    
    def __repr__(self):
        return f"<ConversationMessage(conversation_id={self.conversation_id}, type={self.message_type})>"


class Place(Base):
    """Place model for storing contributed place information."""
    
    __tablename__ = "places"
    
    # Basic info
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    
    # Location
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(Text, nullable=True)
    
    # Contact information
    phone = Column(String(50), nullable=True)
    website = Column(String(500), nullable=True)
    email = Column(String(255), nullable=True)
    
    # Operating hours
    hours = Column(Text, nullable=True)
    is_24_7 = Column(Boolean, default=False)
    
    # Attributes
    attributes = Column(JSON, nullable=True)  # Store as array of attributes
    is_chain = Column(Boolean, default=False)
    
    # Foursquare integration
    foursquare_id = Column(String(100), nullable=True, unique=True)
    
    # Contribution info
    contributor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_verified = Column(Boolean, default=False)
    verification_notes = Column(Text, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Relationships
    contributor = relationship("User", back_populates="contributed_places")
    photos = relationship("PlacePhoto", back_populates="place", cascade="all, delete-orphan")
    
    # Index for location-based queries
    __table_args__ = (
        Index('idx_place_location', 'latitude', 'longitude'),
        Index('idx_place_foursquare', 'foursquare_id'),
    )
    
    def __repr__(self):
        return f"<Place(name={self.name}, latitude={self.latitude}, longitude={self.longitude})>"


class PlacePhoto(Base):
    """Photos associated with places."""
    
    __tablename__ = "place_photos"
    
    place_id = Column(Integer, ForeignKey("places.id"), nullable=False)
    file_id = Column(String(255), nullable=False)  # Telegram file_id
    photo_type = Column(String(50), nullable=True)  # storefront, interior, menu, etc.
    caption = Column(String(500), nullable=True)
    
    # Relationships
    place = relationship("Place", back_populates="photos")
    
    def __repr__(self):
        return f"<PlacePhoto(place_id={self.place_id}, type={self.photo_type})>"


class SearchHistory(Base):
    """Search history for analytics and personalization."""
    
    __tablename__ = "search_history"
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Search parameters
    query = Column(String(500), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius = Column(Integer, nullable=True)
    category = Column(String(100), nullable=True)
    
    # Search filters
    filters = Column(JSON, nullable=True)  # Store filters as JSON
    
    # Results
    results_count = Column(Integer, default=0)
    selected_place_id = Column(String(100), nullable=True)  # Foursquare place ID
    
    # Agent context
    agent_used = Column(String(50), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="search_history")
    
    # Index for analytics queries
    __table_args__ = (
        Index('idx_search_user_date', 'user_id', 'created_at'),
        Index('idx_search_location', 'latitude', 'longitude'),
    )
    
    def __repr__(self):
        return f"<SearchHistory(user_id={self.user_id}, query={self.query})>"


class AgentSession(Base):
    """Track agent sessions for performance monitoring."""
    
    __tablename__ = "agent_sessions"
    
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    agent_name = Column(String(50), nullable=False)
    
    # Performance metrics
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # Status and results
    status = Column(String(20), default="active")  # active, completed, failed
    result_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    conversation = relationship("Conversation")
    
    def __repr__(self):
        return f"<AgentSession(session_id={self.session_id}, agent={self.agent_name})>" 