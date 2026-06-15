"""1:N biometric deduplication -- the Sybil gate.

Searches a new selfie embedding against every enrolled identity. This is what
actually enforces one-human-one-account: a person re-applying with a new wallet,
new passport, or new phone still produces the same face embedding and collides
here.

Reference build does a linear cosine scan (fine to thousands of identities). At
scale, replace the scan with an ANN index (FAISS / pgvector / a vector DB) --
the decision logic (thresholds, twin handling) stays identical.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import DEDUP_REJECT_THRESHOLD, DEDUP_REVIEW_THRESHOLD
from app.models import IdentityRecord


@dataclass
class DedupResult:
    outcome: str          # "clear" | "review" | "reject"
    best_score: float
    match_identity_hash: str | None


def search(db: Session, embedding: list[float]) -> DedupResult:
    query = np.asarray(embedding, dtype=float)
    query = query / (np.linalg.norm(query) or 1.0)

    best_score, best_hash = -1.0, None
    for rec in db.scalars(select(IdentityRecord)):
        cand = np.asarray(rec.biometric_template, dtype=float)
        cand = cand / (np.linalg.norm(cand) or 1.0)
        score = float(np.dot(query, cand))
        if score > best_score:
            best_score, best_hash = score, rec.identity_hash

    if best_score >= DEDUP_REJECT_THRESHOLD:
        outcome = "reject"          # same person already enrolled
    elif best_score >= DEDUP_REVIEW_THRESHOLD:
        outcome = "review"          # too close to auto-clear (e.g. twins)
    else:
        outcome = "clear"
        best_hash = None
    return DedupResult(outcome=outcome, best_score=round(best_score, 4),
                       match_identity_hash=best_hash)
