"""arq background worker.

Runs the heavy biometric decision (face match + 1:N dedup + risk) off the
request path when ``KYC_TASK_QUEUE=arq``. Start it with:

    arq app.worker.WorkerSettings

The web endpoint enqueues ``process_biometrics`` and returns immediately; this
worker opens its own DB session, runs the same ``verification.submit_biometrics``
logic, and writes the decision. The client polls ``GET /v1/sessions/{id}``.

``arq`` is only needed where the worker actually runs, so it is imported here
(this module is loaded by the arq CLI, not by the web app).
"""
from __future__ import annotations

import os

from arq.connections import RedisSettings

from app.db import session_scope
from app.logging_config import configure_logging, get_logger
from app.schemas import BiometricSubmission
from app.services import verification

log = get_logger("worker")


async def process_biometrics(
    ctx: dict, session_id: int, submission: dict, liveness_nonce: str, frames: list[dict]
) -> None:
    sub = BiometricSubmission(**submission)
    with session_scope() as db:
        sess = verification.submit_biometrics(db, session_id, sub, liveness_nonce, frames)
    log.info("biometrics_processed", session_id=session_id,
             decision=sess.decision.value if sess.decision else None)


async def startup(ctx: dict) -> None:
    configure_logging()
    log.info("worker_startup")


class WorkerSettings:
    functions = [process_biometrics]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("KYC_REDIS_URL", "redis://localhost:6379")
    )
