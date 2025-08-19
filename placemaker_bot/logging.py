import logging
import os
import uuid
import contextvars
from logging.handlers import TimedRotatingFileHandler
from pythonjsonlogger import jsonlogger
from typing import Any, Dict, Optional

from .config import settings

# Correlation id context
request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)


class EnrichedJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        from datetime import datetime, timezone
        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()
        log_record["level"] = (getattr(record, "levelname", None) or log_record.get("level", "INFO")).lower()
        log_record.setdefault("service", settings.service_name)
        log_record.setdefault("env", settings.app_env)
        rid = getattr(record, "request_id", None) or request_id_var.get()
        if rid:
            log_record["request_id"] = rid
        module_name = getattr(record, "module_name", None)
        if module_name:
            log_record["module"] = module_name
        operation = getattr(record, "operation", None)
        if operation:
            log_record["process"] = operation
        for attr in ("chat_id", "user_id", "update_id"):
            value = getattr(record, attr, None)
            if value is not None:
                log_record[attr] = value


class BaseContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "service"):
            record.service = settings.service_name
        if not hasattr(record, "env"):
            record.env = settings.app_env
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        return True


def setup_logging() -> logging.Logger:
    logger = logging.getLogger(settings.service_name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
    formatter = EnrichedJsonFormatter(fmt="%(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(BaseContextFilter())
    logger.addHandler(stream_handler)

    if settings.log_to_file:
        try:
            os.makedirs(os.path.dirname(settings.log_file) or ".", exist_ok=True)
        except Exception:
            pass
        file_handler = TimedRotatingFileHandler(
            settings.log_file,
            when=settings.log_rotate_when,
            interval=settings.log_rotate_interval,
            backupCount=settings.log_backup_count,
            utc=True,
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(BaseContextFilter())
        logger.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return logger


def build_log_extra(update: Any = None, context: Any = None, module_name: Optional[str] = None, operation: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
    extra: Dict[str, Any] = {}
    if module_name:
        extra["module_name"] = module_name
    if operation:
        extra["operation"] = operation
    if update is not None:
        try:
            extra["chat_id"] = update.effective_chat.id
        except Exception:
            pass
        try:
            extra["user_id"] = update.effective_user.id
        except Exception:
            pass
        try:
            extra["update_id"] = update.update_id
        except Exception:
            pass
        if context is not None:
            try:
                rid = context.user_data.get("request_id")
            except Exception:
                rid = None
        else:
            rid = getattr(update, "_request_id", None)
        if rid:
            extra["request_id"] = rid
            try:
                request_id_var.set(rid)
            except Exception:
                pass
    extra.update(kwargs)
    return extra


def ensure_request_id(update: Any = None, context: Any = None, generate: bool = False) -> Optional[str]:
    if context is not None:
        try:
            rid = context.user_data.get("request_id")
        except Exception:
            rid = None
    else:
        rid = request_id_var.get()

    if not rid and generate:
        rid = str(uuid.uuid4())
        if context is not None:
            try:
                context.user_data["request_id"] = rid
            except Exception:
                pass
        request_id_var.set(rid)

    if update is not None and rid and not getattr(update, "_request_id", None):
        try:
            setattr(update, "_request_id", rid)
        except Exception:
            pass
    return rid


def set_new_request_id(update: Any = None, context: Any = None) -> str:
    rid = str(uuid.uuid4())
    if context is not None:
        try:
            context.user_data["request_id"] = rid
        except Exception:
            pass
    request_id_var.set(rid)
    if update is not None:
        try:
            setattr(update, "_request_id", rid)
        except Exception:
            pass
    return rid 