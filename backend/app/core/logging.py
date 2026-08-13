"""Logging configuration."""

import logging
from logging.config import dictConfig

from app.core.config import settings


def configure_logging() -> None:
    """Configure process-wide console logging."""
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"default": {"format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s"}},
            "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "default", "stream": "ext://sys.stdout"}},
            "root": {"handlers": ["console"], "level": settings.log_level},
        }
    )
    logging.getLogger(__name__).debug("Logging configured")
