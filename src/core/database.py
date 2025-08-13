"""
Database configuration and session management for PlacePilot.
Provides async database connections, session management, and base model classes.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, DateTime, String, func
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from .config import settings
from .logging import get_logger
from .exceptions import DatabaseError

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Base model class with common fields."""
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DatabaseManager:
    """Database connection manager."""
    
    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None
    
    async def initialize(self) -> None:
        """Initialize database engine and session factory."""
        try:
            # Create async engine
            self._engine = create_async_engine(
                settings.database.url,
                pool_size=settings.database.pool_size,
                max_overflow=settings.database.max_overflow,
                pool_timeout=settings.database.pool_timeout,
                pool_recycle=settings.database.pool_recycle,
                echo=settings.server.debug,
                future=True,
                poolclass=NullPool if "sqlite" in settings.database.url else None
            )
            
            # Create session factory
            self._session_factory = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            logger.info("Database manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database manager: {e}")
            raise DatabaseError(f"Database initialization failed: {e}")
    
    async def close(self) -> None:
        """Close database connections."""
        if self._engine:
            await self._engine.dispose()
            logger.info("Database connections closed")
    
    @property
    def engine(self) -> AsyncEngine:
        """Get database engine."""
        if not self._engine:
            raise DatabaseError("Database manager not initialized")
        return self._engine
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session context manager."""
        if not self._session_factory:
            raise DatabaseError("Database manager not initialized")
        
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise DatabaseError(f"Database operation failed: {e}")
    
    async def create_tables(self) -> None:
        """Create database tables."""
        try:
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise DatabaseError(f"Table creation failed: {e}")
    
    async def drop_tables(self) -> None:
        """Drop database tables."""
        try:
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.info("Database tables dropped successfully")
        except Exception as e:
            logger.error(f"Failed to drop database tables: {e}")
            raise DatabaseError(f"Table drop failed: {e}")


# Global database manager instance
db_manager = DatabaseManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    async with db_manager.get_session() as session:
        yield session


async def init_db() -> None:
    """Initialize database."""
    await db_manager.initialize()
    await db_manager.create_tables()


async def close_db() -> None:
    """Close database connections."""
    await db_manager.close()


# Health check function
async def check_database_health() -> bool:
    """Check if database is healthy."""
    try:
        async with db_manager.get_session() as session:
            await session.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False 