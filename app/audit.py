"""Append-only audit logging."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models import AuditLog

_log = get_logger("audit")


def record(db: Session, *, actor: str, action: str,
           subject: str | None = None, detail: str | None = None) -> None:
    db.add(AuditLog(actor=actor, action=action, subject=subject, detail=detail))
    db.flush()
    # Mirror the durable audit row to the structured log stream. Every
    # state-changing action already funnels through here, so this is the one
    # honest place to observe them. Fields are ids/actions only -- never PII.
    _log.info("audit", actor=actor, action=action, subject=subject, detail=detail)
