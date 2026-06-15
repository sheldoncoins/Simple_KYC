"""Verifiable credential issuance/verification.

The P2P layer receives a short-lived Ed25519-signed JWT that attests only:
verified + unique human, the identity_hash, and remaining limit. No PII. The
P2P layer verifies with the public key (fetched from the JWKS endpoint) -- it
never calls back here for identity data.

Signing goes through the ``Signer`` provider (local key or KMS), so the private
key handling is swappable and tokens carry a ``kid`` for rotation. Each token
also carries a unique ``jti`` so it can be revoked individually.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from app.config import CREDENTIAL_TTL_SECONDS
from app.providers.registry import signer
from app.services import revocation

_ISSUER = "kyc-server"


class RevokedCredentialError(Exception):
    """Raised by ``verify`` when a token (or its identity) has been revoked."""


def issue(identity_hash: str, wallet_pubkey: str, limit_remaining: float) -> tuple[str, int]:
    now = dt.datetime.now(dt.timezone.utc)
    claims = {
        "iss": _ISSUER,
        "sub": wallet_pubkey,
        "jti": uuid.uuid4().hex,
        "identity_hash": identity_hash,
        "verified": True,
        "unique": True,
        "limit_remaining_usdc": round(limit_remaining, 2),
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=CREDENTIAL_TTL_SECONDS)).timestamp()),
    }
    token = signer().sign_jwt(claims)
    return token, CREDENTIAL_TTL_SECONDS


def verify(token: str, db: Session | None = None) -> dict:
    """Validate signature + expiry (raises jwt exceptions on failure).

    When a ``db`` session is supplied, also enforce the revocation list and raise
    ``RevokedCredentialError`` for a revoked token. The ``db``-less form is for
    contexts that only need signature/expiry checking (e.g. the demo).
    """
    claims = signer().verify_jwt(token, issuer=_ISSUER)
    if db is not None and revocation.is_revoked(db, claims):
        raise RevokedCredentialError(claims.get("jti"))
    return claims
