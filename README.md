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

As **defence in depth**, the same *document* reused across identities is flagged
to manual review (`passport_reused`) — via a **salted one-way token** of the
passport (country + number), so reuse is detectable without ever storing the raw
number. It complements the biometric gate (which catches one human regardless of
how many passports they hold); it does not replace it.

## Pipeline

```
onboard → passport MRZ → selfie + liveness → 1:1 face match
        → 1:N biometric dedup → risk decision → identity + signed credential
```

Risk decisions: hard gates (MRZ, liveness, 1:1 match, dedup-reject) fire first;
a weighted score then routes survivors to approve / manual review. High-risk
countries and near-duplicates (e.g. twins) go to review.

## Run it

### Docker (full stack)

```bash
docker compose up --build          # postgres, redis, api, worker, web, prometheus
                                   # API http://localhost:8000/docs · wizard :3000
                                   # Prometheus :9090 · API runs migrations on start
```

Kubernetes manifests, Prometheus scrape/alert rules, and image build steps are in
[`deploy/`](deploy/README.md).

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

🔑 = P2P client API key (`X-API-Key`, `KYC_P2P_API_KEYS`); 🛡️ = staff key
(`X-Admin-Key`, `KYC_ADMIN_API_KEYS`).

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
| GET  | `/healthz` · `/readyz` | liveness / readiness probes (readiness checks the DB) |
| GET  | `/metrics` | Prometheus metrics (HTTP + domain KPIs) — restrict to in-cluster scraping |
| POST | `/v1/credentials/verify` | 🔑 P2P layer verifies a credential |
| POST | `/v1/credentials/revoke` | 🔑 revoke a credential (by `jti` or `identity_hash`) |
| POST | `/v1/limits/debit` | 🔑 consume limit (idempotent) |
| GET  | `/v1/limits/{identity_hash}` | 🔑 limit balance |
| GET  | `/v1/review` | 🛡️ pending manual-review queue (with signals) |
| POST | `/v1/review/{item_id}` | 🛡️ resolve a review item |
| GET  | `/v1/audit` | 🛡️ read-only audit log (most recent first) |
| GET  | `/v1/metrics/summary` | 🛡️ approval/review/reject + dedup/liveness rates, per-country |

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
| Staff auth + review/audit/metrics API | **Real** — `X-Admin-Key`; admin console UI is Phase 5b |
| Identity-bound limit ledger (idempotent) | **Real** |
| Risk engine, review queue, audit log | **Real** |
| Media storage encrypted at rest + retention/purge | **Real** — local AES-256-GCM; raw media TTL (24h) swept **hourly** by the arq worker cron + a k8s CronJob; only templates persist |
| KMS/HSM-backed signing | Plug in — implement `KmsSigner` in `app/providers/signer.py` (`KYC_SIGNER=kms`); local Ed25519 is the dev fallback |
| 1:N dedup search backend | **Real** — pluggable; linear scan (default) or **pgvector** ANN (`KYC_DEDUP_BACKEND=pgvector`), decision/thresholds identical |
| S3-compatible object storage | Plug in — `S3Storage` (`KYC_STORAGE_BACKEND=s3`, needs `boto3`); local encrypted store is the dev fallback |
| Passport MRZ OCR (read from image) | Plug in — `PassportEyeMrzReader` (`KYC_MRZ_READER=ocr`); the text reader drives dev/tests. Validation stays deterministic |
| Liveness landmark extraction | Plug in MediaPipe / dlib (self-hosted) |
| Face match (1:1 selfie↔passport) + embedding | **Real** — `InsightFaceMatcher` (ArcFace) compares the captured selfie to the passport photo (`KYC_FACE_MATCHER=insightface`, install `requirements-face.txt`). The deterministic mock is the default and drives dev/tests |
| Dedup + matching background worker | **Real** — pluggable; inline (default) or **arq + Redis** worker (`KYC_TASK_QUEUE=arq`), client polls session status |

## Deploying to production

> **Read this first.** This repo is a *tested reference backend*, not a
> production-ready service. The topology below is real and the manifests work,
> but you **must** clear the blockers in [Before real money](#before-real-money)
> — above all a real KMS signer — before handling live funds or real PII.
> Nothing here is legal or compliance advice.

### Recommended platform

Run it on managed Kubernetes (or a managed container service) in a region with
**Indian data residency** — biometric + identity data under the DPDP Act 2023,
plus your VASP/AML posture, makes Mumbai the sensible home. The reference mapping
is **AWS `ap-south-1` (Mumbai)**; GCP (`asia-south1`) maps one-to-one.

| Need | Service (AWS `ap-south-1`) | Wires to |
|---|---|---|
| Containers (api, worker, web) | **EKS** (or ECS Fargate) | `deploy/k8s/*` |
| Postgres + **pgvector** | **RDS for PostgreSQL 16** (`CREATE EXTENSION vector`) | `KYC_DATABASE_URL`, `KYC_DEDUP_BACKEND=pgvector` |
| Redis (queue) | **ElastiCache for Redis** | `KYC_REDIS_URL`, `KYC_TASK_QUEUE=arq` |
| Encrypted media at rest | **S3 + SSE-KMS** | `KYC_STORAGE_BACKEND=s3`, `KYC_S3_BUCKET` |
| Credential signing keys | **AWS KMS** (asymmetric) | `KYC_SIGNER=kms` ‹implement `KmsSigner`› |
| Secrets (salt, API keys, DB) | **Secrets Manager / SSM** | k8s `Secret` / external-secrets |
| TLS + ingress | **ALB + ACM** (or ingress-nginx + cert-manager) | `deploy/k8s/ingress.yaml` |
| DNS | **Route 53** | — |
| Metrics + alerts | Managed **Prometheus + Grafana** | `/metrics`, `deploy/prometheus/*` |

The API is **stateless** — scale it horizontally behind the load balancer. The
CPU-heavy work is the InsightFace embedding on the **worker**; scale worker
replicas independently (GPU optional for throughput). pgvector's HNSW index
carries 1:N dedup to millions of identities on a single primary.

### On SurferCloud (UK8S + US3 + UMem)

SurferCloud has the full stack with a **Mumbai** region. Map the components to
its products, then follow the [deploy steps](#deploy-steps) below with the noted
deltas:

| Need | SurferCloud product | Env / file |
|---|---|---|
| Containers (api, worker, web) | **UK8S** (managed Kubernetes) | `deploy/k8s/*` apply as-is |
| Object storage (encrypted media) | **US3** (S3-compatible) | `KYC_STORAGE_BACKEND=s3`, `KYC_S3_BUCKET`, `KYC_S3_ENDPOINT_URL` |
| Redis (queue) | **UMem Redis** | `KYC_REDIS_URL`, `KYC_TASK_QUEUE=arq` |
| Postgres + pgvector | **UDB PostgreSQL** if `vector` is whitelisted, else self-host | `KYC_DATABASE_URL`, `KYC_DEDUP_BACKEND=pgvector` |
| Load balancer / ingress | **ULB** + UK8S ingress | `deploy/k8s/ingress.yaml` |
| Image registry | **UHub** (or Docker Hub) | — |
| Region | **Mumbai** | data residency |

**US3 (object storage).** US3 speaks the S3 API, so the built-in `S3Storage`
backend works against it unchanged — just point boto3 at the US3 endpoint:

```bash
KYC_STORAGE_BACKEND=s3
KYC_S3_BUCKET=<your-us3-bucket>
KYC_S3_ENDPOINT_URL=<US3 Mumbai endpoint>     # e.g. https://<region>.ufileos.com
AWS_ACCESS_KEY_ID=<US3 access key>            # US3 S3-compatible credentials
AWS_SECRET_ACCESS_KEY=<US3 secret key>
```

**pgvector.** The dedup gate needs the `vector` extension. On a UDB PostgreSQL
instance, check availability first:

```sql
SELECT * FROM pg_available_extensions WHERE name = 'vector';
```

If present → `CREATE EXTENSION vector;` and set `KYC_DEDUP_BACKEND=pgvector`. If
it isn't whitelisted, run **self-managed Postgres + pgvector** instead
(CloudNativePG on UK8S with a `pgvector/pgvector:pg16` image, or a UHost VM with
`CREATE EXTENSION vector`); only `KYC_DATABASE_URL` changes — the app is identical.

**Signing keys.** SurferCloud has no managed KMS, so `KYC_SIGNER=kms` needs an
external KMS or a self-hosted HashiCorp Vault (Transit engine) — see
[Before real money](#before-real-money). Don't ship the on-disk dev signer.

**Pilot shortcut.** To get live fast, skip UK8S: one **UHost** VM running
`docker compose up` + **UMem Redis** + **UDB Postgres** + **US3** works. Not for
real funds (in-process rate limiter + dev signer).

### Deploy steps

1. **Provision** RDS (PG16 + `vector` extension), ElastiCache, an S3 bucket with
   SSE-KMS, and the EKS cluster.
2. **Build & push** both images to your registry (ECR):
   ```bash
   docker build -t <ecr>/kyc-server:<tag> .
   docker build -t <ecr>/kyc-web:<tag> \
     --build-arg NEXT_PUBLIC_API_BASE_URL=https://verify.example.com ./web
   ```
3. **Secrets**: put real values in Secrets Manager and surface them as the
   `kyc-secrets` Secret (e.g. via external-secrets) — never commit them.
4. **Configure** the production env (table below) in `deploy/k8s/config.yaml`.
5. **Migrate**: the `kyc-migrate` Job runs `alembic upgrade head` on deploy —
   Alembic owns the schema in production.
6. **Apply** the manifests in order — see [`deploy/README.md`](deploy/README.md)
   (namespace → config → data → api → worker → web → cronjob → ingress).
7. **TLS + DNS + CORS**: point Route 53 at the ALB, terminate TLS with ACM, and
   set `KYC_CORS_ORIGINS` to the wizard's HTTPS origin only.
8. **Observe**: scrape `/metrics` in-cluster, load `deploy/prometheus/alerts.yml`
   (rejection-rate + dedup-anomaly alerts), wire Alertmanager + Grafana.
9. **Verify retention**: confirm the purge runs (worker cron + `k8s/cronjob.yaml`)
   and raw media disappears within `KYC_MEDIA_RETENTION_SECONDS` (+ ~1h).

### Production environment

| Variable | Production value | Why |
|---|---|---|
| `KYC_DATABASE_URL` | `postgresql+psycopg://…@<rds>/kyc` | managed Postgres |
| `KYC_DEDUP_BACKEND` | `pgvector` | HNSW 1:N dedup at scale |
| `KYC_REDIS_URL` / `KYC_TASK_QUEUE` | `redis://<elasticache>` / `arq` | biometrics off the request path |
| `KYC_SIGNER` | `kms` | keys never touch disk ‹needs `KmsSigner`› |
| `KYC_STORAGE_BACKEND` / `KYC_S3_BUCKET` | `s3` / `<bucket>` | encrypted media at rest |
| `KYC_FACE_MATCHER` | `insightface` | real 1:1 match (`requirements-face.txt`) |
| `KYC_MRZ_READER` | `ocr` | read MRZ from image (`requirements-ocr.txt` + tesseract) |
| `KYC_PII_SALT` | secret, **long-lived** | rotating it invalidates every hash |
| `KYC_P2P_API_KEYS` / `KYC_ADMIN_API_KEYS` | strong random, rotated | P2P + staff auth |
| `KYC_CORS_ORIGINS` | `https://verify.example.com` | lock to the wizard origin |
| `KYC_MEDIA_RETENTION_SECONDS` | `86400` (or lower) | raw-media TTL |
| `KYC_LOG_FORMAT` | `json` | structured logs (never PII) |

### Before real money

Standing up the infrastructure is **not** the same as being safe to launch.
What was hardened already: Postgres + Alembic, a swappable `Signer` with JWKS +
key rotation, P2P/staff auth, rate limiting, credential revocation, encrypted-at-
rest media with a retention purge, and pgvector dedup. Still **required** before
live funds or real PII:

- [ ] **Implement `KmsSigner`** (`app/providers/signer.py`) — the dev signer
      keeps the Ed25519 key on disk; production keys must live in a KMS/HSM.
- [ ] **Distributed rate limiter** — the in-process limiter doesn't hold across
      API replicas; move it to Redis or the edge/WAF.
- [ ] **Liveness anti-spoofing** — add passive + injection/virtual-camera
      defences; the self-built active check doesn't stop deepfakes.
- [ ] **Robust MRZ OCR (or NFC chip read)** — the OCR reader is a starting seam
      and misreads real photos; check-digit validation stays deterministic.
- [ ] **DSAR / right-to-erasure + DPIA** — biometric data under DPDP 2023 / LGPD
      / NDPA needs a per-user deletion flow and an impact assessment.
- [ ] **AML / regulatory** — FIU-IND registration, PMLA + suspicious-transaction
      reporting, and sanctions screening (intentionally absent) for an India VDA/VASP.
- [ ] **Transaction-layer fraud monitoring** — this service verifies a *unique
      live human*, not honest funds; pair it with fiat-rail + coordination
      analytics (the mule-farm gap).
- [ ] **Security review + pen test** of the biometric template store and signing path.

This code does not constitute legal or compliance advice.
