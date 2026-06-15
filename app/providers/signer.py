"""Credential signer -- the key-management seam.

The KYC server signs short-lived credentials (EdDSA / Ed25519). In production the
private key must live in a KMS/HSM and never enter the process; for local and
single-node dev we keep an in-process key. Both sit behind the ``Signer``
interface so the rest of the system -- issuance, verification, the JWKS endpoint
-- depends only on this contract.

Each signer publishes its public key as a JWK with a ``kid`` (RFC 7638
thumbprint). Tokens carry that ``kid`` in their header, so verification picks the
right key and key rotation is non-breaking: publish the new key in the JWKS,
start signing with it, and old tokens still verify against the old key until they
expire.
"""
from __future__ import annotations

import base64
import hashlib
import json
from abc import ABC, abstractmethod

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app import crypto

ALGORITHM = "EdDSA"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _public_jwk(public_key: Ed25519PublicKey) -> dict:
    """Build the Ed25519 (OKP) JWK + its RFC 7638 thumbprint ``kid``."""
    raw = public_key.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    jwk = {"kty": "OKP", "crv": "Ed25519", "x": _b64url(raw)}
    canonical = json.dumps(
        {"crv": jwk["crv"], "kty": jwk["kty"], "x": jwk["x"]},
        separators=(",", ":"), sort_keys=True,
    )
    kid = _b64url(hashlib.sha256(canonical.encode()).digest())
    return {**jwk, "kid": kid, "alg": ALGORITHM, "use": "sig"}


class Signer(ABC):
    """Signs credentials and exposes its public keys for verification."""

    algorithm = ALGORITHM

    @property
    @abstractmethod
    def key_id(self) -> str:
        """The ``kid`` of the active signing key."""

    @abstractmethod
    def sign_jwt(self, claims: dict) -> str:
        """Sign ``claims`` into a compact JWT with the active key's ``kid``."""

    @abstractmethod
    def jwks(self) -> dict:
        """Public keys as a JWKS document (``{"keys": [...]}``)."""

    @abstractmethod
    def verify_jwt(self, token: str, *, issuer: str) -> dict:
        """Verify a token against the published keys; raise on any failure."""


class LocalEd25519Signer(Signer):
    """In-process Ed25519 signer -- the dev / self-hosted fallback.

    Backed by the key in ``crypto.py`` (file-based for dev). Adequate for local
    and single-node use; it is NOT a substitute for a KMS in production because
    the private key is in process memory. Select with ``KYC_SIGNER=local``.
    """

    def __init__(self) -> None:
        self._private_pem = crypto.private_pem()
        public_key = serialization.load_pem_private_key(
            self._private_pem, password=None
        ).public_key()
        if not isinstance(public_key, Ed25519PublicKey):  # pragma: no cover - guard
            raise TypeError("signing key is not Ed25519")
        self._jwk = _public_jwk(public_key)

    @property
    def key_id(self) -> str:
        return self._jwk["kid"]

    def sign_jwt(self, claims: dict) -> str:
        return jwt.encode(
            claims, self._private_pem, algorithm=ALGORITHM,
            headers={"kid": self.key_id},
        )

    def jwks(self) -> dict:
        return {"keys": [dict(self._jwk)]}

    def verify_jwt(self, token: str, *, issuer: str) -> dict:
        kid = jwt.get_unverified_header(token).get("kid")
        jwk = next((k for k in self.jwks()["keys"] if k["kid"] == kid), None)
        if jwk is None:
            raise jwt.InvalidKeyError(f"unknown key id: {kid}")
        public_key = jwt.algorithms.OKPAlgorithm.from_jwk(json.dumps(jwk))
        # The JWKS only carries public keys; narrow for the decoder.
        assert isinstance(public_key, Ed25519PublicKey)
        return jwt.decode(token, public_key, algorithms=[ALGORITHM], issuer=issuer)


class KmsSigner(Signer):
    """Production seam for KMS/HSM-backed Ed25519 signing (AWS KMS, GCP KMS, ...).

    The private key stays in the KMS; ``sign_jwt`` would build the JWS signing
    input and call the provider's ``Sign`` API, and ``jwks`` would expose the
    public key fetched from the KMS. Intentionally NOT implemented in this
    reference build -- wire it to your KMS client. Select with ``KYC_SIGNER=kms``.
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "KmsSigner is a documented seam, not implemented in the reference "
            "build. Provide a KMS client to enable it, or use KYC_SIGNER=local."
        )

    @property
    def key_id(self) -> str:  # pragma: no cover - unreachable until implemented
        raise NotImplementedError

    def sign_jwt(self, claims: dict) -> str:  # pragma: no cover
        raise NotImplementedError

    def jwks(self) -> dict:  # pragma: no cover
        raise NotImplementedError

    def verify_jwt(self, token: str, *, issuer: str) -> dict:  # pragma: no cover
        raise NotImplementedError
