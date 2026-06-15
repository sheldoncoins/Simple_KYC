"""Configuration and per-country policy.

Scope (per product decision):
  * Passport only -- no local government IDs.
  * No government-rail validation. Passport integrity is checked via the
    deterministic ICAO 9303 MRZ check digits (see services/mrz.py) -- free,
    no vendor, no ML.
  * No sanctions/PEP screening.

The only thing that varies per country now is risk routing: VE stays elevated
(weak ID infra + OFAC exposure) so its sessions bias toward manual review even
though we don't screen.
"""
import os
from dataclasses import dataclass

DEFAULT_LIMIT_USDC: float = 100.0
CREDENTIAL_TTL_SECONDS: int = 3600

# 1:N biometric dedup (cosine similarity in [-1, 1]) -- the real Sybil gate.
# These defaults match the deterministic mock (same person -> ~1.0). A real
# embedding model lives in a different cosine space (ArcFace: same person ~0.5-0.7,
# different ~0-0.2), so `dedup_thresholds()` adapts the defaults to the active
# matcher and lets them be overridden per deployment.
DEDUP_REJECT_THRESHOLD: float = 0.92   # mock default: already enrolled -> block
DEDUP_REVIEW_THRESHOLD: float = 0.86   # mock default: close (twins) -> review

# ArcFace/InsightFace cosine starting points. Tune against the real applicant
# population: lower = catch more duplicates (more reviews / risk of false block),
# higher = fewer false blocks (risk of missed Sybils).
_INSIGHTFACE_REJECT: float = 0.55
_INSIGHTFACE_REVIEW: float = 0.40

FACE_MATCH_MIN_SCORE: float = 0.80     # 1:1 selfie vs passport photo (mock)
LIVENESS_MIN_SCORE: float = 0.70       # self-built challenge-response score


def dedup_thresholds() -> tuple[float, float]:
    """(reject, review) cosine thresholds for 1:N dedup.

    Defaults follow the active face matcher's embedding space so switching to the
    real model doesn't silently disable the Sybil gate. Override either with
    ``KYC_DEDUP_REJECT_COSINE`` / ``KYC_DEDUP_REVIEW_COSINE``.
    """
    if os.environ.get("KYC_FACE_MATCHER", "mock").strip().lower() == "insightface":
        reject_default, review_default = _INSIGHTFACE_REJECT, _INSIGHTFACE_REVIEW
    else:
        reject_default, review_default = DEDUP_REJECT_THRESHOLD, DEDUP_REVIEW_THRESHOLD
    reject = float(os.environ.get("KYC_DEDUP_REJECT_COSINE", reject_default))
    review = float(os.environ.get("KYC_DEDUP_REVIEW_COSINE", review_default))
    return reject, review


@dataclass(frozen=True)
class CountryPolicy:
    iso: str
    name: str
    high_risk: bool = False
    notes: str = ""


COUNTRY_REGISTRY: dict[str, CountryPolicy] = {
    "IN": CountryPolicy("IN", "India"),
    "NG": CountryPolicy("NG", "Nigeria"),
    "BR": CountryPolicy("BR", "Brazil"),
    "MX": CountryPolicy("MX", "Mexico"),
    "CO": CountryPolicy("CO", "Colombia"),
    "AR": CountryPolicy("AR", "Argentina"),
    "VE": CountryPolicy(
        "VE", "Venezuela", high_risk=True,
        notes="Elevated risk: biases to manual review. OFAC exposure via USDC "
              "is a legal question handled outside this system.",
    ),
}

# Passport is the only accepted document, everywhere.
ACCEPTED_ID_TYPES: tuple[str, ...] = ("passport",)
SUPPORTED_COUNTRIES: tuple[str, ...] = tuple(COUNTRY_REGISTRY.keys())


def policy_for(iso: str) -> CountryPolicy:
    iso = iso.upper()
    if iso not in COUNTRY_REGISTRY:
        raise ValueError(f"Unsupported country: {iso}")
    return COUNTRY_REGISTRY[iso]
