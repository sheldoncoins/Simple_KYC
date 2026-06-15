"""End-to-end: passport image upload -> MRZ read -> deterministic validation."""
from __future__ import annotations

from app.services.mrz_demo import make_mrz

from tests._helpers import frames_for, passport_number_for


def test_passport_image_upload_reads_mrz_and_approves(client) -> None:
    sid = client.post("/v1/onboard", json={
        "wallet_pubkey": "media_wallet_1", "country": "BR"}).json()["session_id"]

    line1, line2 = make_mrz(number=passport_number_for("media_person_1"))
    # The dev MRZ reader treats the upload bytes as the two MRZ lines.
    image = f"{line1}\n{line2}".encode()
    r = client.post(
        f"/v1/sessions/{sid}/passport/image",
        data={"person_seed": "media_person_1"},
        files={"file": ("passport.txt", image, "text/plain")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["signals"]["mrz_valid"] is True

    ch = client.get("/v1/liveness/challenge").json()
    rb = client.post(
        f"/v1/sessions/{sid}/biometrics?liveness_nonce={ch['nonce']}",
        json={"sub": {"selfie_ref": "s", "person_seed": "media_person_1"},
              "frames": frames_for(ch["sequence"])},
    )
    assert rb.json()["decision"] == "approve", rb.text


def test_unreadable_passport_image_returns_422(client) -> None:
    sid = client.post("/v1/onboard", json={
        "wallet_pubkey": "media_wallet_2", "country": "BR"}).json()["session_id"]
    r = client.post(
        f"/v1/sessions/{sid}/passport/image",
        data={"person_seed": "media_person_2"},
        files={"file": ("passport.txt", b"only-one-line", "text/plain")},
    )
    assert r.status_code == 422
