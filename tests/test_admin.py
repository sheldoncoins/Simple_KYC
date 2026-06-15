"""Staff-only admin endpoints: review queue, audit log, metrics."""
from __future__ import annotations

from tests._helpers import run_flow


def test_admin_endpoints_require_staff_key(anon_client) -> None:
    assert anon_client.get("/v1/review").status_code == 401
    assert anon_client.get("/v1/audit").status_code == 401
    assert anon_client.get("/v1/metrics/summary").status_code == 401


def test_p2p_key_is_not_staff(client) -> None:
    # A P2P-only client must not reach staff endpoints.
    from app.main import app
    from fastapi.testclient import TestClient

    from tests.conftest import P2P_KEY

    p2p_only = TestClient(app, headers={"X-API-Key": P2P_KEY})
    assert p2p_only.get("/v1/review").status_code == 401


def test_review_queue_exposes_signals_for_reviewer(client) -> None:
    # A Venezuela applicant routes to manual review.
    sid, r = run_flow(client, "admin_wallet_1", "VE", "admin_person_1")
    assert r.json()["decision"] == "review"

    queue = client.get("/v1/review").json()
    item = next(i for i in queue if i["session_id"] == sid)
    assert item["country"] == "VE"
    assert item["status"] == "pending_review"
    assert "embedding" not in item["signals"]  # raw template never exposed
    assert "liveness_pass" in item["signals"]


def test_audit_log_is_readable_and_recent_first(client) -> None:
    run_flow(client, "admin_wallet_2", "BR", "admin_person_2")
    entries = client.get("/v1/audit?limit=10").json()
    assert len(entries) >= 1
    assert {"actor", "action", "created_at"} <= set(entries[0].keys())


def test_metrics_summary_shape(client) -> None:
    run_flow(client, "admin_wallet_3", "BR", "admin_person_3")
    m = client.get("/v1/metrics/summary").json()
    assert m["total_sessions"] >= 1
    assert set(m["decisions"]) == {"approve", "review", "reject"}
    assert 0.0 <= m["liveness_pass_rate"] <= 1.0
    assert "BR" in m["per_country"]
