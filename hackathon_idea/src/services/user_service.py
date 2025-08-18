"""
User service for PlacePilot.
Manages user registration, preferences, and database operations.
"""

from typing import Optional, Dict, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import db_manager
from ..core.logging import get_logger, LoggerMixin
from ..core.exceptions import DatabaseError
from ..models.database_models import User
from ..models.pydantic_models import UserCreate, UserUpdate

logger = get_logger(__name__)


class UserService(LoggerMixin):
    """Service for managing user operations."""
    
    async def ensure_user_exists(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: Optional[str] = None
    ) -> User:
        """Ensure user exists in database, create if not found."""
        
        try:
            async with db_manager.get_session() as session:
                # Check if user exists
                result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    # Create new user
                    user = User(
                        telegram_id=telegram_id,
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        language_code=language_code,
                        preferred_radius=1000,  # Default 1km
                        is_active=True
                    )
                    session.add(user)
                    await session.commit()
                    await session.refresh(user)
                    
                    self.log_with_context(
                        "info",
                        "New user created",
                        user_id=user.id,
                        telegram_id=telegram_id,
                        username=username
                    )
                else:
                    # Update user info if changed
                    updated = False
                    if username and user.username != username:
                        user.username = username
                        updated = True
                    if first_name and user.first_name != first_name:
                        user.first_name = first_name
                        updated = True
                    if last_name and user.last_name != last_name:
                        user.last_name = last_name
                        updated = True
                    if language_code and user.language_code != language_code:
                        user.language_code = language_code
                        updated = True
                    
                    if updated:
                        await session.commit()
                        self.log_with_context(
                            "debug",
                            "User info updated",
                            user_id=user.id,
                            telegram_id=telegram_id
                        )
                
                return user
                
        except Exception as e:
            self.logger.error(f"Error ensuring user exists: {e}")
            raise DatabaseError(f"Failed to ensure user exists: {e}")
    
    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                return result.scalar_one_or_none()
                
        except Exception as e:
            self.logger.error(f"Error getting user by telegram_id: {e}")
            raise DatabaseError(f"Failed to get user: {e}")
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by internal ID."""
        
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                return result.scalar_one_or_none()
                
        except Exception as e:
            self.logger.error(f"Error getting user by id: {e}")
            raise DatabaseError(f"Failed to get user: {e}")
    
    async def update_user_preferences(
        self,
        telegram_id: int,
        preferences: Dict[str, Any]
    ) -> Optional[User]:
        """Update user preferences."""
        
        try:
            async with db_manager.get_session() as session:
                # Get user
                result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    return None
                
                # Update preferences
                if "preferred_radius" in preferences:
                    user.preferred_radius = preferences["preferred_radius"]
                
                if "preferred_price_range" in preferences:
                    user.preferred_price_range = preferences["preferred_price_range"]
                
                await session.commit()
                await session.refresh(user)
                
                self.log_with_context(
                    "debug",
                    "User preferences updated",
                    user_id=user.id,
                    preferences_count=len(preferences)
                )
                
                return user
                
        except Exception as e:
            self.logger.error(f"Error updating user preferences: {e}")
            raise DatabaseError(f"Failed to update preferences: {e}")
    
    async def update_user_location(
        self, 
        telegram_id: int, 
        latitude: float, 
        longitude: float
    ) -> Optional[User]:
        """Update user's location."""
        
        try:
            async with db_manager.get_session() as session:
                # Get user
                result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    return None
                
                # Update location
                user.latitude = latitude
                user.longitude = longitude
                
                await session.commit()
                await session.refresh(user)
                
                self.log_with_context(
                    "info",
                    "User location updated",
                    user_id=user.id,
                    latitude=latitude,
                    longitude=longitude
                )
                
                return user
                
        except Exception as e:
            self.logger.error(f"Error updating user location: {e}")
            raise DatabaseError(f"Failed to update location: {e}")
    
    async def get_user_location(self, telegram_id: int) -> Optional[Dict[str, float]]:
        """Get user's saved location."""
        
        try:
            user = await self.get_user_by_telegram_id(telegram_id)
            
            if user and user.latitude is not None and user.longitude is not None:
                return {
                    "latitude": user.latitude,
                    "longitude": user.longitude
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting user location: {e}")
            return None
    
    async def user_has_location(self, telegram_id: int) -> bool:
        """Check if user has a saved location."""
        
        location = await self.get_user_location(telegram_id)
        return location is not None
    
    async def clear_user_location(self, telegram_id: int) -> bool:
        """Clear user's saved location."""
        
        try:
            async with db_manager.get_session() as session:
                # Get user
                result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    return False
                
                # Clear location
                user.latitude = None
                user.longitude = None
                
                await session.commit()
                
                self.log_with_context(
                    "info",
                    "User location cleared",
                    user_id=user.id
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error clearing user location: {e}")
            return False
    
    async def deactivate_user(self, telegram_id: int) -> bool:
        """Deactivate user account."""
        
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    update(User)
                    .where(User.telegram_id == telegram_id)
                    .values(is_active=False)
                )
                
                success = result.rowcount > 0
                await session.commit()
                
                if success:
                    self.log_with_context(
                        "info",
                        "User deactivated",
                        telegram_id=telegram_id
                    )
                
                return success
                
        except Exception as e:
            self.logger.error(f"Error deactivating user: {e}")
            raise DatabaseError(f"Failed to deactivate user: {e}")
    
    async def get_user_stats(self, telegram_id: int) -> Dict[str, Any]:
        """Get user statistics."""
        
        try:
            async with db_manager.get_session() as session:
                # Get user with related data
                user_result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                user = user_result.scalar_one_or_none()
                
                if not user:
                    return {}
                
                # Get stats (you can expand this with more complex queries)
                stats = {
                    "user_id": user.id,
                    "telegram_id": user.telegram_id,
                    "username": user.username,
                    "joined_date": user.created_at.isoformat() if user.created_at else None,
                    "is_active": user.is_active,
                    "preferred_radius": user.preferred_radius,
                    "preferred_price_range": user.preferred_price_range,
                    # You can add more stats here like:
                    # "total_searches": ...,
                    # "places_contributed": ...,
                    # "last_activity": ...,
                }
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Error getting user stats: {e}")
            raise DatabaseError(f"Failed to get user stats: {e}") 