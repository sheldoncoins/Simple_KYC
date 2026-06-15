"""1:N biometric deduplication -- the Sybil gate.

Searches a new selfie embedding against every enrolled identity. This is what
actually enforces one-human-one-account: a person re-applying with a new wallet,
new passport, or new phone still produces the same face embedding and collides
here.

The *nearest-neighbour search* is pluggable (`providers/dedup_index.py`: linear
scan by default, pgvector at scale). The **decision** below -- the reject/review
thresholds and twin handling -- is unchanged regardless of backend.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import dedup_thresholds
from app.providers.registry import dedup_index


@dataclass
class DedupResult:
    outcome: str          # "clear" | "review" | "reject"
    best_score: float
    match_identity_hash: str | None


def search(db: Session, embedding: list[float]) -> DedupResult:
    best_score, best_hash = dedup_index().best_match(db, embedding)
    reject_threshold, review_threshold = dedup_thresholds()

    if best_score >= reject_threshold:
        outcome = "reject"          # same person already enrolled
    elif best_score >= review_threshold:
        outcome = "review"          # too close to auto-clear (e.g. twins)
    else:
        outcome = "clear"
        best_hash = None
    return DedupResult(outcome=outcome, best_score=round(best_score, 4),
                       match_identity_hash=best_hash)


def index_identity(db: Session, identity_hash: str, embedding: list[float]) -> None:
    """Register a newly-enrolled identity with the search backend. A no-op for
    the linear scan (it reads templates straight off ``IdentityRecord``); the
    pgvector backend stores the vector for ANN search."""
    dedup_index().add(db, identity_hash, embedding)
