"""The API allows the web wizard's origin (CORS)."""
from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_cors_allows_configured_origin() -> None:
    r = client.get(
        "/v1/liveness/challenge",
        headers={"Origin": "http://localhost:3000"},
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
