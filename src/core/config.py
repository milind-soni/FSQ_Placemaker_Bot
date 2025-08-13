"""
Configuration management for PlacePilot.
Handles environment variables, database settings, API keys, and deployment configs.
"""

import os
from typing import Optional, List
from pydantic import BaseModel, Field, validator
from enum import Enum
from dotenv import load_dotenv

load_dotenv()

class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class DatabaseConfig(BaseModel):
    """Database configuration settings."""
    url: str = Field(..., description="Database connection URL")
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Max pool overflow")
    pool_timeout: int = Field(default=30, description="Pool timeout in seconds")
    pool_recycle: int = Field(default=3600, description="Pool recycle time in seconds")


class RedisConfig(BaseModel):
    """Redis configuration settings."""
    url: str = Field(..., description="Redis connection URL")
    max_connections: int = Field(default=50, description="Max Redis connections")
    socket_timeout: float = Field(default=5.0, description="Socket timeout in seconds")


class APIConfig(BaseModel):
    """External API configuration."""
    openai_api_key: str = Field(..., description="OpenAI API key")
    foursquare_api_key: str = Field(..., description="Foursquare API key")
    telegram_bot_token: str = Field(..., description="Telegram bot token")
    telegram_webhook_url: Optional[str] = Field(default=None, description="Telegram webhook URL")


class ServerConfig(BaseModel):
    """Server configuration settings."""
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=1, description="Number of workers")
    debug: bool = Field(default=False, description="Debug mode")
    reload: bool = Field(default=False, description="Auto-reload on changes")


class LoggingConfig(BaseModel):
    """Logging configuration settings."""
    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format"
    )
    file_path: Optional[str] = Field(default=None, description="Log file path")
    max_file_size: int = Field(default=10485760, description="Max log file size (10MB)")
    backup_count: int = Field(default=5, description="Number of backup log files")


class SecurityConfig(BaseModel):
    """Security configuration settings."""
    secret_key: str = Field(..., description="Application secret key")
    allowed_hosts: List[str] = Field(default=["*"], description="Allowed hosts")
    cors_origins: List[str] = Field(default=["*"], description="CORS allowed origins")
    rate_limit_per_minute: int = Field(default=60, description="Rate limit per minute per user")


class Settings(BaseModel):
    """Main application settings."""
    
    # Environment
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Current environment"
    )
    
    # Core settings
    app_name: str = Field(default="PlacePilot", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    
    # Component configurations
    database: DatabaseConfig
    redis: RedisConfig
    api: APIConfig
    server: ServerConfig
    logging: LoggingConfig
    security: SecurityConfig
    
    # Agent settings
    max_conversation_history: int = Field(default=10, description="Max conversation history to keep")
    default_search_radius: int = Field(default=1000, description="Default search radius in meters")
    max_search_results: int = Field(default=20, description="Maximum search results")
    
    @validator('environment', pre=True)
    def validate_environment(cls, v):
        if isinstance(v, str):
            return Environment(v.lower())
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    """Get application settings from environment variables."""
    
    environment = Environment(os.getenv("ENVIRONMENT", "development").lower())
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    # Database configuration
    database_url = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://placemaker:placemaker123@localhost:5432/placemaker_db"
    )
    
    # Redis configuration
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # API keys
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    foursquare_api_key = os.getenv("FOURSQUARE_API_KEY")
    if not foursquare_api_key:
        raise ValueError("FOURSQUARE_API_KEY environment variable is required")
    
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
    
    # Security
    secret_key = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
    
    return Settings(
        environment=environment,
        database=DatabaseConfig(url=database_url),
        redis=RedisConfig(url=redis_url),
        api=APIConfig(
            openai_api_key=openai_api_key,
            foursquare_api_key=foursquare_api_key,
            telegram_bot_token=telegram_bot_token,
            telegram_webhook_url=os.getenv("TELEGRAM_WEBHOOK_URL")
        ),
        server=ServerConfig(
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
            workers=int(os.getenv("WORKERS", "1")),
            debug=debug,
            reload=debug
        ),
        logging=LoggingConfig(
            level=os.getenv("LOG_LEVEL", "INFO"),
            file_path=os.getenv("LOG_FILE_PATH")
        ),
        security=SecurityConfig(
            secret_key=secret_key,
            allowed_hosts=os.getenv("ALLOWED_HOSTS", "*").split(","),
            cors_origins=os.getenv("CORS_ORIGINS", "*").split(","),
            rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
        )
    )


# Global settings instance
settings = get_settings() 