"""FastAPI surface for the KYC verification server.

Endpoints map 1:1 to the product flow:
  POST /v1/onboard                       start a session
  POST /v1/sessions/{id}/passport        submit passport (MRZ validated)
  GET  /v1/liveness/challenge            issue a randomized liveness challenge
  POST /v1/sessions/{id}/biometrics      submit selfie + liveness -> decision
  GET  /v1/sessions/{id}                 session status + signals
  POST /v1/sessions/{id}/credential      issue signed credential (if approved)
  POST /v1/credentials/verify            P2P layer verifies a credential
  POST /v1/limits/debit                  consume USDC->fiat limit (idempotent)
  GET  /v1/limits/{identity_hash}        limit balance
  GET  /v1/review                        pending review queue
  POST /v1/review/{item_id}              resolve a review item
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

import jwt
import structlog
from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import ACCEPTED_ID_TYPES, policy_for
from app.db import get_session, init_db
from app.logging_config import configure_logging, get_logger
from app.models import SessionStatus
from app.providers.registry import signer
from app.schemas import (
    BiometricSubmission,
    CredentialResponse,
    DebitRequest,
    DocumentSubmission,
    LedgerResponse,
    OnboardRequest,
    OnboardResponse,
    ReviewResolution,
    RevokeRequest,
    RevokeResponse,
    StatusResponse,
    VerifyCredentialRequest,
    VerifyCredentialResponse,
)
from app.security import rate_limit, require_p2p_client
from app.services import credentials, ledger, liveness, review, revocation, verification

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    init_db()
    log.info("startup", service="kyc", version="1.0")
    yield


app = FastAPI(title="KYC Verification Server", version="1.0", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Emit one structured event per request with a correlation id.

    The id is bound into contextvars so any log emitted while handling the
    request carries it too. Only method/path/status/duration are logged -- never
    request bodies, which may hold PII.
    """
    request_id = uuid.uuid4().hex
    structlog.contextvars.bind_contextvars(request_id=request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    log.info(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=elapsed_ms,
    )
    response.headers["X-Request-ID"] = request_id
    structlog.contextvars.clear_contextvars()
    return response


@app.get("/.well-known/jwks.json")
def jwks():
    """Public signing keys (JWKS). The P2P layer fetches these to verify
    credentials; publishing keys here is what makes key rotation non-breaking."""
    return signer().jwks()


@app.post("/v1/onboard", response_model=OnboardResponse,
          dependencies=[Depends(rate_limit("onboard"))])
def onboard(req: OnboardRequest, db: Session = Depends(get_session)):
    try:
        policy = policy_for(req.country)
    except ValueError as e:
        raise HTTPException(400, str(e))
    sess = verification.onboard(db, req)
    return OnboardResponse(session_id=sess.id, status=sess.status.value,
                           accepted_id_types=list(ACCEPTED_ID_TYPES),
                           notes=policy.notes)


@app.post("/v1/sessions/{session_id}/passport", response_model=StatusResponse)
def submit_passport(session_id: int, sub: DocumentSubmission,
                    db: Session = Depends(get_session)):
    try:
        sess = verification.submit_passport(db, session_id, sub)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return _status(sess)


@app.get("/v1/liveness/challenge")
def liveness_challenge(actions: int = 2):
    ch = liveness.issue_challenge(actions)
    return {"nonce": ch.nonce, "sequence": ch.sequence,
            "ttl_seconds": liveness.CHALLENGE_TTL_SECONDS}


@app.post("/v1/sessions/{session_id}/biometrics", response_model=StatusResponse,
          dependencies=[Depends(rate_limit("biometric"))])
def submit_biometrics(session_id: int, sub: BiometricSubmission,
                      liveness_nonce: str, frames: list[dict],
                      db: Session = Depends(get_session)):
    try:
        sess = verification.submit_biometrics(db, session_id, sub, liveness_nonce, frames)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return _status(sess)


@app.get("/v1/sessions/{session_id}", response_model=StatusResponse)
def session_status(session_id: int, db: Session = Depends(get_session)):
    from app.models import VerificationSession
    sess = db.get(VerificationSession, session_id)
    if sess is None:
        raise HTTPException(404, "session_not_found")
    return _status(sess)


@app.post("/v1/sessions/{session_id}/credential", response_model=CredentialResponse)
def issue_credential(session_id: int, db: Session = Depends(get_session)):
    from app.models import User, VerificationSession
    sess = db.get(VerificationSession, session_id)
    if sess is None:
        raise HTTPException(404, "session_not_found")
    if sess.status != SessionStatus.approved:
        raise HTTPException(409, f"not_approved: status={sess.status.value}")
    user = db.get(User, sess.user_id)
    # Invariants for an approved session: the user exists (FK) and its identity
    # was bound during finalization. Assert to narrow the Optionals for mypy.
    assert user is not None and user.identity is not None
    bal = ledger.balance(db, user.identity.identity_hash)
    token, ttl = credentials.issue(user.identity.identity_hash,
                                    user.wallet_pubkey, bal.remaining_usdc)
    return CredentialResponse(credential=token, expires_in=ttl,
                              identity_hash=user.identity.identity_hash,
                              limit_remaining_usdc=bal.remaining_usdc)


@app.post("/v1/credentials/verify", response_model=VerifyCredentialResponse)
def verify_credential(req: VerifyCredentialRequest,
                      db: Session = Depends(get_session),
                      _: str = Depends(require_p2p_client)):
    try:
        claims = credentials.verify(req.credential, db)
        return VerifyCredentialResponse(valid=True, claims=claims)
    except credentials.RevokedCredentialError:
        return VerifyCredentialResponse(valid=False, error="revoked")
    except jwt.PyJWTError as e:
        return VerifyCredentialResponse(valid=False, error=str(e))


@app.post("/v1/credentials/revoke", response_model=RevokeResponse)
def revoke_credential(req: RevokeRequest,
                      db: Session = Depends(get_session),
                      client: str = Depends(require_p2p_client)):
    try:
        revocation.revoke(db, jti=req.jti, identity_hash=req.identity_hash,
                          reason=req.reason, actor=client)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RevokeResponse(revoked=True)


@app.post("/v1/limits/debit", response_model=LedgerResponse)
def debit_limit(req: DebitRequest, db: Session = Depends(get_session),
                _: str = Depends(require_p2p_client)):
    try:
        bal = ledger.debit(db, req.identity_hash, req.amount_usdc,
                           req.idempotency_key, req.memo)
    except ledger.LimitError as e:
        raise HTTPException(409, str(e))
    return LedgerResponse(**bal.__dict__)


@app.get("/v1/limits/{identity_hash}", response_model=LedgerResponse)
def limit_balance(identity_hash: str, db: Session = Depends(get_session),
                  _: str = Depends(require_p2p_client)):
    try:
        bal = ledger.balance(db, identity_hash)
    except ledger.LimitError as e:
        raise HTTPException(404, str(e))
    return LedgerResponse(**bal.__dict__)


@app.get("/v1/review")
def review_queue(db: Session = Depends(get_session)):
    return [{"item_id": i.id, "session_id": i.session_id, "reason": i.reason,
             "payload": i.payload} for i in review.pending(db)]


@app.post("/v1/review/{item_id}", response_model=StatusResponse)
def resolve_review(item_id: int, res: ReviewResolution,
                   db: Session = Depends(get_session)):
    try:
        sess = review.resolve(db, item_id, res.resolution, res.reviewer)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return _status(sess)


def _status(sess) -> StatusResponse:
    return StatusResponse(
        session_id=sess.id, status=sess.status.value,
        decision=sess.decision.value if sess.decision else None,
        risk_score=sess.risk_score, reject_reason=sess.reject_reason,
        signals={k: v for k, v in sess.signals.items() if k != "embedding"},
    )
