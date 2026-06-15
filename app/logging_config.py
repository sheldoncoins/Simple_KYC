"""Structured logging setup (structlog).

One place configures logging for the whole process. Call `configure_logging()`
once at startup (FastAPI lifespan, the demo, or a test). After that, modules get
a logger with `get_logger(__name__)` and emit events as key/value pairs rather
than interpolated strings -- so logs stay machine-parseable in production and
readable in development.

Two knobs, both from the environment so nothing is hard-coded per deployment:

  * ``KYC_LOG_LEVEL``  -- standard level name (default ``INFO``).
  * ``KYC_LOG_FORMAT`` -- ``json`` for structured prod logs, ``console`` for a
    human-friendly dev renderer (default ``console``).

We never log PII here; call sites are responsible for passing only safe fields
(hashes, ids, decisions) -- see the audit choke point in ``app/audit.py``.
"""
from __future__ import annotations

import logging
import os

import structlog

_DEFAULT_LEVEL = "INFO"
_DEFAULT_FORMAT = "console"


def _resolve_level(raw: str | None) -> int:
    """Map a level name to its logging int, falling back to INFO on garbage."""
    name = (raw or _DEFAULT_LEVEL).strip().upper()
    return logging.getLevelNamesMapping().get(name, logging.INFO)


def _resolve_format(raw: str | None) -> str:
    """Return ``json`` or ``console`` (the default for anything unrecognized)."""
    fmt = (raw or _DEFAULT_FORMAT).strip().lower()
    return "json" if fmt == "json" else "console"


def configure_logging(
    *, level: str | None = None, fmt: str | None = None
) -> None:
    """Configure structlog process-wide. Idempotent -- safe to call repeatedly.

    Explicit ``level``/``fmt`` win over the environment, which is what tests use;
    in normal operation both come from ``KYC_LOG_LEVEL`` / ``KYC_LOG_FORMAT``.
    """
    log_level = _resolve_level(level if level is not None else os.environ.get("KYC_LOG_LEVEL"))
    renderer_name = _resolve_format(fmt if fmt is not None else os.environ.get("KYC_LOG_FORMAT"))

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if renderer_name == "json"
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound logger. `name` is attached as the ``logger`` field."""
    return structlog.get_logger(name)
