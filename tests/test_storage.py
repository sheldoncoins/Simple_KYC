"""Local encrypted object storage: roundtrip, at-rest encryption, delete."""
from __future__ import annotations

import pytest
from app.providers.storage import LocalEncryptedStorage
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def test_roundtrip_and_encrypted_at_rest(tmp_path) -> None:
    store = LocalEncryptedStorage(
        directory=str(tmp_path), key=AESGCM.generate_key(bit_length=256)
    )
    ref = store.put("passport_image/abc", b"top-secret-mrz")
    assert store.get(ref) == b"top-secret-mrz"

    blobs = list(tmp_path.rglob("*.enc"))
    assert blobs, "expected an encrypted blob on disk"
    assert b"top-secret-mrz" not in blobs[0].read_bytes()  # ciphertext, not plaintext


def test_delete_is_idempotent(tmp_path) -> None:
    store = LocalEncryptedStorage(
        directory=str(tmp_path), key=AESGCM.generate_key(bit_length=256)
    )
    ref = store.put("k/1", b"data")
    store.delete(ref)
    store.delete(ref)  # no error the second time
    with pytest.raises(FileNotFoundError):
        store.get(ref)
