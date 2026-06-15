"""1:N dedup search backends.

The Sybil-gate *decision* (thresholds, twin handling) lives in
``services/dedup.py`` and never changes. What changes with scale is only how the
nearest enrolled identity is found:

* ``LinearScanIndex`` -- the reference backend: a cosine scan over every
  ``IdentityRecord`` template. Correct and dependency-free; fine to thousands of
  identities. Default.
* ``PgVectorIndex`` -- ANN search via the Postgres ``pgvector`` extension. Keeps
  a ``identity_vectors`` table it provisions itself, so the main schema stays
  database-agnostic. Returns the same cosine score the linear scan would, so the
  decision is identical -- only faster. Select with ``KYC_DEDUP_BACKEND=pgvector``.

Both expose the same contract: ``add`` an enrolled embedding, and ``best_match``
returns ``(best_cosine_score, identity_hash)`` (score ``-1.0`` / ``None`` when the
index is empty).
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import IdentityRecord


def _unit(vec: list[float]) -> np.ndarray:
    arr = np.asarray(vec, dtype=float)
    return arr / (np.linalg.norm(arr) or 1.0)


class DedupIndex(ABC):
    @abstractmethod
    def add(self, db: Session, identity_hash: str, embedding: list[float]) -> None:
        """Register an enrolled identity's embedding for future searches."""

    @abstractmethod
    def best_match(self, db: Session, embedding: list[float]) -> tuple[float, str | None]:
        """Return the closest enrolled identity as (cosine_score, identity_hash)."""


class LinearScanIndex(DedupIndex):
    """Reads embeddings straight from ``IdentityRecord``; ``add`` is a no-op
    because the template already lives on that row."""

    def add(self, db: Session, identity_hash: str, embedding: list[float]) -> None:
        return None

    def best_match(self, db: Session, embedding: list[float]) -> tuple[float, str | None]:
        query = _unit(embedding)
        best_score, best_hash = -1.0, None
        for rec in db.scalars(select(IdentityRecord)):
            score = float(np.dot(query, _unit(rec.biometric_template)))
            if score > best_score:
                best_score, best_hash = score, rec.identity_hash
        return best_score, best_hash


class PgVectorIndex(DedupIndex):
    """ANN search via pgvector. Self-provisions its table/extension on first use."""

    def __init__(self, dim: int | None = None) -> None:
        self._dim = dim or int(os.environ.get("KYC_EMBEDDING_DIM", "128"))
        self._ready = False

    def _ensure(self, db: Session) -> None:
        if self._ready:
            return
        db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        db.execute(text(
            "CREATE TABLE IF NOT EXISTS identity_vectors ("
            "identity_hash text PRIMARY KEY, "
            f"embedding vector({self._dim}))"
        ))
        self._ready = True

    @staticmethod
    def _literal(embedding: list[float]) -> str:
        return "[" + ",".join(repr(float(x)) for x in embedding) + "]"

    def add(self, db: Session, identity_hash: str, embedding: list[float]) -> None:
        self._ensure(db)
        db.execute(
            text(
                "INSERT INTO identity_vectors (identity_hash, embedding) "
                "VALUES (:h, CAST(:v AS vector)) "
                "ON CONFLICT (identity_hash) DO UPDATE SET embedding = EXCLUDED.embedding"
            ),
            {"h": identity_hash, "v": self._literal(embedding)},
        )

    def best_match(self, db: Session, embedding: list[float]) -> tuple[float, str | None]:
        self._ensure(db)
        row = db.execute(
            text(
                "SELECT identity_hash, 1 - (embedding <=> CAST(:v AS vector)) AS score "
                "FROM identity_vectors "
                "ORDER BY embedding <=> CAST(:v AS vector) LIMIT 1"
            ),
            {"v": self._literal(embedding)},
        ).first()
        if row is None:
            return -1.0, None
        return float(row.score), row.identity_hash
