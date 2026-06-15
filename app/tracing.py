"""Distributed tracing (OpenTelemetry) -- optional, off by default.

When ``KYC_OTEL_ENABLED=1`` and the OpenTelemetry packages are installed, this
instruments FastAPI and SQLAlchemy and exports spans over OTLP to the collector
at ``KYC_OTEL_ENDPOINT``. It is a production seam: the deps are not in the base
install and it is imported lazily, so the reference build runs without them.

    pip install opentelemetry-sdk opentelemetry-exporter-otlp \
        opentelemetry-instrumentation-fastapi \
        opentelemetry-instrumentation-sqlalchemy
"""
from __future__ import annotations

import os
from typing import Any

from app.logging_config import get_logger

_log = get_logger("tracing")


def tracing_enabled() -> bool:
    return os.environ.get("KYC_OTEL_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def setup_tracing(app: Any) -> None:
    """Instrument the app if tracing is enabled and the deps are present."""
    if not tracing_enabled():
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        _log.error("otel_deps_missing")
        return

    endpoint = os.environ.get("KYC_OTEL_ENDPOINT", "http://localhost:4318/v1/traces")
    provider = TracerProvider(resource=Resource.create({"service.name": "kyc-server"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        from app.db import engine

        SQLAlchemyInstrumentor().instrument(engine=engine)
    except ImportError:
        pass
    _log.info("tracing_enabled", endpoint=endpoint)
