# Admin Config Service

**Technology:** FastAPI (Python 3.11+), PostgreSQL

## Purpose

The Admin Config Service is the API that tenant admins use to configure the AI
agent's behaviour:

- **Prompt configs:** versioned system-prompt / rules documents per tenant.
  Each version is immutable once created; exactly one version can be
  `is_active = true` at a time.
- **Guardrail policies:** versioned per-tenant declarative guardrail rules
  (JSON policy documents), same activate-one-at-a-time pattern.

All records carry `tenant_id` and are invisible to queries scoped to a
different tenant (enforced at the SQL query level using JWT claims).
Every endpoint requires `role = admin` (or `super_admin`).

## Implementation module

Module 3 — `03-backend-microservices-module.md` → "admin-config-service"
Module 5 — `05-data-and-multitenancy-module.md` → `prompt_configs` /
`guardrail_policies`
Module 9 — Stage 2

## API

Base path: `/api/v1/config` (OpenAPI at `/docs`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/config/prompt` | Active prompt config for caller's tenant |
| `POST` | `/config/prompt` | Create a new prompt config version |
| `GET` | `/config/prompt/versions` | List all versions |
| `GET` | `/config/prompt/{id}` | Get one version by id (tenant-scoped) |
| `PUT` | `/config/prompt/{id}/activate` | Activate a version (deactivates others) |
| `GET` | `/config/guardrails` | Active guardrail policy |
| `POST` | `/config/guardrails` | Create a new guardrail policy version |
| `GET` | `/config/guardrails/versions` | List all versions |
| `GET` | `/config/guardrails/{id}` | Get one version by id (tenant-scoped) |
| `PUT` | `/config/guardrails/{id}/activate` | Activate a version |

## Running locally

```bash
# From rag-platform/
cp .env.example .env   # if needed
docker compose -f docker-compose.dev.yml up -d
cd data/postgres && alembic upgrade head && cd ../..

cd services/admin-config-service
# Install shared libs + service (from monorepo root recommended)
pip install -e ../../shared-libs/schemas \
            -e ../../shared-libs/auth-middleware \
            -e ../../shared-libs/observability \
            -e ".[test]"
uvicorn app.main:app --reload --port 8002
```

## Environment variables

`DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`

## Tests

```bash
cd services/admin-config-service
pytest tests/ -v
```

## Docker

```bash
# From rag-platform/
docker build -f services/admin-config-service/Dockerfile -t rag-admin-config .
# or
docker build -f infra/docker/Dockerfile.admin-config-service -t rag-admin-config .
```
