# BUILD_PLAN.md

Phased roadmap to take the reference backend to a production service with a UI.
Each phase is independently shippable and ends green (`pytest` + a manual smoke
test). Work top to bottom; don't start a phase until the prior one is merged.

Recommended stack (opinionated default — swap if you have a reason):
- **API**: keep FastAPI. Add Postgres, Redis, a background worker.
- **Frontend**: Next.js (App Router) + TypeScript + Tailwind + shadcn/ui.
- **In-browser liveness**: MediaPipe Tasks `FaceLandmarker` (WASM) — landmark
  extraction runs client-side, only the feature timeline is sent to the server.
- **Data**: TanStack Query for server state, Zod for schema parity with the API.
- **Infra**: Docker + docker-compose for dev; container image for prod.

---

## Phase 0 — Project hygiene
- Add `pyproject.toml` (ruff + mypy + pytest config), pre-commit hooks.
- Pin dependencies, add `.env.example`, structured logging (`structlog`).
- CI: lint + type-check + test on every push.

## Phase 1 — Backend hardening
- **Postgres**: switch `KYC_DATABASE_URL`; add Alembic migrations (models are
  already 2.0-style and port directly).
- **Key management**: replace the file-based Ed25519 key in `crypto.py` with a
  KMS/HSM-backed signer. Add a **JWKS endpoint** (`/.well-known/jwks.json`) so
  the P2P layer fetches the public key and key rotation is non-breaking.
- **AuthN/Z**: authenticate the P2P client to the KYC server (API keys or mTLS
  or signed requests). Lock down the admin/review endpoints behind staff auth.
- **Rate limiting** on `/v1/onboard` and biometric submission (slowapi or at the
  edge). Add idempotency keys to onboarding.
- **Credential revocation**: revocation list / short TTL + refresh.

## Phase 2 — Real media handling
- File/video upload for passport image + liveness clip → S3-compatible object
  storage, **encrypted at rest**, with a strict retention TTL and a deletion job
  (DPDP/LGPD/NDPA). Store templates, not raw selfies, long-term.
- Server-side passport MRZ read from the uploaded image (OCR) feeding the
  existing `validate_td3`. Keep MRZ validation deterministic.

## Phase 3 — Face model + dedup at scale
- Implement `FaceMatcher` in `providers/face.py` against self-hosted
  InsightFace/ArcFace (or a cloud face API). Keep the deterministic mock for
  tests behind a flag.
- Move 1:N dedup off the linear scan onto **pgvector or FAISS**. Decision logic
  and thresholds in `services/dedup.py` stay identical — only the search backend
  changes. Benchmark recall/precision and tune `DEDUP_*_THRESHOLD`.
- Run dedup + matching in a **background worker** (arq/Celery + Redis); the
  biometric endpoint enqueues and the client polls session status.

## Phase 4 — Verification UI (the applicant wizard)
A guided, accessible, mobile-first flow that mirrors the pipeline:
1. **Start** — country select (7 markets), wallet binding.
2. **Passport** — camera capture or upload; show MRZ-read result inline.
3. **Liveness** — live camera; fetch a challenge from `/v1/liveness/challenge`,
   run MediaPipe `FaceLandmarker` in-browser, guide the user through the
   randomized actions with real-time feedback, submit the feature timeline.
4. **Result** — approved / in review / rejected, with a clear reason and a
   retry path where appropriate.
Requirements: camera permission handling, graceful failure, i18n
(EN/ES/PT/HI scaffold), WCAG AA, no PII in client logs.

## Phase 5 — Admin / review console
- Authenticated staff app: the manual-review queue (`/v1/review`), side-by-side
  signals, approve/reject with reason, and a read-only **audit log** viewer.
- Metrics dashboard: approval/rejection/review rates, dedup hit rate, liveness
  pass rate, per-country breakdown.

## Phase 6 — Observability & ops
- Metrics (Prometheus), tracing, dashboards, alerting on rejection-rate spikes
  and dedup anomalies (account-farm signal).
- Containerize: `Dockerfile` + `docker-compose.yml` (api, postgres, redis,
  worker, frontend). Health/readiness probes. Then k8s manifests if needed.

## Phase 7 — Pre-launch gates (non-code)
- Legal review of money-transmission/VASP obligations per market; explicit
  decision on the Venezuela/OFAC exposure.
- Data-protection: retention schedule, DSAR/deletion flow, DPIA.
- Security review / pen test of the upload and credential paths.

---

## Definition of done per phase
Green `pytest`, a new test for each added decision path, updated `CLAUDE.md` if
a convention changed, and a one-paragraph note in the PR on what is now real vs.
still stubbed. Keep the "what's real vs. plug in" table in `README.md` honest.
