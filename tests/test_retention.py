"""Retention purge deletes expired media blobs and tombstones the row."""
from __future__ import annotations

import datetime as dt

import pytest
from app.db import session_scope
from app.models import MediaObject, utcnow
from app.providers.registry import storage
from app.services import media
from app.services.retention import purge_expired


def test_purge_expired_deletes_blob_and_marks_row() -> None:
    with session_scope() as db:
        obj = media.store(db, kind="passport_image", data=b"secret-bytes")
        obj.expires_at = utcnow() - dt.timedelta(seconds=1)  # already lapsed
        db.flush()
        ref, media_id = obj.storage_ref, obj.id

    assert storage().get(ref) == b"secret-bytes"  # present before purge

    with session_scope() as db:
        assert purge_expired(db) >= 1

    with pytest.raises(FileNotFoundError):
        storage().get(ref)  # blob gone
    with session_scope() as db:
        assert db.get(MediaObject, media_id).deleted_at is not None  # tombstoned


def test_unexpired_media_survives_purge() -> None:
    with session_scope() as db:
        obj = media.store(db, kind="liveness_clip", data=b"keep-me")
        ref, media_id = obj.storage_ref, obj.id

    with session_scope() as db:
        purge_expired(db)

    assert storage().get(ref) == b"keep-me"
    with session_scope() as db:
        assert db.get(MediaObject, media_id).deleted_at is None
