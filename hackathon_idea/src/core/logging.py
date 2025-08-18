"""
Logging configuration for PlacePilot.
Provides structured logging with different formatters for dev/prod environments.
"""

import logging
import logging.handlers
import json
import sys
from typing import Dict, Any
from datetime import datetime
from pathlib import Path

from .config import settings


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging in production."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        
        if hasattr(record, "conversation_id"):
            log_data["conversation_id"] = record.conversation_id
        
        if hasattr(record, "agent_name"):
            log_data["agent_name"] = record.agent_name
        
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for development environment."""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[1;31m', # Bold Red
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        # Add color to level name
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        
        # Format the message
        formatted = super().format(record)
        
        # Add extra context if available
        extras = []
        if hasattr(record, "user_id"):
            extras.append(f"user_id={record.user_id}")
        if hasattr(record, "agent_name"):
            extras.append(f"agent={record.agent_name}")
        if hasattr(record, "conversation_id"):
            extras.append(f"conv_id={record.conversation_id}")
        
        if extras:
            formatted += f" [{', '.join(extras)}]"
        
        return formatted


def setup_logging() -> None:
    """Setup logging configuration based on environment."""
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.logging.level.upper()))
    
    # Remove default handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    if settings.environment == "production":
        # Use JSON formatter in production
        console_handler.setFormatter(JsonFormatter())
    else:
        # Use colored formatter in development
        formatter = ColoredFormatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(formatter)
    
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if settings.logging.file_path:
        file_path = Path(settings.logging.file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=file_path,
            maxBytes=settings.logging.max_file_size,
            backupCount=settings.logging.backup_count,
            encoding="utf-8"
        )
        
        # Always use JSON format for file logs
        file_handler.setFormatter(JsonFormatter())
        root_logger.addHandler(file_handler)
    
    # Set levels for specific loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


class LoggerMixin:
    """Mixin to add logging capabilities to classes."""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger instance for this class."""
        return get_logger(self.__class__.__name__)
    
    def log_with_context(self, level: str, message: str, **context) -> None:
        """Log message with additional context."""
        logger = self.logger
        log_method = getattr(logger, level.lower())
        
        # Create a new log record with extra context
        extra = {k: v for k, v in context.items() if v is not None}
        log_method(message, extra=extra) 