# Project Context

**Project name:** Enterprise RAG HRMS Platform

**Architecture:** Microservices, multi-tenant, multi-domain (Healthcare,
Retail/Clothing, HR/HRMS, and future domains — served by the same
deployment, isolated by tenant)

**Architecture status:** Frozen. Do not redesign.

## Confirmed stack

| Layer | Choice |
|---|---|
| Frontend | Next.js + TypeScript + Tailwind + shadcn/ui (Admin Portal + User Portal, separate apps) |
| Backend | FastAPI, one process per microservice |
| API Gateway | Kong / Traefik / lightweight FastAPI gateway |
| Database | Postgres (row-level security for tenant isolation) |
| Vector database | Qdrant, self-hosted, tagged by tenant/doc type |
| Queue | Redis + Celery |
| Document parsing | Docling + Tesseract OCR |
| Chunking | LlamaIndex splitter (table/header-aware) |
| Embedding | BGE-large-en-v1.5, local |
| Reranking | bge-reranker-v2-m3, local |
| LLM orchestration | litellm router: Groq → Gemini → OpenRouter → local Ollama |
| Guardrails | Guardrails AI / NeMo Guardrails, Microsoft Presidio |
| Auth | JWT (Supabase Auth or Clerk) |
| Containers | Docker → Kubernetes (production) |
| CI/CD | GitHub Actions, one pipeline per service |
| Observability | OpenTelemetry, Prometheus + Grafana, centralized logging |
| Evaluation | RAGAS |

**Multi-tenant:** Yes — every table, every vector payload, every cache key
carries `tenant_id`. Non-negotiable from the first migration.

**Coding style:** Production-grade. Clean Architecture. SOLID. Every
service ships with tests, Docker, README, logging, and OpenAPI docs.

**Goal:** Enterprise-ready software, not a prototype — built one stage at a
time per `09-implementation-roadmap-module.md`.

## Source of truth

The numbered files `00-README.md` through `09-implementation-roadmap-module.md`
are the complete specification. `AI_DEVELOPMENT_RULES.md` governs how you
work. This file is context that never changes across sessions.
