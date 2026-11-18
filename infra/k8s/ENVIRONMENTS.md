# Environments

| Environment | Purpose | Orchestration | Apply |
|---|---|---|---|
| **local** | Developer laptops | `docker-compose.dev.yml` (infra) + uvicorn | `docker compose -f docker-compose.dev.yml up -d` |
| **staging** | Shared demos / pre-prod | Compose on one VM **or** K8s overlay | See below |
| **production** | Live multi-tenant | Kubernetes | `kubectl apply -k infra/k8s/overlays/production` |

## Staging options

### A) Docker Compose (single VM)

```bash
docker compose -f docker-compose.dev.yml -f infra/docker-compose/staging.yml up -d --build
```

Gateway is the only published app port (`8000`). Point DNS / a reverse proxy at it.

### B) Kubernetes namespace

```bash
# Create real secrets first (never commit secrets.example values)
kubectl -n rag-platform create secret generic rag-platform-secrets --from-env-file=.env.prod
kubectl apply -k infra/k8s/overlays/staging
```

Ingress host default: `staging-api.rag-platform.example`.

Staging ConfigMap uses fake embeddings / LLM for cheap demos; override via ConfigMap edit for live provider demos.

## Production

```bash
kubectl apply -k infra/k8s/overlays/production
```

- In-cluster **Postgres is removed** — set `DATABASE_URL` to managed Postgres (Supabase/RDS/Cloud SQL).
- Redis / Qdrant remain as StatefulSets until you cut over to managed equivalents.
- Only **gateway** is exposed via Ingress (`api.rag-platform.example` + TLS).
- Production deploy requires GitHub Environment **`production`** with required reviewers.

## GitHub Environments & secrets

Create environments `staging` and `production` in the repo settings.

| Secret | Where | Purpose |
|---|---|---|
| `KUBE_CONFIG_STAGING` | staging env / repo | base64 kubeconfig for staging cluster |
| `KUBE_CONFIG_PRODUCTION` | production env | base64 kubeconfig for production |
| `GITHUB_TOKEN` | automatic | GHCR push |

Replace `ghcr.io/ORG/rag-platform/...` image names in overlays with your real GHCR path (CI `kustomize edit set image` does this per deploy).

## Local verification (Windows)

On machines that already run Windows PostgreSQL / Redis on `5432` / `6379`, use
`docker-compose.override.yml` to publish Docker infra on alternate host ports:

| Service | Host port |
|---|---|
| Postgres | `15432` |
| Redis | `16379` |
| Qdrant | `6333` (unchanged) |

Then:

```bash
docker compose -f docker-compose.dev.yml -f docker-compose.override.yml up -d
# migrate via Docker network or host:15432
python scripts/verify_local_stack.py
```

The verify script boots gateway + microservices (fake embeddings / fake chat
orchestrator), creates a tenant, logs in via gateway, uploads a sample doc,
waits for `indexed`, and streams a chat reply.

## Image naming

`ghcr.io/<owner>/<repo>/<service>:<git-sha>`
