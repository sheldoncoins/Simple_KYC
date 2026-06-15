"""The signing key loader must accept Ed25519 and reject anything else."""
from __future__ import annotations

import pytest
from app import crypto
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PrivateKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _pem(key: object) -> bytes:
    return key.private_bytes(  # type: ignore[attr-defined]
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def test_load_rejects_non_ed25519_key(tmp_path, monkeypatch) -> None:
    key_path = tmp_path / "wrong.pem"
    key_path.write_bytes(_pem(Ed448PrivateKey.generate()))
    monkeypatch.setattr(crypto, "_KEY_PATH", str(key_path))
    with pytest.raises(TypeError, match="not Ed25519"):
        crypto._load_or_create_key()


def test_load_roundtrips_ed25519_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(crypto, "_KEY_PATH", str(tmp_path / "key.pem"))
    crypto._load_or_create_key()  # generates + persists
    loaded = crypto._load_or_create_key()  # loads back + validates type
    assert isinstance(loaded, Ed25519PrivateKey)
