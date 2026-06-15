"""Face matcher.

Production: implement `match` against a self-hosted ArcFace/InsightFace model
(or a cloud face API). Extract a 512-d embedding from the selfie, compare to the
passport-photo embedding for the 1:1 score, and return the selfie embedding so
the dedup service can run the 1:N search.

Reference build: `MockFaceMatcher` derives a DETERMINISTIC embedding from a
`person_seed`. Same seed -> same embedding (so the same human re-applying with a
new wallet collides in dedup -- exactly the case we must catch). The 1:1 score
is the cosine similarity between the selfie's and passport's seeded embeddings,
so a mismatched selfie (different seed) fails the 1:1 check, just like reality.
"""
from __future__ import annotations

import hashlib

import numpy as np

from app.providers.base import FaceMatcher, FaceMatchResult

_DIM = 128


def _seed_embedding(person_seed: str) -> np.ndarray:
    """Stable unit-norm embedding for a given 'person'."""
    h = hashlib.sha256(person_seed.encode()).digest()
    rng = np.random.default_rng(int.from_bytes(h[:8], "big"))
    v = rng.standard_normal(_DIM)
    return v / np.linalg.norm(v)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))  # inputs are unit-norm


class MockFaceMatcher(FaceMatcher):
    def match(self, *, selfie_ref: str, person_seed: str,
              passport_person_seed: str) -> FaceMatchResult:
        selfie = _seed_embedding(person_seed)
        passport = _seed_embedding(passport_person_seed)
        score = (cosine(selfie, passport) + 1) / 2  # map [-1,1] -> [0,1]
        # Same underlying person -> ~1.0; different -> ~0.5.
        from app.config import FACE_MATCH_MIN_SCORE
        return FaceMatchResult(
            match=score >= FACE_MATCH_MIN_SCORE,
            score=round(score, 4),
            embedding=selfie.tolist(),
        )
