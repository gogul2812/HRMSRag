# Module 6 — Infrastructure & DevOps

> Depends on: Module 3 (service inventory). Defines how everything in this
> repo actually runs.

## 1. Local development

`infra/docker-compose/docker-compose.dev.yml` brings up every dependency a
developer needs on a laptop:

```
services:
  postgres, redis, qdrant, (each backend microservice), gateway
```

One command (`docker compose up`) gets a new engineer to a fully working
local stack — this matters more than it sounds like once there are 7+
microservices; nobody should need to manually start each one.

## 2. Environments

| Environment | Purpose | Orchestration |
|---|---|---|
| `local` | Individual developer machines | Docker Compose |
| `staging` | Shared pre-production, used for client demos | Docker Compose on a single VM, or a small Kubernetes namespace |
| `production` | Live, multi-tenant | Kubernetes |

Moving from `staging` (single VM, free-tier-friendly) to `production`
(Kubernetes) does not change any service's code — only its deployment
manifest, per the free→paid migration principle established in Module 1.

## 3. Kubernetes (production target)

- One Deployment + Service per microservice, each independently scalable
  (`ingestion-service` and `retrieval-service` will need different replica
  counts under real load — this is the whole point of splitting them).
- `ingestion-service`'s Celery workers scale as a separate Deployment from
  its API pod, since document-processing load and upload-request load are
  different things.
- Qdrant, Postgres, Redis run as StatefulSets (or as managed cloud services
  once budget allows — see the free→paid table below).
- An Ingress (or the API gateway itself) is the only externally exposed
  entry point; every internal service communicates over the cluster
  network only.

## 4. CI/CD

- One GitHub Actions pipeline per service under `infra/ci-cd/`: lint → test
  → build image → push → deploy to staging → (manual approval) → deploy to
  production.
- Independent pipelines mean a fix to `chat-service` ships without
  rebuilding or redeploying `ingestion-service`.
- `shared-libs/` changes trigger a rebuild of every service that depends on
  it (a simple dependency-graph check in the pipeline, or just rebuild all
  on any `shared-libs` change until the team is large enough to need
  finer-grained invalidation).

## 5. Observability

- **Logging**: structured JSON logs from every service, shipped to a
  central store (Loki or the ELK stack); every log line includes
  `tenant_id` and `request_id` so a single request can be traced across
  services.
- **Metrics**: Prometheus scrapes each service's `/metrics`; Grafana
  dashboards per service plus one cross-service "RAG pipeline health"
  dashboard (ingestion queue depth, retrieval latency, LLM router fallback
  rate — a rising fallback rate is an early warning that a primary
  provider is degrading).
- **Tracing**: OpenTelemetry spans across the gateway → orchestrator →
  retrieval → LLM router call chain, so a slow chat response can be
  attributed to a specific stage.

## 6. POC (free-tier) → Production (paid) migration path

| Component | POC | Production |
|---|---|---|
| Qdrant | Self-hosted on a free VM | Qdrant Cloud, or a larger self-hosted cluster |
| Postgres | Free-tier managed (Supabase) | Dedicated managed Postgres, or RLS-backed multi-tenant cluster |
| Hosting | Render/Railway/Vercel free tiers | Kubernetes cluster (own cloud account or client's) |
| LLM | Free tiers (Groq/Gemini/OpenRouter) + local Ollama | Same providers on paid tiers, or add enterprise-grade models via the same router config |

No service is rewritten at this transition — only its deployment target and
connection strings change, per the reusability principle from Module 1.
