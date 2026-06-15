"""Orchestration: onboarding and the verification pipeline.

Pipeline order matches the product-flow diagram:
  phone/email dedup -> passport MRZ -> selfie+liveness -> 1:1 face match
  -> 1:N biometric dedup -> risk decision -> identity + credential.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.config import DEFAULT_LIMIT_USDC, policy_for
from app.crypto import identity_hash as make_identity_hash
from app.crypto import pii_hash
from app.models import Decision, IdentityRecord, SessionStatus, User, VerificationSession
from app.providers.registry import face_matcher
from app.schemas import BiometricSubmission, DocumentSubmission, OnboardRequest
from app.services import dedup, liveness, review, risk
from app.services.mrz import validate_td3

# --- Onboarding -----------------------------------------------------------

def onboard(db: Session, req: OnboardRequest) -> VerificationSession:
    policy = policy_for(req.country)  # raises on unsupported country

    user = db.scalar(select(User).where(User.wallet_pubkey == req.wallet_pubkey))
    if user is None:
        user = User(wallet_pubkey=req.wallet_pubkey, country=req.country.upper())
        db.add(user)
    user.phone_hash = pii_hash(req.phone) if req.phone else None
    user.email_hash = pii_hash(req.email) if req.email else None
    user.device_fingerprint = req.device_fingerprint
    db.flush()

    # Cheap pre-signal: contact/device collisions (account-farm indicator).
    device_risk = _device_risk(db, user)

    sess = VerificationSession(
        user_id=user.id, status=SessionStatus.started,
        signals={"device_risk": device_risk,
                 "high_risk_country": policy.high_risk},
    )
    db.add(sess)
    db.flush()
    audit.record(db, actor=req.wallet_pubkey, action="onboard_started",
                 subject=str(sess.id), detail=req.country)
    return sess


def _device_risk(db: Session, user: User) -> float:
    risk = 0.0
    if user.phone_hash:
        dup = db.scalar(select(User).where(User.phone_hash == user.phone_hash,
                                           User.id != user.id))
        if dup:
            risk += 0.5
    if user.device_fingerprint:
        dup = db.scalar(select(User).where(
            User.device_fingerprint == user.device_fingerprint, User.id != user.id))
        if dup:
            risk += 0.5
    return min(risk, 1.0)


# --- Document stage -------------------------------------------------------

def submit_passport(db: Session, session_id: int, sub: DocumentSubmission) -> VerificationSession:
    sess = _get(db, session_id)
    if sub.id_type != "passport":
        sess.signals = {**sess.signals, "mrz_valid": False}
        sess.status = SessionStatus.documents_submitted
        db.flush()
        return sess

    mrz = validate_td3(sub.mrz_line1, sub.mrz_line2)
    sess.signals = {
        **sess.signals,
        "mrz_valid": mrz.valid,
        "mrz_failed_checks": mrz.failed_checks,
        "passport_country": mrz.extracted.get("issuing_country"),
        "passport_person_seed": sub.person_seed,  # binds the doc's 'face'
    }
    sess.status = SessionStatus.documents_submitted
    audit.record(db, actor="system", action="passport_submitted",
                 subject=str(sess.id), detail=f"valid={mrz.valid}")
    db.flush()
    return sess


# --- Biometric stage + decision ------------------------------------------

def submit_biometrics(db: Session, session_id: int, sub: BiometricSubmission,
                      liveness_nonce: str, frames: list[dict]) -> VerificationSession:
    sess = _get(db, session_id)
    sess.status = SessionStatus.biometrics_submitted

    live = liveness.verify_response(liveness_nonce, frames)

    passport_seed = sess.signals.get("passport_person_seed", "")
    fm = face_matcher().match(selfie_ref=sub.selfie_ref, person_seed=sub.person_seed,
                              passport_person_seed=passport_seed)

    dd = dedup.search(db, fm.embedding)

    sess.signals = {
        **sess.signals,
        "liveness_pass": live.is_live, "liveness_score": live.score,
        "face_match": fm.match, "face_match_score": fm.score,
        "dedup_outcome": dd.outcome, "dedup_score": dd.best_score,
        "dedup_match": dd.match_identity_hash,
        "embedding": fm.embedding, "person_seed": sub.person_seed,
    }

    outcome = risk.decide(sess.signals, high_risk_country=sess.signals["high_risk_country"])
    sess.risk_score = outcome.score
    sess.decision = outcome.decision

    if outcome.decision == Decision.reject:
        sess.status = SessionStatus.rejected
        sess.reject_reason = outcome.reason
    elif outcome.decision == Decision.review:
        sess.status = SessionStatus.pending_review
        review.enqueue(db, sess.id, outcome.reason,
                       {"dedup_score": dd.best_score})
    else:
        finalize_identity(db, sess)

    audit.record(db, actor="system", action="decision",
                 subject=str(sess.id), detail=f"{outcome.decision.value}:{outcome.reason}")
    db.flush()
    return sess


def finalize_identity(db: Session, sess: VerificationSession) -> IdentityRecord:
    """Create the unique IdentityRecord and bind the limit. Used by both
    auto-approval and manual review approval."""
    user = db.get(User, sess.user_id)
    assert user is not None  # FK invariant: a session always has its user
    ih = make_identity_hash(user.country, sess.signals["person_seed"])

    rec = db.scalar(select(IdentityRecord).where(IdentityRecord.identity_hash == ih))
    if rec is None:
        rec = IdentityRecord(
            identity_hash=ih, country=user.country,
            biometric_template=sess.signals["embedding"],
            limit_usdc=DEFAULT_LIMIT_USDC,
        )
        db.add(rec)
        db.flush()
        # Register the new identity with the dedup search backend (no-op for the
        # linear scan; stores the vector for pgvector ANN search).
        dedup.index_identity(db, rec.identity_hash, rec.biometric_template)
    user.identity_id = rec.id
    sess.status = SessionStatus.approved
    sess.decision = Decision.approve
    db.flush()
    return rec


def mark_biometrics_received(db: Session, session_id: int) -> VerificationSession:
    """Async path: record that biometrics arrived and flip the session to
    ``biometrics_submitted`` so a polling client sees "processing" until the
    worker runs ``submit_biometrics`` and writes the decision."""
    sess = _get(db, session_id)
    sess.status = SessionStatus.biometrics_submitted
    db.flush()
    return sess


def _get(db: Session, session_id: int) -> VerificationSession:
    sess = db.get(VerificationSession, session_id)
    if sess is None:
        raise ValueError("session_not_found")
    return sess
