"""Provider interface.

After dropping government rails and sanctions screening, the only capability
worth keeping swappable is face embedding (1:1 match + the embedding reused for
1:N dedup). You can back it with a self-hosted open-source model (InsightFace /
ArcFace) or a cloud API (AWS Rekognition) -- the rest of the system depends only
on this interface.

Document checks (passport MRZ) and liveness (challenge-response) are NOT
provider interfaces -- they are deterministic algorithms we own, implemented in
services/mrz.py and services/liveness.py.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class FaceMatchResult:
    match: bool             # selfie matches the passport photo?
    score: float            # 0..1 similarity (1:1)
    embedding: list[float]  # selfie embedding, reused for 1:N dedup


@dataclass
class FaceMatchInput:
    """Everything a matcher might need. The mock uses the seeds (deterministic,
    for tests); a real model (InsightFace) uses the image bytes. Callers pass
    whatever they have -- a real selfie image is only present once the wizard
    captures one."""
    selfie_seed: str = ""
    passport_seed: str = ""
    selfie_image: bytes | None = None
    passport_image: bytes | None = None


class FaceMatcher(ABC):
    @abstractmethod
    def match(self, inp: FaceMatchInput) -> FaceMatchResult:
        """Return the 1:1 match result + the selfie embedding for 1:N dedup."""
