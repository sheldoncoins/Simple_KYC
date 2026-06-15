"""Reusable flow helpers shared across the HTTP tests."""
from __future__ import annotations

import hashlib

from app.services.mrz_demo import make_mrz
from fastapi.testclient import TestClient


def passport_number_for(seed: str) -> str:
    """Deterministic, per-person passport number so distinct applicants don't
    share a document (which would trip the passport-reuse check). Same seed ->
    same number (the Sybil/same-person case)."""
    return hashlib.sha1(seed.encode()).hexdigest()[:9].upper()


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


def run_flow(client: TestClient, wallet: str, country: str, seed: str,
             selfie_seed: str | None = None, good: bool = True):
    """Drive onboard -> passport -> biometrics; return (session_id, response)."""
    selfie_seed = selfie_seed or seed
    sid = client.post("/v1/onboard", json={
        "wallet_pubkey": wallet, "country": country}).json()["session_id"]
    l1, l2 = make_mrz(number=passport_number_for(seed))
    client.post(f"/v1/sessions/{sid}/passport", json={
        "id_type": "passport", "mrz_line1": l1, "mrz_line2": l2, "person_seed": seed})
    ch = client.get("/v1/liveness/challenge").json()
    frames = frames_for(ch["sequence"]) if good else [{"ear": 0.3}]
    r = client.post(
        f"/v1/sessions/{sid}/biometrics?liveness_nonce={ch['nonce']}",
        json={"sub": {"selfie_ref": "s", "person_seed": selfie_seed}, "frames": frames})
    return sid, r


def issue_credential(client: TestClient, session_id: int):
    return client.post(f"/v1/sessions/{session_id}/credential")
