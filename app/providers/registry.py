"""Provider wiring. Swap the implementation here to go from mock to a
self-hosted model without touching the rest of the system."""
from __future__ import annotations

from app.providers.base import FaceMatcher
from app.providers.face import MockFaceMatcher

_face_matcher: FaceMatcher = MockFaceMatcher()


def face_matcher() -> FaceMatcher:
    return _face_matcher


def set_face_matcher(impl: FaceMatcher) -> None:
    global _face_matcher
    _face_matcher = impl
