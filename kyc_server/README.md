# KYC verification server (P2P, USDC→fiat)

A centralized KYC service for a P2P protocol. It verifies users, blocks
multi-accounting (Sybil resistance), and grants each **unique human** up to
**$100** of USDC→fiat conversion. The P2P layer receives a short-lived signed
credential — never the user's PII.

This is a **runnable reference implementation**. Every endpoint works and the
test suite passes. The only piece that needs a real model swapped in is face
embedding (see "What's real vs. what to plug in").

## Scope (as configured)

* **Passport only.** No local government IDs, no government-rail lookups.
  Passport integrity is checked with deterministic **ICAO 9303 MRZ check
  digits** (`app/services/mrz.py`) — free, offline, no vendor, no ML.
* **Self-built liveness.** Active challenge-response
  (`app/services/liveness.py`): randomized action sequence + single-use nonce.
  Only the per-frame landmark extraction needs an open-source, self-hosted
  model (MediaPipe Face Mesh / dlib) — not a paid SaaS.
* **No sanctions/PEP screening.** (Venezuela + USDC/OFAC remains a legal
  question handled outside this system; `VE` still routes to manual review.)

Net result: **no paid third-party KYC vendor is required** — only self-hosted
open-source models.

## The Sybil gate

Document and phone checks don't stop one person opening many accounts — a new
wallet, a new passport, and a new SIM are cheap. The **1:N biometric dedup**
(`app/services/dedup.py`) is the actual defense: every new selfie is searched
against all enrolled identities, and a match blocks the new account. The $100
limit is bound to the **identity**, not the wallet, so a fresh keypair can't
reset it.

## Pipeline

```
onboard → passport MRZ → selfie + liveness → 1:1 face match
        → 1:N biometric dedup → risk decision → identity + signed credential
```

Risk decisions: hard gates (MRZ, liveness, 1:1 match, dedup-reject) fire first;
a weighted score then routes survivors to approve / manual review. High-risk
countries and near-duplicates (e.g. twins) go to review.

## Run it

```bash
pip install -r requirements.txt

python run_demo.py                 # narrated end-to-end demo, no server
python -m pytest tests/ -v         # full test suite (8 tests)
uvicorn app.main:app --reload      # HTTP API at http://127.0.0.1:8000/docs
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/onboard` | start a verification session |
| POST | `/v1/sessions/{id}/passport` | submit passport (MRZ validated) |
| GET  | `/v1/liveness/challenge` | issue randomized liveness challenge |
| POST | `/v1/sessions/{id}/biometrics` | submit selfie + liveness → decision |
| GET  | `/v1/sessions/{id}` | session status + signals |
| POST | `/v1/sessions/{id}/credential` | issue signed credential (if approved) |
| POST | `/v1/credentials/verify` | P2P layer verifies a credential |
| POST | `/v1/limits/debit` | consume limit (idempotent) |
| GET  | `/v1/limits/{identity_hash}` | limit balance |
| GET  | `/v1/review` | pending manual-review queue |
| POST | `/v1/review/{item_id}` | resolve a review item |

## What's real vs. what to plug in

| Component | Status |
|---|---|
| Passport MRZ validation | **Real** — ICAO 9303 check digits |
| Active liveness protocol + scoring | **Real** — challenge-response, anti-replay |
| 1:N dedup decision logic + thresholds | **Real** — linear cosine scan |
| Credential signing/verification (Ed25519) | **Real** |
| Identity-bound limit ledger (idempotent) | **Real** |
| Risk engine, review queue, audit log | **Real** |
| Liveness landmark extraction | Plug in MediaPipe / dlib (self-hosted) |
| Face embedding (1:1 + 1:N) | Plug in InsightFace/ArcFace (self-hosted) or a face API — implement `FaceMatcher` in `app/providers/face.py` |
| Dedup index at scale | Swap linear scan for FAISS / pgvector (logic unchanged) |

## Production hardening (before real money)

Key in a KMS/HSM (not on disk); Postgres instead of SQLite; rate limiting and
abuse controls on onboarding; encryption at rest for biometric templates +
strict retention/deletion under DPDP/LGPD/NDPA; revocation list for
credentials; and a legal review of money-transmission/VASP obligations in each
market. This code does not constitute legal or compliance advice.
