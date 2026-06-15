"""Verifiable credential issuance/verification.

The P2P layer receives a short-lived Ed25519-signed JWT that attests only:
verified + unique human, the identity_hash, and remaining limit. No PII. The
P2P layer verifies with the public key alone -- it never calls back here for
identity data.
"""
from __future__ import annotations

import datetime as dt

import jwt

from app.config import CREDENTIAL_TTL_SECONDS
from app.crypto import private_pem, public_pem

_ALG = "EdDSA"
_ISSUER = "kyc-server"


def issue(identity_hash: str, wallet_pubkey: str, limit_remaining: float) -> tuple[str, int]:
    now = dt.datetime.now(dt.timezone.utc)
    claims = {
        "iss": _ISSUER,
        "sub": wallet_pubkey,
        "identity_hash": identity_hash,
        "verified": True,
        "unique": True,
        "limit_remaining_usdc": round(limit_remaining, 2),
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=CREDENTIAL_TTL_SECONDS)).timestamp()),
    }
    token = jwt.encode(claims, private_pem(), algorithm=_ALG)
    return token, CREDENTIAL_TTL_SECONDS


def verify(token: str) -> dict:
    """Raises jwt exceptions on invalid/expired tokens."""
    return jwt.decode(token, public_pem(), algorithms=[_ALG], issuer=_ISSUER)
