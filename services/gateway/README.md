# Gateway Service

**Technology:** FastAPI (Python 3.11+), or Kong / Traefik

## Purpose

The API Gateway is the single entry point for all client traffic. It:

- Routes requests from the Admin Portal and User Portal to the correct
  downstream microservice.
- Validates JWTs and injects tenant context headers (`X-Tenant-ID`,
  `X-User-ID`, `X-Role`) before forwarding.
- Enforces global rate limits per tenant.
- Aggregates health checks from all downstream services at `GET /health`.
- Provides a unified base URL so frontends never need service-specific addresses.

Routes to services that do not exist yet return `501 Not Implemented` during
early stages.

## Implementation module

Module 3 — `03-backend-microservices-module.md` → "gateway"

## Routes

| Prefix | Downstream service |
|---|---|
| `/api/v1/auth/**` | `auth-service` |
| `/api/v1/tenants/**` | `auth-service` |
| `/api/v1/config/**` | `admin-config-service` |
| `/api/v1/ingest/**` | `ingestion-service` |
| `/api/v1/retrieve/**` | `retrieval-service` |
| `/api/v1/orchestrate/**` | `llm-orchestrator-service` |
| `/api/v1/chat/**` | `chat-service` |
| `/api/v1/notify/**` | stub (501) until notification-service |

## Running locally (Stage 1+)

```bash
cd services/gateway
cp ../../.env.example .env    # or symlink
python -m uvicorn app.main:app --reload --port 8000
```

## Environment variables

See root `.env.example` for `GATEWAY_PORT` and downstream service URLs.

Stage 10 also uses:
- `GATEWAY_RATE_LIMIT_PER_MINUTE` (default 120)
- `OTEL_EXPORTER_OTLP_ENDPOINT` / `OTEL_CONSOLE_EXPORT` for traces
- Prometheus scrape of gateway `/metrics`
