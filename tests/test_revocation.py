"""Credential revocation: by token (jti) and by identity."""
from __future__ import annotations

from tests._helpers import issue_credential, run_flow


def _approved_credential(client, wallet: str, seed: str) -> dict:
    sid, r = run_flow(client, wallet, "BR", seed)
    assert r.json()["decision"] == "approve", r.text
    return issue_credential(client, sid).json()


def test_revoke_by_jti_blocks_that_token(client) -> None:
    cred = _approved_credential(client, "rev_wallet_1", "rev_person1")
    token = cred["credential"]

    v = client.post("/v1/credentials/verify", json={"credential": token}).json()
    assert v["valid"] is True
    jti = v["claims"]["jti"]

    r = client.post("/v1/credentials/revoke", json={"jti": jti, "reason": "test"})
    assert r.status_code == 200 and r.json()["revoked"] is True

    after = client.post("/v1/credentials/verify", json={"credential": token}).json()
    assert after["valid"] is False and after["error"] == "revoked"


def test_revoke_by_identity_blocks_its_credentials(client) -> None:
    cred = _approved_credential(client, "rev_wallet_2", "rev_person2")
    token, identity_hash = cred["credential"], cred["identity_hash"]

    client.post("/v1/credentials/revoke",
                json={"identity_hash": identity_hash, "reason": "account_banned"})

    after = client.post("/v1/credentials/verify", json={"credential": token}).json()
    assert after["valid"] is False and after["error"] == "revoked"


def test_revoke_without_target_is_rejected(client) -> None:
    r = client.post("/v1/credentials/revoke", json={"reason": "nothing-to-revoke"})
    assert r.status_code == 400
