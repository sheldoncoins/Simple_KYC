"""Prometheus metrics.

Two kinds of signal:

* **HTTP** -- request counts + latency, labelled by method/route/status. The
  route *template* (``/v1/sessions/{session_id}``) is used, never the raw path,
  so ids don't explode label cardinality.
* **Domain** -- a collector that, on scrape, derives the verification KPIs
  (decision counts, dedup hit rate, liveness pass rate, per-country) from the DB
  via ``services.metrics``. This queries on every scrape, which is fine at
  reference scale; back it with rollups for production.

``/metrics`` should be network-restricted (in-cluster scraping), not public.
Alert rules (rejection-rate spikes, dedup anomalies) live in deploy/ (Phase 6b).
"""
from __future__ import annotations

from collections.abc import Iterator

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector

CONTENT_TYPE = CONTENT_TYPE_LATEST

_http_requests = Counter(
    "kyc_http_requests_total", "HTTP requests", ["method", "route", "status"]
)
_http_latency = Histogram(
    "kyc_http_request_duration_seconds", "HTTP request latency (s)",
    ["method", "route"],
)


def record_request(method: str, route: str, status: int, duration_s: float) -> None:
    _http_requests.labels(method, route, str(status)).inc()
    _http_latency.labels(method, route).observe(duration_s)


class _DomainMetricsCollector(Collector):
    """Derives verification KPIs from the DB on each scrape."""

    def collect(self) -> Iterator[GaugeMetricFamily]:
        from app.db import session_scope
        from app.services import metrics as metrics_service

        try:
            with session_scope() as db:
                summary = metrics_service.summary(db)
        except Exception:  # never let a scrape take the endpoint down
            return

        total = GaugeMetricFamily("kyc_sessions_total", "Verification sessions")
        total.add_metric([], summary["total_sessions"])
        yield total

        decisions = GaugeMetricFamily(
            "kyc_decisions_total", "Sessions by decision", labels=["decision"]
        )
        for name, count in summary["decisions"].items():
            decisions.add_metric([name], count)
        yield decisions

        dedup = GaugeMetricFamily("kyc_dedup_hit_rate", "1:N dedup hit rate")
        dedup.add_metric([], summary["dedup_hit_rate"])
        yield dedup

        liveness = GaugeMetricFamily("kyc_liveness_pass_rate", "Liveness pass rate")
        liveness.add_metric([], summary["liveness_pass_rate"])
        yield liveness

        by_country = GaugeMetricFamily(
            "kyc_sessions_by_country_total",
            "Sessions by country and decision",
            labels=["country", "decision"],
        )
        for iso, bucket in summary["per_country"].items():
            for name in ("approve", "review", "reject"):
                by_country.add_metric([iso, name], bucket.get(name, 0))
        yield by_country


_domain_registered = False


def register_domain_metrics() -> None:
    """Register the domain collector once (idempotent)."""
    global _domain_registered
    if not _domain_registered:
        from prometheus_client import REGISTRY

        REGISTRY.register(_DomainMetricsCollector())
        _domain_registered = True


def metrics_payload() -> bytes:
    return generate_latest()
