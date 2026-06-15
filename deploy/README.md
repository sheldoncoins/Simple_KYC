# Deploy

Ops artifacts for the KYC server (Phase 6).

## Local stack (Docker Compose)

```bash
docker compose up --build
```

Brings up **postgres**, **redis**, the **api** (runs migrations, then uvicorn;
dispatches biometrics to the worker via arq), the **worker**, the **web**
frontend (http://localhost:3000), and **prometheus** (http://localhost:9090,
scraping the API and loading the alert rules).

## Prometheus

- `prometheus/prometheus.yml` — scrape config (`/metrics` on the API).
- `prometheus/alerts.yml` — alert rules, including **rejection-rate spikes** and
  **dedup anomalies** (the account-farm signal). Thresholds are starting points;
  tune against real traffic. Point Alertmanager at these for paging, and add
  Grafana with Prometheus as a datasource for dashboards.

## Kubernetes (`k8s/`)

Apply in order (namespace + config first):

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/config.yaml        # EDIT secrets first (or use a secret manager)
kubectl apply -f k8s/data.yaml          # or use managed Postgres (pgvector) + Redis
kubectl apply -f k8s/api.yaml           # includes the migration Job
kubectl apply -f k8s/worker.yaml
kubectl apply -f k8s/web.yaml
kubectl apply -f k8s/cronjob.yaml       # hourly retention purge
kubectl apply -f k8s/ingress.yaml
```

### Retention / data deletion

Raw media (passport images, selfies) is encrypted and given a TTL
(`KYC_MEDIA_RETENTION_SECONDS`, default **24h**). It is actually deleted by a
**purge sweep that runs hourly** — two ways, so it always runs:

- the **arq worker** runs `purge_media` on a cron (top of every hour), and
- `k8s/cronjob.yaml` runs `python -m app.jobs.purge_media` hourly as a standalone
  CronJob (for deployments without the worker).

So raw uploads are removed within the retention window + ~1h. Only derived
templates / hashes / ledger / audit persist.

Build + push the images referenced by the manifests first:

```bash
docker build -t <registry>/kyc-server:<tag> .
docker build -t <registry>/kyc-web:<tag> \
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://verify.example.com ./web
```

Notes: the api Deployment wires `/healthz` (liveness) and `/readyz` (readiness)
probes and Prometheus scrape annotations; `/metrics` is scraped in-cluster only
(not exposed through the Ingress). Replace every value in the `Secret` before
applying.
