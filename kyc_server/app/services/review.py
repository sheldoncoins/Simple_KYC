"""Manual review queue. Items land here for near-duplicates, high-risk
countries, and low-confidence sessions; a reviewer resolves approve/reject."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.models import (Decision, ReviewItem, SessionStatus,
                        VerificationSession)


def enqueue(db: Session, session_id: int, reason: str, payload: dict) -> ReviewItem:
    item = ReviewItem(session_id=session_id, reason=reason, payload=payload)
    db.add(item)
    db.flush()
    return item


def pending(db: Session) -> list[ReviewItem]:
    return list(db.scalars(select(ReviewItem).where(ReviewItem.resolved == False)))  # noqa: E712


def resolve(db: Session, item_id: int, resolution: str, reviewer: str):
    item = db.get(ReviewItem, item_id)
    if item is None or item.resolved:
        raise ValueError("review_item_not_found_or_resolved")
    sess = db.get(VerificationSession, item.session_id)

    item.resolved = True
    item.resolution = resolution
    if resolution == "approve":
        from app.services.verification import finalize_identity  # lazy: avoid cycle
        finalize_identity(db, sess)
    else:
        sess.decision = Decision.reject
        sess.status = SessionStatus.rejected
        sess.reject_reason = "manual_review_rejected"
    audit.record(db, actor=reviewer, action="review_resolved",
                 subject=str(sess.id), detail=resolution)
    db.flush()
    return sess
