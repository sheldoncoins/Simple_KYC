"""Face matcher.

Production: ``InsightFaceMatcher`` runs a self-hosted ArcFace/InsightFace model
over the actual selfie + passport-photo images, returns the cosine 1:1 score and
the selfie embedding (reused for 1:N dedup). Select with
``KYC_FACE_MATCHER=insightface`` (needs ``insightface`` + ``onnxruntime``).

Reference build: ``MockFaceMatcher`` derives a DETERMINISTIC embedding from a
``person_seed`` -- same seed -> same embedding -- so tests are reproducible. It
does NOT look at images; it is the stand-in until a real model is plugged in.
"""
from __future__ import annotations

import hashlib
import os

import numpy as np

from app.providers.base import FaceMatcher, FaceMatchInput, FaceMatchResult

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
    def match(self, inp: FaceMatchInput) -> FaceMatchResult:
        selfie = _seed_embedding(inp.selfie_seed)
        passport = _seed_embedding(inp.passport_seed)
        score = (cosine(selfie, passport) + 1) / 2  # map [-1,1] -> [0,1]
        # Same underlying person -> ~1.0; different -> ~0.5.
        from app.config import FACE_MATCH_MIN_SCORE
        return FaceMatchResult(
            match=score >= FACE_MATCH_MIN_SCORE,
            score=round(score, 4),
            embedding=selfie.tolist(),
        )


class InsightFaceMatcher(FaceMatcher):
    """Real 1:1 face match with self-hosted ArcFace (InsightFace ``buffalo_l``).

    Embeds the largest detected face in each image and compares by cosine
    similarity. The threshold (``KYC_FACE_MATCH_THRESHOLD``, default 0.40) is
    tuned for ArcFace normalized embeddings: genuine matches sit well above it,
    different people near zero. A missing/undetectable face is treated as a
    non-match (the pipeline then rejects), never an approval."""

    def __init__(self) -> None:
        from insightface.app import FaceAnalysis

        model = os.environ.get("KYC_FACE_MODEL", "buffalo_l")
        self._threshold = float(os.environ.get("KYC_FACE_MATCH_THRESHOLD", "0.40"))
        self._app = FaceAnalysis(name=model, providers=["CPUExecutionProvider"])
        self._app.prepare(ctx_id=-1, det_size=(640, 640))

    def _embed(self, image: bytes) -> np.ndarray | None:
        import cv2

        frame = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return None
        faces = self._app.get(frame)
        if not faces:
            return None
        face = max(faces, key=lambda f: f.det_score)
        return np.asarray(face.normed_embedding, dtype=float)

    def match(self, inp: FaceMatchInput) -> FaceMatchResult:
        if not inp.selfie_image or not inp.passport_image:
            return FaceMatchResult(match=False, score=0.0, embedding=[])
        selfie = self._embed(inp.selfie_image)
        passport = self._embed(inp.passport_image)
        if selfie is None or passport is None:
            # No face detected in one of the images -> cannot verify -> reject.
            return FaceMatchResult(match=False, score=0.0, embedding=[])
        score = float(np.dot(selfie, passport))
        return FaceMatchResult(
            match=score >= self._threshold,
            score=round(score, 4),
            embedding=selfie.tolist(),
        )
