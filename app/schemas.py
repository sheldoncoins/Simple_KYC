"""API request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class OnboardRequest(BaseModel):
    wallet_pubkey: str = Field(..., min_length=8, max_length=128)
    country: str = Field(..., min_length=2, max_length=2)
    phone: str | None = None
    email: str | None = None
    device_fingerprint: str | None = None


class OnboardResponse(BaseModel):
    session_id: int
    status: str
    accepted_id_types: list[str]
    notes: str


class DocumentSubmission(BaseModel):
    id_type: str = "passport"
    # Passport MRZ (two lines, 44 chars each) -- validated via ICAO 9303 check
    # digits. In production these are read from the document image via OCR/MRZ.
    mrz_line1: str = ""
    mrz_line2: str = ""
    # A stable per-person seed so the demo can simulate 'same human, new doc'.
    person_seed: str = Field(..., description="Simulates the real human behind the doc")


class BiometricSubmission(BaseModel):
    selfie_ref: str
    # Same seed as the document for a genuine applicant; a different seed
    # simulates a face that doesn't match the ID.
    person_seed: str


class StatusResponse(BaseModel):
    session_id: int
    status: str
    decision: str | None
    risk_score: float | None
    reject_reason: str | None
    signals: dict


class CredentialResponse(BaseModel):
    credential: str
    expires_in: int
    identity_hash: str
    limit_remaining_usdc: float


class VerifyCredentialRequest(BaseModel):
    credential: str


class VerifyCredentialResponse(BaseModel):
    valid: bool
    claims: dict | None = None
    error: str | None = None


class DebitRequest(BaseModel):
    identity_hash: str
    amount_usdc: float = Field(..., gt=0)
    idempotency_key: str
    memo: str | None = None


class LedgerResponse(BaseModel):
    identity_hash: str
    limit_usdc: float
    consumed_usdc: float
    remaining_usdc: float


class ReviewResolution(BaseModel):
    resolution: str = Field(..., pattern="^(approve|reject)$")
    reviewer: str = "manual_reviewer"


class RevokeRequest(BaseModel):
    # Target a single token (jti) or an entire identity (identity_hash).
    jti: str | None = None
    identity_hash: str | None = None
    reason: str = Field("manual", max_length=255)


class RevokeResponse(BaseModel):
    revoked: bool


# --- Admin / review console -------------------------------------------------


class ReviewListItem(BaseModel):
    item_id: int
    session_id: int
    reason: str
    payload: dict
    country: str | None
    status: str
    decision: str | None
    risk_score: float | None
    signals: dict
    created_at: str


class AuditEntry(BaseModel):
    id: int
    actor: str
    action: str
    subject: str | None
    detail: str | None
    created_at: str


class MetricsSummary(BaseModel):
    total_sessions: int
    decided: int
    decisions: dict[str, int]
    rates: dict[str, float]
    dedup_hit_rate: float
    liveness_pass_rate: float
    per_country: dict[str, dict[str, int]]
