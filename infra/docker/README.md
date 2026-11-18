# infra/docker

**Technology:** Docker

## Purpose

This directory contains one `Dockerfile` per microservice — the production
container image definition for each service.

### Naming convention

```
docker/
├── Dockerfile.gateway
├── Dockerfile.auth-service
├── Dockerfile.admin-config-service
├── Dockerfile.ingestion-service
├── Dockerfile.retrieval-service
├── Dockerfile.llm-orchestrator-service
├── Dockerfile.chat-service
└── Dockerfile.notification-service
```

Each `Dockerfile`:
- Uses a multi-stage build (builder + slim runtime image) to minimise image
  size.
- Pins a specific Python base image version (`python:3.11-slim-bookworm`).
- Runs the application as a non-root user.
- Uses `COPY --chown` to set file ownership.
- Exposes the service port via `EXPOSE`.
- Accepts all runtime configuration via environment variables — no hardcoded
  secrets or hostnames.

Dockerfiles are created in Stage 1+ (one per service as that service is built).

## Implementation module

Module 6 — `06-infra-and-devops-module.md`
