import json
import logging
import os
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler

# Import tracing utilities for trace_id correlation
try:
    from shared.utils.tracing import get_parent_trace_id, get_trace_id
except ImportError:
    # Fallback if shared module not available
    def get_trace_id() -> str | None:
        return None

    def get_parent_trace_id() -> str | None:
        return None


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging in production"""

    def format(self, record):
        """Format."""
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add trace_id for distributed tracing correlation
        trace_id = get_trace_id()
        if trace_id:
            log_entry["trace_id"] = trace_id

        parent_trace_id = get_parent_trace_id()
        if parent_trace_id:
            log_entry["parent_trace_id"] = parent_trace_id

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        if hasattr(record, "channel_id"):
            log_entry["channel_id"] = record.channel_id
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "trace_id"):
            log_entry["trace_id"] = record.trace_id

        return json.dumps(log_entry)


def configure_logging(level: str | None = None, log_file: str | None = None):
    """Configure application logging with enhanced formatting"""

    # Get configuration from environment
    log_level_str = level or os.getenv("LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    environment = os.getenv("ENVIRONMENT", "development")

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    if environment == "production":
        # Production: JSON structured logging
        formatter = JSONFormatter()

        # Console handler with JSON
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # File logging with rotation
        os.makedirs("logs", exist_ok=True)

        # Main log file

        file_handler = RotatingFileHandler(
            "logs/app.log",
            maxBytes=50 * 1024 * 1024,
            backupCount=5,  # 50MB
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # Error log file
        error_handler = RotatingFileHandler(
            "logs/error.log",
            maxBytes=50 * 1024 * 1024,
            backupCount=10,  # 50MB
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)

    else:
        # Development: Human-readable logging
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # Optional file handler for development
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

    # Configure third-party loggers to reduce noise
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("slack_bolt").setLevel(logging.WARNING)
    logging.getLogger("slack_sdk").setLevel(logging.WARNING)

    return root_logger
