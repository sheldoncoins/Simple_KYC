"""Risk decision engine.

Turns the accumulated signals into approve / review / reject. Hard gates fire
first (a failed gate can't be averaged away); the weighted score only decides
among the survivors and routes borderline cases to a human.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models import Decision


@dataclass
class RiskOutcome:
    decision: Decision
    score: float
    reason: str


def decide(signals: dict, *, high_risk_country: bool) -> RiskOutcome:
    # --- Hard gates -------------------------------------------------------
    if not signals.get("mrz_valid", False):
        return RiskOutcome(Decision.reject, 0.0, "passport_mrz_invalid")
    if not signals.get("liveness_pass", False):
        return RiskOutcome(Decision.reject, 0.0, "liveness_failed")
    if not signals.get("face_match", False):
        return RiskOutcome(Decision.reject, 0.0, "face_mismatch_selfie_vs_passport")

    dedup = signals.get("dedup_outcome", "clear")
    if dedup == "reject":
        return RiskOutcome(Decision.reject, 0.0, "duplicate_identity")

    # --- Weighted score among survivors ----------------------------------
    score = (
        0.45 * min(signals.get("face_match_score", 0.0), 1.0)
        + 0.35 * min(signals.get("liveness_score", 0.0), 1.0)
        + 0.20 * (1.0 - signals.get("device_risk", 0.0))
    )

    # --- Routing to review ------------------------------------------------
    if dedup == "review":
        return RiskOutcome(Decision.review, round(score, 4),
                           "near_duplicate_needs_review")
    if high_risk_country:
        return RiskOutcome(Decision.review, round(score, 4),
                           "high_risk_country_manual_review")
    if score < 0.75:
        return RiskOutcome(Decision.review, round(score, 4), "low_confidence")

    return RiskOutcome(Decision.approve, round(score, 4), "auto_approved")
