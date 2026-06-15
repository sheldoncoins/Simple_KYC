"""Store uploaded media with a retention deadline.

The bytes go to encrypted object storage; a ``MediaObject`` row keeps only the
ref + expiry. Retention defaults come from ``KYC_MEDIA_RETENTION_SECONDS`` so raw
passport images / liveness clips are short-lived by policy (DPDP/LGPD/NDPA).
"""
from __future__ import annotations

import datetime as dt
import os
import uuid

from sqlalchemy.orm import Session

from app import audit
from app.models import MediaObject, utcnow
from app.providers.registry import storage

_DEFAULT_RETENTION_SECONDS = 86_400  # 24h


def retention_seconds() -> int:
    return int(os.environ.get("KYC_MEDIA_RETENTION_SECONDS", _DEFAULT_RETENTION_SECONDS))


def store(
    db: Session,
    *,
    kind: str,
    data: bytes,
    content_type: str | None = None,
    session_id: int | None = None,
) -> MediaObject:
    """Encrypt + persist ``data`` and record its retention deadline."""
    key = f"{kind}/{uuid.uuid4().hex}"
    ref = storage().put(key, data)
    expires_at = utcnow() + dt.timedelta(seconds=retention_seconds())
    obj = MediaObject(
        session_id=session_id, kind=kind, storage_ref=ref,
        content_type=content_type, expires_at=expires_at,
    )
    db.add(obj)
    db.flush()
    audit.record(db, actor="system", action="media_stored",
                 subject=str(session_id), detail=f"{kind}:{ref}")
    return obj


def load(db: Session, media_id: int) -> bytes:
    """Fetch and decrypt a stored blob (raises if missing/deleted)."""
    obj = db.get(MediaObject, media_id)
    if obj is None or obj.deleted_at is not None:
        raise ValueError("media_not_found")
    return storage().get(obj.storage_ref)
