# infra/docker-compose

**Technology:** Docker Compose v2

## Purpose

This directory contains Docker Compose files for different local dev scenarios.
The root-level `docker-compose.dev.yml` is the primary file for Stage 0 (infrastructure
only). Additional compose files here will be added as services are built.

### Files (planned)

| File | Purpose |
|---|---|
| `../../docker-compose.dev.yml` | Root — infrastructure only (Postgres, Redis, Qdrant). This is the Stage 0 file. |
| `services.yml` | All application services (added per stage as they are implemented) |
| `ai.yml` | Ollama + model pull, Presidio containers (GPU-optional) |
| `observability.yml` | Prometheus, Grafana, Loki / ELK, Jaeger/Tempo |

### Usage

```bash
# Stage 0 (infrastructure only — from repo root):
docker compose -f docker-compose.dev.yml up -d

# Stage 1+ (infrastructure + application services):
docker compose -f docker-compose.dev.yml -f infra/docker-compose/services.yml up -d
```

## Implementation module

Module 6 — `06-infra-and-devops-module.md`
