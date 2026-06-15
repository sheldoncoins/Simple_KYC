"""P2P client authentication and rate limiting."""
from __future__ import annotations

from app import security
from app.main import app
from fastapi.testclient import TestClient


def test_p2p_endpoints_reject_without_api_key(anon_client) -> None:
    assert anon_client.post(
        "/v1/credentials/verify", json={"credential": "x"}).status_code == 401
    assert anon_client.post("/v1/limits/debit", json={
        "identity_hash": "x", "amount_usdc": 1, "idempotency_key": "k"}).status_code == 401
    assert anon_client.get("/v1/limits/somehash").status_code == 401
    assert anon_client.post(
        "/v1/credentials/revoke", json={"jti": "x"}).status_code == 401


def test_wrong_api_key_rejected() -> None:
    bad = TestClient(app, headers={"X-API-Key": "not-a-real-key"})
    assert bad.post(
        "/v1/credentials/verify", json={"credential": "x"}).status_code == 401


def test_valid_api_key_reaches_handler(client) -> None:
    # Auth passes; the junk token then fails verification -> valid=False (200).
    r = client.post("/v1/credentials/verify", json={"credential": "not-a-jwt"})
    assert r.status_code == 200
    assert r.json()["valid"] is False


def test_onboard_is_rate_limited(monkeypatch, client) -> None:
    security.reset_rate_limits()
    monkeypatch.setenv("KYC_RATELIMIT_ONBOARD_PER_MIN", "2")
    codes = [
        client.post(
            "/v1/onboard", json={"wallet_pubkey": f"rl_wallet_{i}", "country": "BR"}
        ).status_code
        for i in range(3)
    ]
    assert codes == [200, 200, 429]
    security.reset_rate_limits()
