"""Structured JSON logging configuration."""

import json
import logging
import sys
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format.

        Returns:
            str: JSON-formatted log line.
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "extra"):
            log_data["extra"] = record.extra

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def configure_logging(level: str = "INFO") -> None:
    """Configure structured JSON logging.

    Args:
        level: Logging level as string (e.g., "INFO", "DEBUG", "WARNING").
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create stream handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level.upper())

    # Set JSON formatter
    formatter = JSONFormatter()
    handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger.addHandler(handler)

    # Suppress logs from external libraries (reduce noise)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

