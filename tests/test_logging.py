"""Tests for the structured-logging configuration decision paths."""
from __future__ import annotations

import logging

import structlog
from app import logging_config


def test_resolve_format_defaults_to_console() -> None:
    assert logging_config._resolve_format(None) == "console"
    assert logging_config._resolve_format("") == "console"
    assert logging_config._resolve_format("garbage") == "console"
    assert logging_config._resolve_format("JSON") == "json"
    assert logging_config._resolve_format(" json ") == "json"


def test_resolve_level_parses_names_and_falls_back() -> None:
    assert logging_config._resolve_level("debug") == logging.DEBUG
    assert logging_config._resolve_level("WARNING") == logging.WARNING
    assert logging_config._resolve_level(None) == logging.INFO
    assert logging_config._resolve_level("nonsense") == logging.INFO


def test_configure_logging_selects_renderer_by_format() -> None:
    logging_config.configure_logging(fmt="json", level="INFO")
    assert isinstance(
        structlog.get_config()["processors"][-1],
        structlog.processors.JSONRenderer,
    )

    logging_config.configure_logging(fmt="console", level="INFO")
    assert isinstance(
        structlog.get_config()["processors"][-1],
        structlog.dev.ConsoleRenderer,
    )
