"""Object storage for uploaded media (passport images, liveness clips).

Raw media is sensitive and short-lived: it is encrypted at rest and deleted once
its retention window passes (see ``services/retention.py``). Only derived
templates persist long-term -- never the raw selfie.

Two backends behind one interface:

* ``LocalEncryptedStorage`` -- the dev/self-hosted fallback. Writes AES-256-GCM
  encrypted blobs under a local directory. The data key comes from
  ``KYC_STORAGE_KEY`` (base64, 32 bytes); for dev convenience a key is generated
  and persisted next to the data if none is set. In production set it from a
  secret manager so blobs survive key handling and stay confidential at rest.
* ``S3Storage`` -- S3-compatible object storage (AWS S3, MinIO, ...). Uses
  server-side encryption. ``boto3`` is imported lazily so it is only required
  when this backend is selected (``KYC_STORAGE_BACKEND=s3``).
"""
from __future__ import annotations

import base64
import os
from abc import ABC, abstractmethod
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_BYTES = 12


class ObjectStorage(ABC):
    """Put/get/delete opaque blobs by key. Implementations encrypt at rest."""

    @abstractmethod
    def put(self, key: str, data: bytes) -> str:
        """Store ``data`` under ``key``; return the storage ref (usually ``key``)."""

    @abstractmethod
    def get(self, key: str) -> bytes:
        """Return the bytes stored at ``key`` (raises if missing)."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete ``key``. Idempotent: deleting a missing key is not an error."""


class LocalEncryptedStorage(ObjectStorage):
    def __init__(self, directory: str | None = None, key: bytes | None = None) -> None:
        self._dir = Path(directory or os.environ.get("KYC_STORAGE_DIR", "./media_store"))
        self._dir.mkdir(parents=True, exist_ok=True)
        self._key = key or self._load_or_create_key()

    def _load_or_create_key(self) -> bytes:
        env = os.environ.get("KYC_STORAGE_KEY")
        if env:
            return base64.b64decode(env)
        # Dev convenience: persist a generated key so blobs remain decryptable
        # across restarts. Production must supply KYC_STORAGE_KEY explicitly.
        key_file = self._dir / ".storage_key"
        if key_file.exists():
            return base64.b64decode(key_file.read_bytes())
        key = AESGCM.generate_key(bit_length=256)
        key_file.write_bytes(base64.b64encode(key))
        return key

    def _path(self, key: str) -> Path:
        path = (self._dir / key).with_suffix(".enc")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def put(self, key: str, data: bytes) -> str:
        nonce = os.urandom(_NONCE_BYTES)
        ciphertext = AESGCM(self._key).encrypt(nonce, data, key.encode())
        self._path(key).write_bytes(nonce + ciphertext)
        return key

    def get(self, key: str) -> bytes:
        blob = self._path(key).read_bytes()
        nonce, ciphertext = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
        return AESGCM(self._key).decrypt(nonce, ciphertext, key.encode())

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3Storage(ObjectStorage):  # pragma: no cover - exercised against real S3
    """S3-compatible backend with server-side encryption. Production seam.

    Validated against a real bucket/MinIO, not in CI. Bucket + credentials come
    from the environment (``KYC_S3_BUCKET`` and the standard AWS_* variables /
    instance role); ``KYC_S3_ENDPOINT_URL`` points at MinIO or another gateway.
    """

    def __init__(self) -> None:
        try:
            import boto3
        except ImportError as exc:  # noqa: TRY003
            raise RuntimeError(
                "S3Storage needs boto3 -- `pip install boto3` or use "
                "KYC_STORAGE_BACKEND=local."
            ) from exc
        self._bucket = os.environ["KYC_S3_BUCKET"]
        self._client = boto3.client(
            "s3", endpoint_url=os.environ.get("KYC_S3_ENDPOINT_URL") or None
        )

    def put(self, key: str, data: bytes) -> str:
        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=data, ServerSideEncryption="AES256"
        )
        return key

    def get(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)
