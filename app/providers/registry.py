"""Provider wiring. Swap the implementation here to go from mock to a
self-hosted model without touching the rest of the system."""
from __future__ import annotations

import os

from app.providers.base import FaceMatcher
from app.providers.face import MockFaceMatcher
from app.providers.signer import KmsSigner, LocalEd25519Signer, Signer

_face_matcher: FaceMatcher = MockFaceMatcher()


def face_matcher() -> FaceMatcher:
    return _face_matcher


def set_face_matcher(impl: FaceMatcher) -> None:
    global _face_matcher
    _face_matcher = impl


# --- Credential signer ------------------------------------------------------
# Built lazily so importing the registry never touches a KMS or a key on disk
# until a credential is actually signed/verified. KYC_SIGNER picks the backend.
_signer: Signer | None = None


def _build_signer() -> Signer:
    backend = os.environ.get("KYC_SIGNER", "local").strip().lower()
    if backend == "kms":
        return KmsSigner()
    return LocalEd25519Signer()


def signer() -> Signer:
    global _signer
    if _signer is None:
        _signer = _build_signer()
    return _signer


def set_signer(impl: Signer | None) -> None:
    """Override (or reset, with None) the signer -- used by tests."""
    global _signer
    _signer = impl
