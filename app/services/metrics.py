"""Aggregate metrics for the staff dashboard.

Approval/rejection/review rates, the dedup hit rate, the liveness pass rate, and
a per-country breakdown -- derived from the verification sessions and their
signals. This walks all sessions, which is fine at reference scale; production
should back the dashboard with rollups / materialized views.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, VerificationSession

_DECISIONS = ("approve", "review", "reject")


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def summary(db: Session) -> dict:
    rows = db.execute(
        select(VerificationSession, User.country).join(
            User, VerificationSession.user_id == User.id
        )
    ).all()

    total = len(rows)
    decided = 0
    by_decision = {d: 0 for d in _DECISIONS}
    dedup_total = dedup_hits = 0
    live_total = live_pass = 0
    per_country: dict[str, dict[str, int]] = {}

    for sess, country in rows:
        bucket = per_country.setdefault(
            country, {"total": 0, "approve": 0, "review": 0, "reject": 0}
        )
        bucket["total"] += 1

        if sess.decision is not None:
            decided += 1
            name = sess.decision.value
            by_decision[name] = by_decision.get(name, 0) + 1
            bucket[name] = bucket.get(name, 0) + 1

        signals = sess.signals or {}
        if "dedup_outcome" in signals:
            dedup_total += 1
            if signals.get("dedup_outcome") != "clear":
                dedup_hits += 1
        if "liveness_pass" in signals:
            live_total += 1
            if signals.get("liveness_pass"):
                live_pass += 1

    return {
        "total_sessions": total,
        "decided": decided,
        "decisions": by_decision,
        "rates": {d: _rate(by_decision[d], decided) for d in _DECISIONS},
        "dedup_hit_rate": _rate(dedup_hits, dedup_total),
        "liveness_pass_rate": _rate(live_pass, live_total),
        "per_country": per_country,
    }
