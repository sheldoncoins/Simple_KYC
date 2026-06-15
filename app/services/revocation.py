"""Credential revocation.

Credentials are short-lived (``CREDENTIAL_TTL_SECONDS``), so revocation only has
to cover that window. A revocation targets either a single token (``jti``) or an
entire identity (``identity_hash`` -- e.g. an account taken over or banned).
``is_revoked`` is consulted during credential verification.
"""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import audit
from app.models import RevokedCredential


def revoke(
    db: Session,
    *,
    jti: str | None = None,
    identity_hash: str | None = None,
    reason: str = "manual",
    actor: str = "p2p_client",
) -> RevokedCredential:
    """Record a revocation. At least one of ``jti``/``identity_hash`` is required."""
    if not jti and not identity_hash:
        raise ValueError("revocation requires a jti or an identity_hash")
    entry = RevokedCredential(jti=jti, identity_hash=identity_hash, reason=reason)
    db.add(entry)
    db.flush()
    audit.record(
        db, actor=actor, action="credential_revoked",
        subject=identity_hash or jti, detail=reason,
    )
    return entry


def is_revoked(db: Session, claims: dict) -> bool:
    """True if the token's ``jti`` or its ``identity_hash`` has been revoked."""
    jti = claims.get("jti")
    identity_hash = claims.get("identity_hash")
    conditions = []
    if jti:
        conditions.append(RevokedCredential.jti == jti)
    if identity_hash:
        conditions.append(RevokedCredential.identity_hash == identity_hash)
    if not conditions:
        return False
    return db.scalar(select(RevokedCredential.id).where(or_(*conditions))) is not None
