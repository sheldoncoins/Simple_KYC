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
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_LIMIT_USDC: float = 100.0
CREDENTIAL_TTL_SECONDS: int = 3600

# 1:N biometric dedup (cosine similarity in [-1, 1]) -- the real Sybil gate.
DEDUP_REJECT_THRESHOLD: float = 0.92   # same person already enrolled -> block
DEDUP_REVIEW_THRESHOLD: float = 0.86   # close (e.g. twins) -> human review

FACE_MATCH_MIN_SCORE: float = 0.80     # 1:1 selfie vs passport photo
LIVENESS_MIN_SCORE: float = 0.70       # self-built challenge-response score


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
