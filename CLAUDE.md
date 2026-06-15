# CLAUDE.md

Project memory for Claude Code. Read this before making changes.

## What this is

A centralized KYC verification service for a **P2P USDC↔fiat protocol**. It
verifies users, blocks multi-accounting (Sybil resistance), and grants each
**unique human** up to **$100** of USDC→fiat conversion. The P2P layer receives
a short-lived signed credential — **never** the user's PII.

The current repo is a **tested reference backend** (FastAPI + SQLAlchemy,
`python -m pytest tests/` is green). The job now is to harden it for production
and build the UI. See `BUILD_PLAN.md` for the phased roadmap.

## Hard scope decisions (do not silently revisit)

- **Passport only.** No local government IDs, no government-rail lookups.
  Passport integrity = ICAO 9303 MRZ check digits (`app/services/mrz.py`).
- **Self-built liveness.** Active challenge-response (`app/services/liveness.py`):
  randomized action sequence + single-use nonce. Landmark extraction runs on a
  self-hosted open-source model (MediaPipe Face Mesh / dlib) — **prefer running
  it client-side in the browser (MediaPipe Tasks WASM)** so raw video can stay
  off the server. No paid liveness vendor.
- **No sanctions/PEP screening.** Removed by product decision. `VE` (Venezuela)
  still routes to manual review on risk grounds.
- **Face embedding is a swappable model** (`app/providers/face.py`,
  `FaceMatcher` interface). `InsightFaceMatcher` (ArcFace) is implemented and does
  the real 1:1 selfie↔passport compare on the actual images
  (`KYC_FACE_MATCHER=insightface`); the deterministic seed-based mock is the
  default for dev/tests. The matcher takes a `FaceMatchInput` (seeds for the mock,
  image bytes for the real model); the selfie is captured in-browser during
  liveness and the passport photo is the stored document image.
- **Credential signing is swappable too** (`app/providers/signer.py`, `Signer`
  interface). `LocalEd25519Signer` is the dev fallback; `KmsSigner` is the
  production seam (`KYC_SIGNER=kms`) and is intentionally unimplemented -- don't
  fake it. Tokens carry a `kid`; public keys are served at `/.well-known/jwks.json`.
- **Media storage and MRZ-OCR are swappable seams too**
  (`app/providers/storage.py`, `app/providers/mrz_reader.py`). Local encrypted
  storage + a text MRZ reader drive dev/tests; `S3Storage` and
  `PassportEyeMrzReader` are the production seams (`KYC_STORAGE_BACKEND=s3`,
  `KYC_MRZ_READER=ocr`). Raw uploads are encrypted at rest and purged after a
  retention TTL (`app/services/retention.py`, `app/jobs/purge_media.py`) -- only
  derived templates persist. MRZ *validation* stays deterministic regardless of
  how the lines were read.
- **The dedup search backend is pluggable** (`app/providers/dedup_index.py`):
  `LinearScanIndex` (default) or `PgVectorIndex` (`KYC_DEDUP_BACKEND=pgvector`).
  The reject/review thresholds and twin handling in `services/dedup.py` are
  identical across backends -- only the nearest-neighbour search changes. New
  enrollments call `dedup.index_identity(...)` (a no-op for linear).
- **Biometric processing is dispatchable** (`app/providers/task_queue.py`):
  `InlineTaskQueue` (default, synchronous) or `ArqTaskQueue`
  (`KYC_TASK_QUEUE=arq`, Redis + `app/worker.py`). Async path returns
  `biometrics_submitted` and the client polls `GET /v1/sessions/{id}`. The
  decision logic in `verification.submit_biometrics` is the same either way.

## The one idea everything protects

The **1:N biometric dedup** (`app/services/dedup.py`) is the Sybil gate.
Documents and phones are cheap to replace; the face is not. The $100 limit is
bound to the **identity**, not the wallet (`app/services/ledger.py`), so a new
keypair cannot reset it. Never let a code change make the limit wallet-scoped.

Dedup thresholds live in the face matcher's cosine space, so they adapt to the
active matcher (`config.dedup_thresholds()`): mock 0.92/0.86, InsightFace/ArcFace
0.55/0.40 (override via `KYC_DEDUP_REJECT_COSINE`/`_REVIEW_COSINE`). Switching to
a real matcher must not silently disable the gate -- keep the defaults calibrated.

## Pipeline (matches the product flow)

```
onboard → passport MRZ → selfie + liveness → 1:1 face match
        → 1:N dedup → risk decision → identity + Ed25519 credential
```

Hard gates (MRZ, liveness, 1:1 match, dedup-reject) fire before the weighted
risk score in `app/services/risk.py`. Near-duplicates (twins) and high-risk
countries go to the manual review queue.

## Markets

India, Nigeria, Brazil, Mexico, Colombia, Argentina, Venezuela
(`app/config.py: COUNTRY_REGISTRY`). VE is `high_risk=True`.

## Layout

```
app/
  config.py        policy, thresholds, country registry
  db.py            SQLAlchemy engine/session (Postgres via psycopg; SQLite for dev/tests)
  models.py        ORM: User, IdentityRecord, VerificationSession, LedgerEntry,
                   ReviewItem, AuditLog, RevokedCredential, MediaObject
  schemas.py       Pydantic request/response
  crypto.py        Ed25519 key load + PII hashing (key handling wrapped by Signer)
  audit.py         append-only audit log + structured log mirror
  security.py      P2P (X-API-Key) + staff (X-Admin-Key) auth + rate limiter
  observability.py Prometheus HTTP + domain metrics (/metrics)
  tracing.py       OpenTelemetry tracing seam (off unless KYC_OTEL_ENABLED)
  logging_config.py structlog setup
  main.py          FastAPI routes (/v1/..., JWKS at /.well-known/jwks.json)
  providers/       FaceMatcher + Signer + ObjectStorage + MrzReader + DedupIndex
                   interfaces, mocks/local fallbacks + registry (swap point)
  services/        mrz, liveness, dedup, risk, credentials, ledger, review,
                   revocation, media, retention, metrics, verification (orchestrator)
  jobs/            purge_media (retention deletion job)
  worker.py        arq background worker (biometric decision off the request path)
migrations/        Alembic env + versioned schema (owns the schema in prod)
Dockerfile, docker-compose.yml   local dev stack: api + postgres
tests/             pytest suite (conftest + _helpers shared)
run_demo.py        narrated no-HTTP demo
```

## Conventions (match existing style)

- Python 3.12, type hints everywhere, `from __future__ import annotations`.
- SQLAlchemy 2.0 mapped-style models.
- Docstrings explain **why**, in prose, not just what.
- New vendor-replaceable capabilities go behind an interface in `providers/`,
  never inline in services.
- Append-only `audit.record(...)` for any state-changing action.
- Structured logging via `structlog`: get a logger with
  `logging_config.get_logger(__name__)`, log events as key/value pairs (not
  f-strings), and never log PII -- ids/hashes/decisions only.
- Tests must stay green; add a test for every new decision path.

## Commands

```bash
pip install -r requirements-dev.txt   # runtime + tooling (deps are pinned)
pre-commit install                    # ruff + mypy + hygiene hooks on commit

python -m pytest tests/ -v        # full suite
python run_demo.py                # narrated flow
uvicorn app.main:app --reload     # API at /docs

ruff check .                      # lint (E/F/W/I; E501 -> formatter)
mypy                              # type-check app/ + run_demo.py

docker compose up --build         # Postgres + API (migrations run on start)
alembic upgrade head              # apply schema; alembic revision --autogenerate -m "msg"
```

Database: Postgres in prod/dev (`postgresql+psycopg://…` via `KYC_DATABASE_URL`),
SQLite for the demo/tests. Alembic (`migrations/`) owns the schema; after
changing `models.py`, generate a migration and keep `migrations/` excluded from
ruff (it is Alembic-managed).

Tooling config lives in `pyproject.toml`; CI (`.github/workflows/ci.yml`) runs
lint + type-check + tests on every push. Copy `.env.example` -> `.env` for the
environment variables the app reads.

## Guardrails for changes

- Do **not** describe the system as production-ready until the `BUILD_PLAN.md`
  hardening phase is done (KMS, Postgres, auth, rate limiting, encrypted
  storage, retention).
- Biometric storage triggers data-protection law (DPDP / LGPD / NDPA);
  any feature touching templates must respect encryption-at-rest +
  retention/deletion. Don't add a feature that stores raw selfies indefinitely.
- The Venezuela + USDC/OFAC question is **legal**, handled outside this code.
  Don't add sanctions logic without an explicit instruction.
- The face matcher and liveness landmark extraction are the only places real ML
  belongs. Don't fake them as "done" — keep the interface honest.
