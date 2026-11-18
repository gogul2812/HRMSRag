# Module 3 — Backend Microservices

> Depends on: Module 1 (structure), Module 5 (data model). Feeds into:
> Module 4 (the AI logic these services call as a library).

## 1. Why microservices here, specifically

Ingestion (parsing 100+ documents) and live chat (sub-second response
expectations) have completely different load profiles and scaling needs. A
monolith would force them to scale together. Splitting them means a large
document upload burst for the Healthcare tenant never slows down chat
latency for the Retail tenant.

## 2. Service inventory

### `gateway`
- **Responsibility**: single public entry point. Routes `/auth/*` →
  `auth-service`, `/documents/*` → `ingestion-service`, `/chat/*` →
  `chat-service`, `/config/*` → `admin-config-service`. Validates the JWT
  once at the edge and forwards tenant/role context as headers so
  downstream services don't re-implement auth parsing.
- **Tech**: Kong or Traefik (config-driven), or a thin FastAPI app if the
  team prefers to keep everything in Python.

### `auth-service`
- **Responsibility**: login, JWT issuance/refresh, tenant + role
  management, invite flow for new users.
- **Owns**: `users`, `tenants`, `invitations` tables.
- **Tech**: FastAPI + Supabase Auth/Clerk as the identity provider behind it
  (this service is mostly a thin wrapper + tenant-role mapping).

### `admin-config-service`
- **Responsibility**: CRUD for `prompt_configs` (rules, versioned) and
  `guardrail_policies`, tenant-level settings, theming config.
- **Owns**: `prompt_configs`, `guardrail_policies`, `tenant_settings`
  tables.
- **Called by**: Admin Portal directly; read by `llm-orchestrator-service`
  on every chat request (cached, see Module 5).

### `ingestion-service`
- **Responsibility**: accepts uploads, writes to object storage, creates a
  `documents` row, and enqueues a Celery job that runs the full
  parse → chunk → embed → store pipeline (using `ai-core` as a library).
  Also exposes a synchronous "transient parse" endpoint for the User
  Portal's tender-upload flow (Module 4, Layer 4), which does not persist
  to the permanent knowledge base.
- **Owns**: `documents` table, Celery workers.
- **Tech**: FastAPI (API) + Celery workers (processing), imports `ai-core`.

### `retrieval-service`
- **Responsibility**: given a query (or extracted requirement JSON), runs
  hybrid search + rerank against Qdrant, scoped to the calling tenant, and
  returns the top matches with citation metadata.
- **Owns**: no database of its own — reads Qdrant, which is populated by
  `ingestion-service`.
- **Tech**: FastAPI, imports `ai-core` (reranking module).

### `llm-orchestrator-service`
- **Responsibility**: the core RAG "brain." Assembles the final prompt
  (active rules from `admin-config-service` + retrieved context from
  `retrieval-service` + chat history from `chat-service`), applies the
  sensitivity-based routing rule (Module 4, Layer 7), calls the LLM router,
  and streams tokens back.
- **Owns**: no persistent data — it's a pure orchestration layer.
- **Tech**: FastAPI, imports `ai-core` (llm_router module).

### `chat-service`
- **Responsibility**: owns chat sessions and message history, exposes the
  SSE endpoint the User Portal connects to (which internally calls
  `llm-orchestrator-service` and streams its output through), and records
  feedback (thumbs up/down).
- **Owns**: `chat_sessions`, `chat_messages`, `feedback` tables.
- **Tech**: FastAPI with SSE support.

### `notification-service` (optional, add when needed)
- **Responsibility**: pushes ingestion status updates to the Admin Portal
  (websocket or polling-backed), and optionally emails a tenant admin when
  a batch upload finishes or fails.
- **Tech**: FastAPI + websockets, or a simple polling endpoint if
  websockets aren't needed yet — this is the one service safe to defer
  until Module 9's later phases.

## 3. How services talk to each other

- **Synchronous** (REST over HTTP, internal network only): Gateway → any
  service; `llm-orchestrator-service` → `retrieval-service` and →
  `admin-config-service`; `chat-service` → `llm-orchestrator-service`.
- **Asynchronous** (Celery + Redis as the broker): `ingestion-service`'s API
  process → its own Celery workers, for the parse/chunk/embed pipeline.
  This is the only place a queue is required at first; add Redis Streams or
  RabbitMQ later only if more services need to publish events (e.g. "document
  indexed" fan-out to `notification-service`).

## 4. API contract conventions (apply to every service)

- Every request carries `tenant_id` and `role` as headers, injected by the
  gateway from the validated JWT — services trust the gateway, not the raw
  client.
- Every list/search endpoint is implicitly scoped to `tenant_id` at the
  query level — there is no endpoint that can return cross-tenant data,
  by construction, not by convention.
- Every service exposes `/health` and `/metrics` (Prometheus format) for
  the observability stack (Module 6).
- Shared request/response models live in `shared-libs/schemas` and are
  imported, never redefined per service — this is what keeps the
  `documents` object, for example, identical whether it's returned by
  `ingestion-service` or read by `retrieval-service`.
