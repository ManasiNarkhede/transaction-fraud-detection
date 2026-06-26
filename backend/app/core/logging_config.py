"""JSON structured logging with timestamp, level, service, version, trace_id, event, message."""

import logging
import sys
from typing import Any

from app.config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string."""
        import json

        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "service": "fraud-api",
            "version": settings.version,
            "trace_id": getattr(record, "trace_id", "unknown"),
            "event": getattr(record, "event", record.name),
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra"):
            log_data["extra"] = record.extra

        return json.dumps(log_data)


def configure_logging() -> None:
    """Configure structured JSON logging for the application."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)

    if settings.log_format.lower() == "json":
        formatter: logging.Formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = []
    root_logger.addHandler(handler)
