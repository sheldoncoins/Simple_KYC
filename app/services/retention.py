"""Retention enforcement: delete expired media blobs.

Run on a schedule (see ``app/jobs/purge_media.py``). For each ``MediaObject``
past its ``expires_at`` and not yet deleted, the underlying blob is removed from
object storage and the row is stamped ``deleted_at`` (kept as a tombstone for
audit). This is what keeps raw selfies/passport images from lingering.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.models import MediaObject, utcnow
from app.providers.registry import storage


def purge_expired(db: Session, now: dt.datetime | None = None) -> int:
    """Delete blobs whose retention has lapsed; return how many were purged."""
    now = now or utcnow()
    expired = db.scalars(
        select(MediaObject).where(
            MediaObject.expires_at < now,
            MediaObject.deleted_at.is_(None),
        )
    ).all()
    for obj in expired:
        storage().delete(obj.storage_ref)
        obj.deleted_at = now
        audit.record(db, actor="retention_job", action="media_purged",
                     subject=str(obj.session_id), detail=f"{obj.kind}:{obj.storage_ref}")
    db.flush()
    return len(expired)
