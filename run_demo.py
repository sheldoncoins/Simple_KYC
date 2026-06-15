"""Runnable narrated demo -- no HTTP, direct service calls.

    python run_demo.py

Walks: approve a genuine user, block the same face on a new wallet (Sybil),
reject a mismatched selfie, route a Venezuela applicant to review, then spend
against the $100 limit.
"""
from __future__ import annotations

import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.setdefault("KYC_DATABASE_URL", f"sqlite:///{_tmp}/demo.db")
os.environ.setdefault("KYC_SIGNING_KEY_PATH", f"{_tmp}/key.pem")
# Keep the narrated output readable: only warnings+ from the structured logger.
os.environ.setdefault("KYC_LOG_LEVEL", "WARNING")

from app.logging_config import configure_logging

configure_logging()

from app.db import init_db, session_scope
from app.schemas import BiometricSubmission, DocumentSubmission, OnboardRequest
from app.services import credentials, ledger, liveness, review, verification
from app.services.mrz_demo import make_mrz

FRAMES = {"blink": [{"ear": 0.30}, {"ear": 0.10}, {"ear": 0.30}],
          "turn_left": [{"yaw": -30.0}, {"yaw": 0.0}],
          "turn_right": [{"yaw": 30.0}, {"yaw": 0.0}],
          "smile": [{"mar": 0.70}, {"mar": 0.10}]}


def frames_for(seq):
    out = []
    for a in seq:
        out += FRAMES[a]
    return out


def enroll(wallet, country, seed, selfie_seed=None, good=True):
    selfie_seed = selfie_seed or seed
    with session_scope() as db:
        sess = verification.onboard(db, OnboardRequest(wallet_pubkey=wallet, country=country))
        sid = sess.id
        l1, l2 = make_mrz()
        verification.submit_passport(db, sid, DocumentSubmission(
            mrz_line1=l1, mrz_line2=l2, person_seed=seed))
    ch = liveness.issue_challenge(2)
    frames = frames_for(ch.sequence) if good else [{"ear": 0.3}]
    with session_scope() as db:
        sess = verification.submit_biometrics(
            db, sid, BiometricSubmission(selfie_ref="s", person_seed=selfie_seed),
            ch.nonce, frames)
        assert sess.decision is not None  # set once biometrics are scored
        return sid, sess.decision.value, sess.reject_reason


def line(label, value):
    print(f"   {label:<22} {value}")


def main():
    init_db()
    print("\n=== 1. Genuine applicant (Brazil) ===")
    sid, decision, reason = enroll("wallet_alice", "BR", "alice")
    line("decision", decision)
    with session_scope() as db:
        from app.models import User
        alice = db.query(User).filter_by(wallet_pubkey="wallet_alice").one()
        assert alice.identity is not None  # approved above, so identity is bound
        ih = alice.identity.identity_hash
        token, _ = credentials.issue(ih, "wallet_alice", 100.0)
    claims = credentials.verify(token)
    line("identity_hash", ih[:24] + "...")
    line("credential.unique", claims["unique"])
    line("credential.verified", claims["verified"])

    print("\n=== 2. SAME face, new wallet + new passport (Sybil attempt) ===")
    _, decision, reason = enroll("wallet_alice_alt", "BR", "alice")
    line("decision", decision)
    line("reason", reason)

    print("\n=== 3. Selfie does not match the passport ===")
    _, decision, reason = enroll("wallet_carol", "AR", "carol_passport", selfie_seed="stranger")
    line("decision", decision)
    line("reason", reason)

    print("\n=== 4. Venezuela -> mandatory manual review ===")
    sid, decision, reason = enroll("wallet_frank", "VE", "frank")
    line("decision", decision)
    line("reason", reason)
    with session_scope() as db:
        item = next(i for i in review.pending(db) if i.session_id == sid)
        sess = review.resolve(db, item.id, "approve", "reviewer_1")
        line("after review", sess.status.value)

    print("\n=== 5. Spend against the $100 limit (bound to identity) ===")
    with session_scope() as db:
        b = ledger.debit(db, ih, 70, "tx-001", "cash-out")
        line("after $70 debit", f"remaining ${b.remaining_usdc}")
        try:
            ledger.debit(db, ih, 50, "tx-002", "cash-out")
        except ledger.LimitError as e:
            line("$50 more", f"blocked -> {e}")
        b = ledger.debit(db, ih, 70, "tx-001", "retry")  # idempotent
        line("retry tx-001", f"remaining ${b.remaining_usdc} (no double-spend)")

    print("\nDone.\n")


if __name__ == "__main__":
    main()
