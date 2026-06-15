"""Append-only audit logging."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLog


def record(db: Session, *, actor: str, action: str,
           subject: str | None = None, detail: str | None = None) -> None:
    db.add(AuditLog(actor=actor, action=action, subject=subject, detail=detail))
    db.flush()
