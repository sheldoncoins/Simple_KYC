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
kubectl apply -f k8s/ingress.yaml
```

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
