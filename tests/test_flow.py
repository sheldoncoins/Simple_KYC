"""End-to-end tests over the HTTP API using FastAPI's TestClient.

Covers: happy-path approval + credential + limit spend, the Sybil rejection
(same face, new wallet), passport MRZ rejection, liveness failure paths,
credential verification, idempotent debit, limit enforcement, and the manual
review queue for high-risk countries.
"""
from __future__ import annotations

import os
import tempfile

import pytest

# Isolated DB + keys per test run.
_tmp = tempfile.mkdtemp()
os.environ["KYC_DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["KYC_SIGNING_KEY_PATH"] = f"{_tmp}/key.pem"

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import liveness  # noqa: E402
from app.services.mrz_demo import make_mrz  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

init_db()
client = TestClient(app)


# Feature timelines that the (self-built) liveness detector reads.
GOOD_FRAMES = {
    "blink":      [{"ear": 0.30}, {"ear": 0.10}, {"ear": 0.30}],
    "turn_left":  [{"yaw": -30.0}, {"yaw": 0.0}],
    "turn_right": [{"yaw": 30.0}, {"yaw": 0.0}],
    "smile":      [{"mar": 0.70}, {"mar": 0.10}],
}


def frames_for(sequence: list[str]) -> list[dict]:
    out: list[dict] = []
    for action in sequence:
        out.extend(GOOD_FRAMES[action])
    return out


def _flow(wallet, country, seed, selfie_seed=None, good=True):
    selfie_seed = selfie_seed or seed
    sid = client.post("/v1/onboard", json={
        "wallet_pubkey": wallet, "country": country}).json()["session_id"]
    l1, l2 = make_mrz()
    client.post(f"/v1/sessions/{sid}/passport", json={
        "id_type": "passport", "mrz_line1": l1, "mrz_line2": l2, "person_seed": seed})
    ch = client.get("/v1/liveness/challenge").json()
    frames = frames_for(ch["sequence"]) if good else [{"ear": 0.3}]
    r = client.post(
        f"/v1/sessions/{sid}/biometrics?liveness_nonce={ch['nonce']}",
        json={"sub": {"selfie_ref": "s", "person_seed": selfie_seed}, "frames": frames})
    return sid, r


def test_happy_path_approves_and_issues_credential():
    sid, r = _flow("wallet_alice", "BR", "person_alice")
    assert r.status_code == 200, r.text
    assert r.json()["decision"] == "approve"

    cred = client.post(f"/v1/sessions/{sid}/credential").json()
    assert cred["limit_remaining_usdc"] == 100.0
    v = client.post("/v1/credentials/verify", json={"credential": cred["credential"]}).json()
    assert v["valid"] and v["claims"]["unique"] and v["claims"]["verified"]


def test_sybil_same_face_new_wallet_is_rejected():
    _flow("wallet_bob1", "MX", "person_bob")
    # Same human (same person_seed), brand-new wallet + new passport submission.
    _, r = _flow("wallet_bob2", "MX", "person_bob")
    assert r.json()["decision"] == "reject"
    assert r.json()["reject_reason"] == "duplicate_identity"


def test_selfie_not_matching_passport_is_rejected():
    _, r = _flow("wallet_carol", "AR", "passport_carol", selfie_seed="someone_else")
    assert r.json()["decision"] == "reject"
    assert r.json()["reject_reason"] == "face_mismatch_selfie_vs_passport"


def test_failed_liveness_is_rejected():
    _, r = _flow("wallet_dave", "CO", "person_dave", good=False)
    assert r.json()["decision"] == "reject"
    assert r.json()["reject_reason"] == "liveness_failed"


def test_invalid_passport_mrz_is_rejected():
    sid = client.post("/v1/onboard", json={
        "wallet_pubkey": "wallet_eve", "country": "NG"}).json()["session_id"]
    # Tamper the MRZ so check digits fail.
    l1, l2 = make_mrz(number="FAKE00000")
    l2 = l2[:9] + "0" + l2[10:]  # wrong passport-number check digit
    client.post(f"/v1/sessions/{sid}/passport", json={
        "id_type": "passport", "mrz_line1": l1, "mrz_line2": l2, "person_seed": "eve"})
    ch = client.get("/v1/liveness/challenge").json()
    r = client.post(f"/v1/sessions/{sid}/biometrics?liveness_nonce={ch['nonce']}",
                    json={"sub": {"selfie_ref": "s", "person_seed": "eve"},
                          "frames": frames_for(ch["sequence"])})
    assert r.json()["decision"] == "reject"
    assert r.json()["reject_reason"] == "passport_mrz_invalid"


def test_high_risk_country_goes_to_review_then_approve():
    sid, r = _flow("wallet_frank", "VE", "person_frank")
    assert r.json()["decision"] == "review"
    queue = client.get("/v1/review").json()
    item = next(i for i in queue if i["session_id"] == sid)
    res = client.post(f"/v1/review/{item['item_id']}",
                      json={"resolution": "approve"}).json()
    assert res["status"] == "approved"
    cred = client.post(f"/v1/sessions/{sid}/credential")
    assert cred.status_code == 200


def test_limit_ledger_enforces_and_is_idempotent():
    sid, _ = _flow("wallet_grace", "IN", "person_grace")
    ih = client.post(f"/v1/sessions/{sid}/credential").json()["identity_hash"]

    b = client.post("/v1/limits/debit", json={
        "identity_hash": ih, "amount_usdc": 60, "idempotency_key": "tx1"}).json()
    assert b["remaining_usdc"] == 40.0
    # Idempotent replay -> no double spend.
    b = client.post("/v1/limits/debit", json={
        "identity_hash": ih, "amount_usdc": 60, "idempotency_key": "tx1"}).json()
    assert b["remaining_usdc"] == 40.0
    # Over the remaining limit -> rejected.
    over = client.post("/v1/limits/debit", json={
        "identity_hash": ih, "amount_usdc": 50, "idempotency_key": "tx2"})
    assert over.status_code == 409


def test_replayed_liveness_nonce_rejected():
    liveness.reset()
    ch = liveness.issue_challenge(2)
    first = liveness.verify_response(ch.nonce, frames_for(ch.sequence))
    assert first.is_live
    again = liveness.verify_response(ch.nonce, frames_for(ch.sequence))
    assert not again.is_live and "unknown_or_reused_nonce" in again.reasons


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
