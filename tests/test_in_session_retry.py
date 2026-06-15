"""In-session retries: a genuine user can re-attempt a failed stage on the same
session, the attempt is bounded, and a decided session is never reprocessed."""
from __future__ import annotations

from app.services.mrz_demo import make_mrz

from tests._helpers import frames_for, passport_number_for, run_flow


def _onboard_with_passport(client, wallet: str, seed: str) -> int:
    """Onboard + submit a valid passport; return the session id ready for the
    biometric stage."""
    sid = client.post("/v1/onboard", json={
        "wallet_pubkey": wallet, "country": "BR"}).json()["session_id"]
    l1, l2 = make_mrz(number=passport_number_for(seed))
    client.post(f"/v1/sessions/{sid}/passport", json={
        "id_type": "passport", "mrz_line1": l1, "mrz_line2": l2, "person_seed": seed})
    return sid


def _submit_biometrics(client, sid: int, seed: str, *, good: bool):
    ch = client.get("/v1/liveness/challenge").json()
    frames = frames_for(ch["sequence"]) if good else [{"ear": 0.3}]
    return client.post(
        f"/v1/sessions/{sid}/biometrics?liveness_nonce={ch['nonce']}",
        json={"sub": {"selfie_ref": "s", "person_seed": seed}, "frames": frames})


def test_retry_after_soft_failure_approves_same_session(client) -> None:
    """A failed liveness attempt leaves the session retryable; a second attempt
    on the *same* session can approve."""
    seed = "retry_person_1"
    sid = _onboard_with_passport(client, "retry_wallet_1", seed)

    bad = _submit_biometrics(client, sid, seed, good=False)
    assert bad.json()["decision"] == "reject"
    assert bad.json()["reject_reason"] == "liveness_failed"

    good = _submit_biometrics(client, sid, seed, good=True)
    assert good.status_code == 200, good.text
    body = good.json()
    assert body["decision"] == "approve"
    # The stale reject reason from the first attempt is cleared on success.
    assert body["reject_reason"] is None
    assert body["signals"]["biometric_attempts"] == 2


def test_approved_session_is_not_reprocessed(client) -> None:
    """Resubmitting biometrics on an approved session is a 409 -- never a
    self-collision against the user's own freshly enrolled identity."""
    sid, r = run_flow(client, "retry_wallet_2", "BR", "retry_person_2")
    assert r.json()["decision"] == "approve"

    again = _submit_biometrics(client, sid, "retry_person_2", good=True)
    assert again.status_code == 409
    assert again.json()["detail"] == "already_verified"

    # The original approval still stands (was not flipped to duplicate_identity).
    status = client.get(f"/v1/sessions/{sid}").json()
    assert status["status"] == "approved"


def test_biometric_attempts_are_capped(client, monkeypatch) -> None:
    """After the retry budget is spent, further attempts are refused with 409."""
    monkeypatch.setenv("KYC_MAX_BIOMETRIC_ATTEMPTS", "2")
    seed = "retry_person_3"
    sid = _onboard_with_passport(client, "retry_wallet_3", seed)

    for _ in range(2):
        assert _submit_biometrics(client, sid, seed, good=False).json()["decision"] == "reject"

    blocked = _submit_biometrics(client, sid, seed, good=True)
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "too_many_attempts"


def test_passport_resubmit_blocked_after_approval(client) -> None:
    """A decided session won't accept a new passport either."""
    sid, r = run_flow(client, "retry_wallet_4", "BR", "retry_person_4")
    assert r.json()["decision"] == "approve"

    l1, l2 = make_mrz(number=passport_number_for("retry_person_4"))
    resub = client.post(f"/v1/sessions/{sid}/passport", json={
        "id_type": "passport", "mrz_line1": l1, "mrz_line2": l2,
        "person_seed": "retry_person_4"})
    assert resub.status_code == 409
    assert resub.json()["detail"] == "already_verified"
