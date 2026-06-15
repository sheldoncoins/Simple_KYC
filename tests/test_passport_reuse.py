"""Passport-reuse detection via a salted one-way document token (privacy-safe)."""
from __future__ import annotations

from app import crypto
from app.models import Decision
from app.services import risk
from app.services.mrz_demo import make_mrz

from tests._helpers import frames_for, passport_number_for, run_flow


def test_document_token_is_deterministic_and_opaque() -> None:
    token = crypto.document_token("UTO", "L898902C3")
    assert token == crypto.document_token("uto", "l898902c3")  # normalized
    assert token != crypto.document_token("UTO", "X1234567")
    # Opaque: a 64-hex digest, never the raw number.
    assert len(token) == 64 and "L898902C3" not in token


def test_risk_routes_reused_document_to_review_but_reject_wins() -> None:
    base = {
        "mrz_valid": True, "liveness_pass": True, "face_match": True,
        "dedup_outcome": "clear", "face_match_score": 0.99, "liveness_score": 0.9,
    }
    out = risk.decide({**base, "document_reused": True}, high_risk_country=False)
    assert out.decision == Decision.review and out.reason == "passport_reused"

    # A hard gate still wins over the reuse flag.
    rejected = risk.decide(
        {**base, "face_match": False, "document_reused": True}, high_risk_country=False
    )
    assert rejected.decision == Decision.reject
    assert rejected.reason == "face_mismatch_selfie_vs_passport"


def test_cloned_passport_number_routes_to_review(client) -> None:
    # Person A enrols with their own passport + face.
    run_flow(client, "reuse_wallet_a", "BR", "reuse_person_a")
    a_number = passport_number_for("reuse_person_a")

    # Person B: a *new* face, but a document carrying A's passport number.
    sid = client.post("/v1/onboard", json={
        "wallet_pubkey": "reuse_wallet_b", "country": "BR"}).json()["session_id"]
    l1, l2 = make_mrz(number=a_number)
    client.post(f"/v1/sessions/{sid}/passport", json={
        "id_type": "passport", "mrz_line1": l1, "mrz_line2": l2,
        "person_seed": "reuse_person_b"})
    ch = client.get("/v1/liveness/challenge").json()
    r = client.post(
        f"/v1/sessions/{sid}/biometrics?liveness_nonce={ch['nonce']}",
        json={"sub": {"selfie_ref": "s", "person_seed": "reuse_person_b"},
              "frames": frames_for(ch["sequence"])},
    )
    assert r.json()["decision"] == "review", r.text

    queue = client.get("/v1/review").json()
    item = next(i for i in queue if i["session_id"] == sid)
    assert item["reason"] == "passport_reused"
