# Single-VPS production stack

Run the whole system on one server with Docker Compose, behind Caddy with
**automatic HTTPS**. Good for a single-box production deployment or a pilot. For
multi-node / managed-service deployments see [`../README.md`](../README.md) and
the root README's *Deploying to production* section.

> This stack is **not** production-hardened on every axis — it uses the on-disk
> Ed25519 signer (`KYC_SIGNER=local`), not a KMS. That is the main compromise vs.
> the root README's *Before real money* checklist; everything else (Postgres +
> pgvector, encrypted media + retention, real OCR + face match, arq worker, TLS,
> auth, rate limiting) is the production path. Don't handle real funds until the
> signer is moved to a KMS/HSM.

## What you get

| Container | Role |
|---|---|
| `caddy` | TLS termination (Let's Encrypt) + same-origin routing (`/v1`, JWKS → api; everything else → web) |
| `web` | Next.js verification wizard |
| `api` | FastAPI (`alembic upgrade head` on start, then uvicorn) |
| `worker` | arq worker — runs the biometric decision **and** the hourly retention purge |
| `db` | Postgres 16 **+ pgvector** (HNSW 1:N dedup) |
| `redis` | arq queue (password-protected) |

Real seams are on: `pgvector` dedup, `insightface` 1:1 match, `ocr` MRZ reader,
encrypted-at-rest local media with a 24h retention purge. Raw media lives on a
volume **shared** by api + worker (the worker must read the passport image the
api stored) — this is why local storage works here; a multi-node setup needs S3.

## Prerequisites

- A VPS with **≥ 2 vCPU, ≥ 4 GB RAM, ≥ 40 GB disk** (the ArcFace model + ONNX
  runtime are loaded by both api and worker; give it headroom).
- **Docker Engine + Compose plugin** installed.
- A **domain name** with a DNS `A` record pointing at the VPS, and ports **80 +
  443** open (Caddy needs both for ACME + serving).

## Deploy

```bash
# on the VPS
git clone <your-repo> && cd <repo>/deploy/single-vps
cp .env.example .env
# fill in .env — generate secrets with: openssl rand -base64 32
nano .env

docker compose up -d --build
```

First build is large (ML deps); the **first verification** downloads the ArcFace
model (~300 MB) into the `insightface` volume, once. Watch progress:

```bash
docker compose logs -f api worker
```

When it's up:

- Wizard: `https://<your-domain>/`
- API: `https://<your-domain>/v1/...`, JWKS at `/.well-known/jwks.json`
- Health: `https://<your-domain>/healthz`

`/metrics` is intentionally **not** exposed publicly — scrape it on the internal
Docker network if you add Prometheus.

## Operate

- **Logs:** `docker compose logs -f`
- **Update:** `git pull && docker compose up -d --build`
- **Backups (do this):** the `pgdata` volume (identities/ledger/audit) and the
  `appdata` volume (which holds `signing_key.pem` — losing it means re-issuing
  every credential). Back both up off-box; treat the signing key as a secret.
- **Retention:** the worker runs the purge hourly; raw media is gone within
  `KYC_MEDIA_RETENTION_SECONDS` (24h) + ~1h. Only encrypted templates persist.

## Hardening notes

- **Signer:** move off the on-disk key by implementing `KmsSigner`
  (`app/providers/signer.py`) and setting `KYC_SIGNER=kms` — point it at an
  external KMS or a self-hosted HashiCorp Vault (Transit). This is the one real
  gap on a single box.
- **Rate limiting:** the in-process limiter is fine here (one api instance). It
  does **not** hold if you scale `api` to multiple replicas — move to Redis then.
- **Object storage:** to scale beyond one box, switch `KYC_STORAGE_BACKEND=s3`
  (works with any S3-compatible store, e.g. SurferCloud US3, via
  `KYC_S3_ENDPOINT_URL`) so api + worker no longer need a shared local volume.
- **Firewall:** expose only 80/443 (and SSH); Postgres/Redis are internal to the
  Compose network and are not published to the host.
