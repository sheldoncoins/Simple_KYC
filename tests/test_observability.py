"""Health/readiness probes and Prometheus metrics."""
from __future__ import annotations

from tests._helpers import run_flow


def test_healthz_is_ok(client) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_readyz_checks_database(client) -> None:
    r = client.get("/readyz")
    assert r.status_code == 200 and r.json()["status"] == "ready"


def test_metrics_exposes_http_and_domain_series(client) -> None:
    # Generate a decision so the domain collector has something to report.
    run_flow(client, "metrics_wallet_1", "BR", "metrics_person_1")
    client.get("/healthz")  # some HTTP traffic to count

    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    body = r.text
    assert "kyc_http_requests_total" in body
    assert "kyc_sessions_total" in body
    assert "kyc_decisions_total" in body
    assert "kyc_liveness_pass_rate" in body
