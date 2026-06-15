"""Dedup search-backend abstraction (linear default; pgvector validated locally)."""
from __future__ import annotations

from app.db import session_scope
from app.models import IdentityRecord
from app.providers.dedup_index import LinearScanIndex
from app.providers.face import _seed_embedding
from app.providers.registry import dedup_index
from app.services import dedup


def test_default_backend_is_linear_scan() -> None:
    assert isinstance(dedup_index(), LinearScanIndex)


def test_linear_best_match_finds_nearest_identity() -> None:
    emb = _seed_embedding("dedup_idx_person").tolist()
    with session_scope() as db:
        db.add(IdentityRecord(identity_hash="dedup_idx_hash", country="BR",
                              biometric_template=emb, limit_usdc=100.0))
        db.flush()
        score, identity_hash = LinearScanIndex().best_match(db, emb)
    assert identity_hash == "dedup_idx_hash"
    assert score > 0.99  # an embedding matches itself


def test_index_identity_is_noop_for_linear_backend() -> None:
    # The linear backend reads templates off IdentityRecord, so add() does
    # nothing and must not raise.
    with session_scope() as db:
        assert dedup.index_identity(db, "whatever", [0.1, 0.2, 0.3]) is None
