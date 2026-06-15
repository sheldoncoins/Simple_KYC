"""Task queue for the biometric decision step.

Face matching + 1:N dedup are the heavy part of the pipeline. With a real face
model they belong on a background worker so the request thread returns fast and
the client polls session status. That is the production shape; for the reference
build (mock matcher, instant) running inline is simpler and keeps the API
synchronous.

* ``InlineTaskQueue`` -- default. The biometric endpoint processes the decision
  in-request and returns it. ``is_async()`` is False.
* ``ArqTaskQueue`` -- enqueues the job to Redis for the arq worker
  (``app/worker.py``); the endpoint returns immediately with the session in
  ``biometrics_submitted`` and the client polls ``GET /v1/sessions/{id}``.
  ``arq`` is imported lazily, so it is only needed when selected
  (``KYC_TASK_QUEUE=arq``).
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod


class TaskQueue(ABC):
    @abstractmethod
    def is_async(self) -> bool:
        """True if work is dispatched to a worker (endpoint should not block)."""

    @abstractmethod
    def enqueue_biometrics(
        self, session_id: int, submission: dict, liveness_nonce: str, frames: list[dict]
    ) -> None:
        """Hand the biometric decision job to the worker."""


class InlineTaskQueue(TaskQueue):
    def is_async(self) -> bool:
        return False

    def enqueue_biometrics(
        self, session_id: int, submission: dict, liveness_nonce: str, frames: list[dict]
    ) -> None:
        # Inline path runs the work in-request; nothing to enqueue.
        raise RuntimeError("InlineTaskQueue does not enqueue; run the work inline")


class ArqTaskQueue(TaskQueue):  # pragma: no cover - needs Redis + the arq worker
    """Redis-backed dispatch. Validated against a running Redis + arq worker."""

    def is_async(self) -> bool:
        return True

    def enqueue_biometrics(
        self, session_id: int, submission: dict, liveness_nonce: str, frames: list[dict]
    ) -> None:
        import asyncio

        from arq import create_pool
        from arq.connections import RedisSettings

        async def _send() -> None:
            redis = await create_pool(
                RedisSettings.from_dsn(os.environ.get("KYC_REDIS_URL", "redis://localhost:6379"))
            )
            await redis.enqueue_job(
                "process_biometrics", session_id, submission, liveness_nonce, frames
            )

        asyncio.run(_send())
