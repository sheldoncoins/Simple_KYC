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

### Docker (Postgres + API)

```bash
docker compose up --build          # Postgres + API; runs migrations on start
                                   # API at http://localhost:8000/docs
```

### Local (Python)

```bash
pip install -r requirements.txt          # runtime only
# or: pip install -r requirements-dev.txt # + ruff/mypy/pytest/pre-commit

cp .env.example .env                      # set KYC_DATABASE_URL (Postgres or SQLite)
alembic upgrade head                      # apply schema (Postgres); SQLite works too

python run_demo.py                 # narrated end-to-end demo, no server
python -m pytest tests/ -v         # full test suite (runs on SQLite)
uvicorn app.main:app --reload      # HTTP API at http://127.0.0.1:8000/docs

ruff check . && mypy               # lint + type-check (also enforced in CI)
```

The app is database-agnostic via SQLAlchemy 2.0: **Postgres** is the
production/dev target (`postgresql+psycopg://…`), and **SQLite** is the
zero-config default used by the demo and tests. Schema is owned by **Alembic**
migrations in `migrations/`.

## API

Endpoints marked 🔑 require a P2P client API key (`X-API-Key`); see
`KYC_P2P_API_KEYS` in `.env.example`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/onboard` | start a verification session (rate-limited) |
| POST | `/v1/sessions/{id}/passport` | submit passport MRZ lines (text) |
| POST | `/v1/sessions/{id}/passport/image` | upload passport image → server-side MRZ read → validation |
| GET  | `/v1/liveness/challenge` | issue randomized liveness challenge |
| POST | `/v1/sessions/{id}/biometrics` | submit selfie + liveness → decision (rate-limited) |
| GET  | `/v1/sessions/{id}` | session status + signals |
| POST | `/v1/sessions/{id}/credential` | issue signed credential (if approved) |
| GET  | `/.well-known/jwks.json` | public signing keys (JWKS) for credential verification |
| POST | `/v1/credentials/verify` | 🔑 P2P layer verifies a credential |
| POST | `/v1/credentials/revoke` | 🔑 revoke a credential (by `jti` or `identity_hash`) |
| POST | `/v1/limits/debit` | 🔑 consume limit (idempotent) |
| GET  | `/v1/limits/{identity_hash}` | 🔑 limit balance |
| GET  | `/v1/review` | pending manual-review queue |
| POST | `/v1/review/{item_id}` | resolve a review item |

## Verification wizard (web UI)

`web/` is the applicant-facing wizard (Next.js App Router + TypeScript + Tailwind
+ shadcn-style UI): country/wallet → passport capture → in-browser MediaPipe
liveness → result, against the `/v1` API. Liveness landmark extraction runs
client-side (WASM); only the feature timeline is sent. See `web/README.md`.

```bash
cd web && cp .env.example .env.local && npm install && npm run dev
```

The API enables CORS for the wizard origin via `KYC_CORS_ORIGINS`.

## What's real vs. what to plug in

| Component | Status |
|---|---|
| Passport MRZ validation | **Real** — ICAO 9303 check digits |
| Active liveness protocol + scoring | **Real** — challenge-response, anti-replay |
| 1:N dedup decision logic + thresholds | **Real** — linear cosine scan |
| Credential signing/verification (Ed25519) | **Real** — via swappable `Signer`, with `kid` + JWKS |
| JWKS endpoint + key rotation support | **Real** |
| Credential revocation (by token or identity) | **Real** |
| P2P client auth (API key) + rate limiting | **Real** — in-process limiter |
| Identity-bound limit ledger (idempotent) | **Real** |
| Risk engine, review queue, audit log | **Real** |
| Media storage encrypted at rest + retention/purge | **Real** — local AES-256-GCM; purge job deletes expired raw media |
| KMS/HSM-backed signing | Plug in — implement `KmsSigner` in `app/providers/signer.py` (`KYC_SIGNER=kms`); local Ed25519 is the dev fallback |
| 1:N dedup search backend | **Real** — pluggable; linear scan (default) or **pgvector** ANN (`KYC_DEDUP_BACKEND=pgvector`), decision/thresholds identical |
| S3-compatible object storage | Plug in — `S3Storage` (`KYC_STORAGE_BACKEND=s3`, needs `boto3`); local encrypted store is the dev fallback |
| Passport MRZ OCR (read from image) | Plug in — `PassportEyeMrzReader` (`KYC_MRZ_READER=ocr`); the text reader drives dev/tests. Validation stays deterministic |
| Liveness landmark extraction | Plug in MediaPipe / dlib (self-hosted) |
| Face embedding (1:1 + 1:N) | Plug in `InsightFaceMatcher` (`KYC_FACE_MATCHER=insightface`); the deterministic mock drives dev/tests. Needs real selfie/passport images (UI, Phase 4) |
| Dedup + matching background worker | **Real** — pluggable; inline (default) or **arq + Redis** worker (`KYC_TASK_QUEUE=arq`), client polls session status |

## Production hardening (before real money)

Done in Phase 1: Postgres + Alembic migrations; a swappable `Signer` with a JWKS
endpoint and key-rotation support; P2P client API-key auth; rate limiting on
onboarding + biometric submission; and credential revocation. Done in Phase 2:
media uploads to encrypted-at-rest object storage (local AES-GCM or S3) with a
retention TTL + purge job, and server-side MRZ reading from a passport image
(deterministic validation unchanged). Still outstanding before real money: a real
**KMS/HSM** signer (the `KmsSigner` seam — keys must leave disk); production
object storage on S3/KMS; a real OCR backend; a distributed rate limiter
(Redis/edge); staff auth on the review/admin endpoints; a full DSAR/deletion flow
and DPIA; and a legal review of money-transmission/VASP obligations in each
market. This code does not constitute legal or compliance advice.
