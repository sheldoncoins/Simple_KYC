"""Key management + hashing.

The KYC server holds an Ed25519 signing key. It signs credentials; the P2P
layer verifies them with the public key. In production the private key lives in
a KMS/HSM -- here we generate/persist a dev key on disk. PII is stored only as
salted hashes where we need to dedup on it (phone/email) without keeping the
raw value in a queryable column.
"""
from __future__ import annotations

import hashlib
import hmac
import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

_KEY_PATH = os.environ.get("KYC_SIGNING_KEY_PATH", "./signing_key.pem")
# In production this salt comes from a secret manager, per-deployment.
_PII_SALT = os.environ.get("KYC_PII_SALT", "dev-pii-salt-change-me").encode()


def _load_or_create_key() -> Ed25519PrivateKey:
    if os.path.exists(_KEY_PATH):
        with open(_KEY_PATH, "rb") as fh:
            key = serialization.load_pem_private_key(fh.read(), password=None)
        # The signer only issues Ed25519 credentials; reject any other key type
        # loudly rather than limping on with a key the rest of the code can't use.
        if not isinstance(key, Ed25519PrivateKey):
            raise TypeError(f"signing key at {_KEY_PATH} is not Ed25519")
        return key
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with open(_KEY_PATH, "wb") as fh:
        fh.write(pem)
    return key


_PRIVATE_KEY = _load_or_create_key()
_PUBLIC_KEY: Ed25519PublicKey = _PRIVATE_KEY.public_key()


def private_pem() -> bytes:
    return _PRIVATE_KEY.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def public_pem() -> bytes:
    return _PUBLIC_KEY.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def pii_hash(value: str) -> str:
    """Salted HMAC of a PII value -- lets us dedup on phone/email without
    storing the raw value in a queryable column."""
    return hmac.new(_PII_SALT, value.strip().lower().encode(), hashlib.sha256).hexdigest()


def identity_hash(country: str, template_seed: str) -> str:
    """Stable opaque handle for a unique identity, shared with the P2P layer."""
    raw = f"{country.upper()}:{template_seed}".encode()
    return hashlib.sha256(_PII_SALT + raw).hexdigest()
