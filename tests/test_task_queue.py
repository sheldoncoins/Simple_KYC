"""Task-queue dispatch: inline default + the async (worker) contract."""
from __future__ import annotations

import os

from app.main import app
from app.providers.registry import set_task_queue, task_queue
from app.providers.task_queue import InlineTaskQueue, TaskQueue
from app.services.mrz_demo import make_mrz
from fastapi.testclient import TestClient

from tests._helpers import frames_for

_KEY = os.environ["KYC_P2P_API_KEYS"].split(",")[0]


def test_default_queue_is_inline() -> None:
    assert isinstance(task_queue(), InlineTaskQueue)
    assert task_queue().is_async() is False


class _RecordingAsyncQueue(TaskQueue):
    """Stand-in for the arq queue: async, records enqueues instead of using Redis."""

    def __init__(self) -> None:
        self.jobs: list[tuple] = []

    def is_async(self) -> bool:
        return True

    def enqueue_biometrics(self, session_id, submission, liveness_nonce, frames) -> None:
        self.jobs.append((session_id, submission, liveness_nonce, frames))


def test_async_queue_defers_decision_then_worker_completes() -> None:
    client = TestClient(app, headers={"X-API-Key": _KEY})
    sid = client.post("/v1/onboard", json={
        "wallet_pubkey": "queue_wallet_1", "country": "BR"}).json()["session_id"]
    l1, l2 = make_mrz()
    client.post(f"/v1/sessions/{sid}/passport", json={
        "id_type": "passport", "mrz_line1": l1, "mrz_line2": l2,
        "person_seed": "queue_person_1"})
    ch = client.get("/v1/liveness/challenge").json()

    fake = _RecordingAsyncQueue()
    set_task_queue(fake)
    try:
        r = client.post(
            f"/v1/sessions/{sid}/biometrics?liveness_nonce={ch['nonce']}",
            json={"sub": {"selfie_ref": "s", "person_seed": "queue_person_1"},
                  "frames": frames_for(ch["sequence"])})
        # Async path: no decision yet, job handed to the worker.
        assert r.status_code == 200, r.text
        assert r.json()["decision"] is None
        assert r.json()["status"] == "biometrics_submitted"
        assert len(fake.jobs) == 1 and fake.jobs[0][0] == sid
    finally:
        set_task_queue(None)

    # The worker would run this; do it inline to prove the deferred path decides.
    from app.db import session_scope
    from app.schemas import BiometricSubmission
    from app.services import verification
    job_sid, submission, nonce, frames = fake.jobs[0]
    with session_scope() as db:
        verification.submit_biometrics(
            db, job_sid, BiometricSubmission(**submission), nonce, frames)

    assert client.get(f"/v1/sessions/{sid}").json()["decision"] == "approve"
