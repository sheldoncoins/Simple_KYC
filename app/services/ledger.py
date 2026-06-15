"""USDC->fiat limit ledger.

Bound to the IDENTITY, not the wallet -- a new wallet cannot reset the limit
because dedup collapses it onto the same identity. Debits are idempotent so a
retried conversion can't double-spend the allowance.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import IdentityRecord, LedgerEntry


@dataclass
class Balance:
    identity_hash: str
    limit_usdc: float
    consumed_usdc: float
    remaining_usdc: float


class LimitError(Exception):
    pass


def _identity(db: Session, identity_hash: str) -> IdentityRecord:
    rec = db.scalar(select(IdentityRecord).where(
        IdentityRecord.identity_hash == identity_hash))
    if rec is None:
        raise LimitError("unknown_identity")
    return rec


def balance(db: Session, identity_hash: str) -> Balance:
    rec = _identity(db, identity_hash)
    consumed = db.scalar(
        select(func.coalesce(func.sum(LedgerEntry.amount_usdc), 0.0))
        .where(LedgerEntry.identity_id == rec.id)
    ) or 0.0
    return Balance(identity_hash, rec.limit_usdc, round(consumed, 2),
                   round(rec.limit_usdc - consumed, 2))


def debit(db: Session, identity_hash: str, amount: float,
          idempotency_key: str, memo: str | None = None) -> Balance:
    rec = _identity(db, identity_hash)

    existing = db.scalar(select(LedgerEntry).where(
        LedgerEntry.idempotency_key == idempotency_key))
    if existing is not None:
        return balance(db, identity_hash)  # idempotent replay

    bal = balance(db, identity_hash)
    if amount > bal.remaining_usdc + 1e-9:
        raise LimitError(
            f"limit_exceeded: requested {amount}, remaining {bal.remaining_usdc}")

    db.add(LedgerEntry(identity_id=rec.id, amount_usdc=amount,
                       idempotency_key=idempotency_key, memo=memo))
    db.flush()
    return balance(db, identity_hash)
