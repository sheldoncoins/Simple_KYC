"""Provider wiring. Swap the implementation here to go from mock to a
self-hosted model without touching the rest of the system."""
from __future__ import annotations

import os

from app.providers.base import FaceMatcher
from app.providers.dedup_index import DedupIndex, LinearScanIndex, PgVectorIndex
from app.providers.face import MockFaceMatcher
from app.providers.mrz_reader import MrzReader, PassportEyeMrzReader, TextMrzReader
from app.providers.signer import KmsSigner, LocalEd25519Signer, Signer
from app.providers.storage import LocalEncryptedStorage, ObjectStorage, S3Storage
from app.providers.task_queue import ArqTaskQueue, InlineTaskQueue, TaskQueue

# --- Face matcher -----------------------------------------------------------
# Mock is the tested default; the real model is behind a flag (KYC_FACE_MATCHER).
_face_matcher: FaceMatcher | None = None


def _build_face_matcher() -> FaceMatcher:
    backend = os.environ.get("KYC_FACE_MATCHER", "mock").strip().lower()
    if backend == "insightface":
        from app.providers.face import InsightFaceMatcher
        return InsightFaceMatcher()
    return MockFaceMatcher()


def face_matcher() -> FaceMatcher:
    global _face_matcher
    if _face_matcher is None:
        _face_matcher = _build_face_matcher()
    return _face_matcher


def set_face_matcher(impl: FaceMatcher | None) -> None:
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


# --- Object storage ---------------------------------------------------------
_storage: ObjectStorage | None = None


def _build_storage() -> ObjectStorage:
    backend = os.environ.get("KYC_STORAGE_BACKEND", "local").strip().lower()
    if backend == "s3":
        return S3Storage()
    return LocalEncryptedStorage()


def storage() -> ObjectStorage:
    global _storage
    if _storage is None:
        _storage = _build_storage()
    return _storage


def set_storage(impl: ObjectStorage | None) -> None:
    global _storage
    _storage = impl


# --- MRZ reader -------------------------------------------------------------
_mrz_reader: MrzReader | None = None


def _build_mrz_reader() -> MrzReader:
    backend = os.environ.get("KYC_MRZ_READER", "text").strip().lower()
    if backend == "ocr":
        return PassportEyeMrzReader()
    return TextMrzReader()


def mrz_reader() -> MrzReader:
    global _mrz_reader
    if _mrz_reader is None:
        _mrz_reader = _build_mrz_reader()
    return _mrz_reader


def set_mrz_reader(impl: MrzReader | None) -> None:
    global _mrz_reader
    _mrz_reader = impl


# --- Dedup search backend ---------------------------------------------------
_dedup_index: DedupIndex | None = None


def _build_dedup_index() -> DedupIndex:
    backend = os.environ.get("KYC_DEDUP_BACKEND", "linear").strip().lower()
    if backend == "pgvector":
        return PgVectorIndex()
    return LinearScanIndex()


def dedup_index() -> DedupIndex:
    global _dedup_index
    if _dedup_index is None:
        _dedup_index = _build_dedup_index()
    return _dedup_index


def set_dedup_index(impl: DedupIndex | None) -> None:
    global _dedup_index
    _dedup_index = impl


# --- Task queue (biometric decision dispatch) -------------------------------
_task_queue: TaskQueue | None = None


def _build_task_queue() -> TaskQueue:
    backend = os.environ.get("KYC_TASK_QUEUE", "inline").strip().lower()
    if backend == "arq":
        return ArqTaskQueue()
    return InlineTaskQueue()


def task_queue() -> TaskQueue:
    global _task_queue
    if _task_queue is None:
        _task_queue = _build_task_queue()
    return _task_queue


def set_task_queue(impl: TaskQueue | None) -> None:
    global _task_queue
    _task_queue = impl
