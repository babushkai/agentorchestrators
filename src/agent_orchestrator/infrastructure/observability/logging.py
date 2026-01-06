"""Structured logging configuration."""

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor

from agent_orchestrator.config import TelemetrySettings


def setup_logging(settings: TelemetrySettings) -> None:
    """Configure structured logging with structlog."""
    # Determine log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Shared processors for both dev and prod
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    # Development: colored console output
    # Production: JSON output
    if settings.log_level == "DEBUG":
        processors: list[Processor] = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        processors = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a logger for a module."""
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """Bind context variables for logging."""
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear context variables."""
    structlog.contextvars.clear_contextvars()
