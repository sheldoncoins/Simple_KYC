"""Data layer.

Design notes that matter for the product goals:

* IdentityRecord is the unit of uniqueness. The $100 limit and the biometric
  template live here, keyed by `identity_hash`. Wallets/accounts reference an
  identity; spinning up a new wallet cannot create a new identity, because the
  biometric dedup gate collapses them onto the same IdentityRecord.

* No raw PII is exposed to the P2P layer. PII columns live only on this server
  (the "vault"); the credential the P2P layer receives carries only the
  identity_hash + entitlements.

* AuditLog is append-only (we never update or delete rows).
"""
from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class SessionStatus(str, enum.Enum):
    started = "started"
    documents_submitted = "documents_submitted"
    biometrics_submitted = "biometrics_submitted"
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"


class Decision(str, enum.Enum):
    approve = "approve"
    review = "review"
    reject = "reject"


# ---------------------------------------------------------------------------

class User(Base):
    """An applicant + their P2P wallet handle. Contact identifiers live here.

    A User maps to at most one approved IdentityRecord. Many Users can collapse
    onto one IdentityRecord -- that *is* the multi-account that dedup detects.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wallet_pubkey: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    country: Mapped[str] = mapped_column(String(2), index=True)
    phone_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    email_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    device_fingerprint: Mapped[str | None] = mapped_column(String(128), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    identity_id: Mapped[int | None] = mapped_column(ForeignKey("identities.id"))
    identity: Mapped["IdentityRecord | None"] = relationship(back_populates="users")
    sessions: Mapped[list["VerificationSession"]] = relationship(back_populates="user")


class IdentityRecord(Base):
    """The unique human. One row per real person. Limit is bound here."""
    __tablename__ = "identities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Stable opaque handle shared with the P2P layer. Never reveals PII.
    identity_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    country: Mapped[str] = mapped_column(String(2))
    # Face embedding used for 1:N dedup. JSON list[float]. In production this is
    # a vendor template; never store raw selfies alongside it long-term.
    biometric_template: Mapped[list] = mapped_column(JSON)
    limit_usdc: Mapped[float] = mapped_column(Float)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="identity")
    ledger: Mapped[list["LedgerEntry"]] = relationship(back_populates="identity")


class VerificationSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), default=SessionStatus.started)
    # Accumulated signals from each verification stage.
    signals: Mapped[dict] = mapped_column(JSON, default=dict)
    decision: Mapped[Decision | None] = mapped_column(Enum(Decision))
    risk_score: Mapped[float | None] = mapped_column(Float)
    reject_reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(back_populates="sessions")


class LedgerEntry(Base):
    """Append-only debit/credit against an identity's USDC->fiat limit."""
    __tablename__ = "ledger"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ledger_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"), index=True)
    # Positive = consumed limit (debit), negative = restored (credit/refund).
    amount_usdc: Mapped[float] = mapped_column(Float)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    memo: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    identity: Mapped["IdentityRecord"] = relationship(back_populates="ledger")


class ReviewItem(Base):
    __tablename__ = "review_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    reason: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    resolved: Mapped[bool] = mapped_column(default=False)
    resolution: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    """Append-only. Forensics + dispute resolution."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(80), index=True)
    subject: Mapped[str | None] = mapped_column(String(128), index=True)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)


class RevokedCredential(Base):
    """Credential revocation list. Credentials are short-lived, so this only has
    to outlast the TTL; a row revokes either a single token (by ``jti``) or every
    credential for an identity (by ``identity_hash``). Verification checks here."""
    __tablename__ = "revoked_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jti: Mapped[str | None] = mapped_column(String(64), index=True)
    identity_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
