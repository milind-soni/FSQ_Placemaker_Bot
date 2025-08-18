"""
Conversation service for PlacePilot.
Manages persistent conversation state, history, and context.
"""

import json
from typing import Optional, Dict, Any, List
from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from ..core.database import db_manager
from ..core.logging import get_logger, LoggerMixin
from ..core.exceptions import DatabaseError
from ..models.database_models import Conversation, ConversationMessage, User
from ..models.pydantic_models import ConversationState, MessageType

logger = get_logger(__name__)


class ConversationService(LoggerMixin):
    """Service for managing conversation operations."""
    
    async def get_or_create_conversation(
        self,
        conversation_id: str,
        user_telegram_id: int
    ) -> Conversation:
        """Get existing conversation or create new one."""
        
        try:
            async with db_manager.get_session() as session:
                # First get user
                user_result = await session.execute(
                    select(User).where(User.telegram_id == user_telegram_id)
                )
                user = user_result.scalar_one_or_none()
                
                if not user:
                    raise DatabaseError(f"User not found: {user_telegram_id}")
                
                # Check if conversation exists
                result = await session.execute(
                    select(Conversation).where(
                        Conversation.conversation_id == conversation_id
                    )
                )
                conversation = result.scalar_one_or_none()
                
                if not conversation:
                    # Create new conversation
                    conversation = Conversation(
                        conversation_id=conversation_id,
                        user_id=user.id,
                        current_state=ConversationState.LOCATION.value,
                        context_data={},
                        is_active=True
                    )
                    session.add(conversation)
                    await session.commit()
                    await session.refresh(conversation)
                    
                    self.log_with_context(
                        "info",
                        "New conversation created",
                        conversation_id=conversation_id,
                        user_id=user.id
                    )
                
                return conversation
                
        except Exception as e:
            self.logger.error(f"Error getting/creating conversation: {e}")
            raise DatabaseError(f"Failed to get/create conversation: {e}")
    
    async def get_conversation_context(self, conversation_id: str) -> Dict[str, Any]:
        """Get conversation context data."""
        
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(Conversation).where(
                        Conversation.conversation_id == conversation_id
                    )
                )
                conversation = result.scalar_one_or_none()
                
                if not conversation:
                    return {}
                
                context = conversation.context_data or {}
                
                # Add conversation metadata
                context.update({
                    "conversation_state": conversation.current_state,
                    "conversation_id": conversation_id,
                    "latitude": conversation.latitude,
                    "longitude": conversation.longitude,
                    "is_active": conversation.is_active
                })
                
                return context
                
        except Exception as e:
            self.logger.error(f"Error getting conversation context: {e}")
            return {}
    
    async def update_conversation_context(
        self,
        conversation_id: str,
        context_updates: Dict[str, Any]
    ) -> bool:
        """Update conversation context data."""
        
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(Conversation).where(
                        Conversation.conversation_id == conversation_id
                    )
                )
                conversation = result.scalar_one_or_none()
                
                if not conversation:
                    return False
                
                # Merge context updates
                current_context = conversation.context_data or {}
                current_context.update(context_updates)
                
                # Update conversation state if provided
                if "conversation_state" in context_updates:
                    conversation.current_state = context_updates["conversation_state"]
                
                # Update location if provided
                if "latitude" in context_updates and "longitude" in context_updates:
                    conversation.latitude = context_updates["latitude"]
                    conversation.longitude = context_updates["longitude"]
                
                # Update context data
                conversation.context_data = current_context
                
                await session.commit()
                
                self.log_with_context(
                    "debug",
                    "Conversation context updated",
                    conversation_id=conversation_id,
                    updates_count=len(context_updates)
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error updating conversation context: {e}")
            return False
    
    async def add_message(
        self,
        conversation_id: str,
        message_type: MessageType,
        content: str,
        agent_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ConversationMessage]:
        """Add message to conversation history."""
        
        try:
            async with db_manager.get_session() as session:
                # Get conversation
                conv_result = await session.execute(
                    select(Conversation).where(
                        Conversation.conversation_id == conversation_id
                    )
                )
                conversation = conv_result.scalar_one_or_none()
                
                if not conversation:
                    return None
                
                # Create message
                message = ConversationMessage(
                    conversation_id=conversation.id,
                    message_type=message_type.value,
                    content=content,
                    agent_name=agent_name,
                    metadata=metadata or {}
                )
                
                session.add(message)
                await session.commit()
                await session.refresh(message)
                
                self.log_with_context(
                    "debug",
                    "Message added to conversation",
                    conversation_id=conversation_id,
                    message_type=message_type.value,
                    agent_name=agent_name
                )
                
                return message
                
        except Exception as e:
            self.logger.error(f"Error adding message: {e}")
            return None
    
    async def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 10
    ) -> List[ConversationMessage]:
        """Get conversation message history."""
        
        try:
            async with db_manager.get_session() as session:
                # Get conversation
                conv_result = await session.execute(
                    select(Conversation).where(
                        Conversation.conversation_id == conversation_id
                    )
                )
                conversation = conv_result.scalar_one_or_none()
                
                if not conversation:
                    return []
                
                # Get messages
                result = await session.execute(
                    select(ConversationMessage)
                    .where(ConversationMessage.conversation_id == conversation.id)
                    .order_by(desc(ConversationMessage.created_at))
                    .limit(limit)
                )
                
                messages = result.scalars().all()
                return list(reversed(messages))  # Return in chronological order
                
        except Exception as e:
            self.logger.error(f"Error getting conversation history: {e}")
            return []
    
    async def reset_conversation(self, conversation_id: str) -> bool:
        """Reset conversation state and clear context."""
        
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    update(Conversation)
                    .where(Conversation.conversation_id == conversation_id)
                    .values(
                        current_state=ConversationState.LOCATION.value,
                        context_data={},
                        latitude=None,
                        longitude=None
                    )
                )
                
                success = result.rowcount > 0
                await session.commit()
                
                if success:
                    self.log_with_context(
                        "info",
                        "Conversation reset",
                        conversation_id=conversation_id
                    )
                
                return success
                
        except Exception as e:
            self.logger.error(f"Error resetting conversation: {e}")
            return False
    
    async def end_conversation(self, conversation_id: str) -> bool:
        """Mark conversation as ended."""
        
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    update(Conversation)
                    .where(Conversation.conversation_id == conversation_id)
                    .values(
                        is_active=False,
                        completed_at=datetime.utcnow()
                    )
                )
                
                success = result.rowcount > 0
                await session.commit()
                
                if success:
                    self.log_with_context(
                        "info",
                        "Conversation ended",
                        conversation_id=conversation_id
                    )
                
                return success
                
        except Exception as e:
            self.logger.error(f"Error ending conversation: {e}")
            return False
    
    async def get_active_conversations(self, user_telegram_id: int) -> List[Conversation]:
        """Get active conversations for a user."""
        
        try:
            async with db_manager.get_session() as session:
                # Get user
                user_result = await session.execute(
                    select(User).where(User.telegram_id == user_telegram_id)
                )
                user = user_result.scalar_one_or_none()
                
                if not user:
                    return []
                
                # Get active conversations
                result = await session.execute(
                    select(Conversation)
                    .where(
                        Conversation.user_id == user.id,
                        Conversation.is_active == True
                    )
                    .order_by(desc(Conversation.created_at))
                )
                
                return list(result.scalars().all())
                
        except Exception as e:
            self.logger.error(f"Error getting active conversations: {e}")
            return [] 