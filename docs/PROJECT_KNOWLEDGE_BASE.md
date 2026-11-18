# RAG Platform (RAG HRMS) — Complete Project Knowledge Base

> **Purpose of this document:** Feed this file to ChatGPT, Claude, or any other assistant when you need accurate answers about this codebase.  
> **Rule for consumers:** Prefer facts stated here over general RAG knowledge. If something is marked **NOT IMPLEMENTED**, **STUB**, or **UNKNOWN**, do not invent behavior. If a detail is absent from this file, say it is not documented here rather than guessing.

**Canonical project root:** `rag-platform/`  
**Product name in UI:** RAG HRMS  
**Last grounded against repository structure:** July 2026 (includes org-based auth, profile fields migration `0008`, document view/download APIs, sample rules/guardrails UI loaders)

---

## 1. What this project is

### 1.1 One-sentence definition

A **multi-tenant, microservice-based Retrieval-Augmented Generation (RAG) platform** for enterprise knowledge (demo focus: HRMS / company policies / project docs). Organizations upload documents; end users ask questions; answers are generated only from tenant-scoped retrieved context, with citations, guardrails, and an explicit **insufficient information** path.

### 1.2 What it is not

- Not a single monolithic Django/Rails app.
- Not a fine-tuned custom LLM product (generation uses third-party or local LLMs via a router).
- Not a general open-web chatbot; retrieval is limited to indexed org documents in Qdrant.
- Notification microservice is **planned/stub**, not a running local service.

### 1.3 Primary user roles

| Role string (DB/JWT) | UI label | Scope |
|----------------------|----------|--------|
| `super_admin` | Super Admin | Platform-wide; manages organizations; **no** `tenant_id` / org binding |
| `admin` | Org Admin / Admin | One organization; documents, rules, guardrails, org users |
| `end_user` | User | One organization; chat, compare, history, own profile |

**Important naming rule:** In the data layer, **Organization == Tenant**. Table is still `tenants`; column is still `tenant_id`. APIs and JWT also expose `organization_id` (same UUID when the user belongs to an org).

### 1.4 Two frontends

| App | Local URL | Audience |
|-----|-----------|----------|
| Admin portal | http://localhost:3000 | Super Admin + Org Admin |
| User portal | http://localhost:3001 | End users |

Both call the **gateway** at `http://localhost:8000` with a Bearer JWT after login.

---

## 2. High-level architecture

```text
┌────────────────────┐     ┌────────────────────┐
│  Admin Portal      │     │  User Portal       │
│  :3000  Next.js    │     │  :3001  Next.js    │
└─────────┬──────────┘     └─────────┬──────────┘
          │  HTTP + JWT              │
          └────────────┬─────────────┘
                       ▼
              ┌────────────────┐
              │  Gateway :8000 │  single public API entry
              └────────┬───────┘
         ┌─────────────┼─────────────┬──────────────┐
         ▼             ▼             ▼              ▼
    Auth :8001   Admin-cfg :8002  Ingest :8003   Chat :8006
                                   │                │
                                   ▼                ▼
                              Celery/Redis    Orchestrator :8005
                                   │                │
                                   ▼                ▼
                              Qdrant :6333    Retrieval :8004
                                   ▲                │
                                   └────────────────┘
                     Postgres (local host :15432) · Redis (local host :16379)
```

### 2.1 Layer responsibilities

| Layer | Path | Role |
|-------|------|------|
| Presentation | `frontend/` | Admin + User Next.js apps + `shared-ui` |
| Edge | `services/gateway` | Auth middleware, rate limit, reverse proxy |
| Domain APIs | `services/*` | FastAPI microservices |
| AI pipeline libraries | `ai-core/` | Parse → chunk → embed → rerank → LLM router (**not HTTP servers**) |
| Shared Python libs | `shared-libs/` | Pydantic schemas, JWT middleware, observability, PII scrub |
| Data | `data/` | Alembic migrations, Qdrant bootstrap, Postgres init SQL |
| Infra | `infra/` | Dockerfiles, K8s, CI templates |
| Ops scripts | `scripts/` | `start_local.ps1`, `stop_local.ps1`, verify helpers |
| Samples | `samples/demo/` | Demo leave / WFH / Project Phoenix markdown docs |
| Docs | `docs/` | Architecture, API keys, module specs |
| Evals | `evals/` | Offline RAG quality evaluation harness |

---

## 3. Complete tech stack (as implemented)

### 3.1 Languages & runtimes

| Component | Stack |
|-----------|--------|
| Backend services | **Python 3.11+** (3.13 OK per README), **FastAPI**, **Uvicorn** |
| Frontends | **Node.js 20+**, **Next.js** (App Router), TypeScript/React |
| Package management (Python) | Editable installs via `pip install -e …` for services, ai-core, shared-libs |
| Package management (JS) | npm **workspaces** under `frontend/` |

### 3.2 Data stores (Docker)

| Store | Image | Container name | Named volume | Default compose host port | Windows override host port |
|-------|-------|----------------|--------------|---------------------------|----------------------------|
| PostgreSQL | `postgres:16-alpine` | `ragplatform_postgres` | `ragplatform_postgres_data` | 5432 | **15432** |
| Redis | `redis:7-alpine` | `ragplatform_redis` | `ragplatform_redis_data` | 6379 | **16379** |
| Qdrant | `qdrant/qdrant:v1.13.6` | `ragplatform_qdrant` | `ragplatform_qdrant_data` | 6333 (HTTP), 6334 (gRPC) | same |

Compose files:

- `docker-compose.dev.yml` — infra only (Postgres, Redis, Qdrant)
- `docker-compose.override.yml` — remaps Postgres→15432, Redis→16379 to avoid Windows port clashes

Network: bridge `ragplatform_net`.

**Note:** Application microservices are **not** containerized in the default local `start_local.ps1` path; they run as local Uvicorn processes. Dockerfiles exist under `infra/` for deployment packaging.

### 3.3 Why each infrastructure piece exists

#### PostgreSQL

Stores **relational metadata and application state**, not chunk vectors:

- Organizations (`tenants`)
- Users + password hashes + profile fields
- Document upload metadata and indexing status
- Versioned system prompts (“Rules”) and guardrail policies
- Chat sessions, messages, feedback
- Row Level Security (RLS) helpers for tenant isolation

Drivers: **asyncpg** for async SQLAlchemy (`DATABASE_URL`), **psycopg2** / sync URL for Alembic (`DATABASE_URL_SYNC`).

#### Redis

Used for:

1. **Celery broker + result backend** for ingestion indexing jobs (`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` = `REDIS_URL`).
2. **JWT deny-list** on logout (`ragplatform:{tenant_id}:jwt_deny:{jti}`).
3. **Gateway rate limiting** keys (`ragplatform:ratelimit:tenant:…` or `…:ip:…`).

Redis runs with **requirepass** and **AOF** (`appendonly yes`, `appendfsync everysec`).

Local start often sets `CELERY_TASK_ALWAYS_EAGER=1` so tasks run in-process without a separate Celery worker process.

#### Qdrant (vector database)

Stores **embedding vectors + payload** for each text chunk:

- Collection name: **`document_chunks`**
- Vector size: **1024**
- Distance: **Cosine**
- Payload includes at least: `tenant_id`, `doc_id`, `doc_type`, `chunk_index`, `section`, `page`, `text`
- Keyword indexes on `tenant_id`, `doc_id`, `doc_type`

**Why Qdrant version v1.13.6:** newer `qdrant-client` versions call `/points/query`; older Qdrant server images (e.g. 1.9.x) break retrieval. Do not downgrade casually.

#### Object storage

Original uploaded bytes:

- Default: **local filesystem** under `LOCAL_STORAGE_PATH` (typically `./data/object-storage`)
- Optional: **S3-compatible** via boto3 (`STORAGE_BACKEND=s3`, `S3_*` env vars)

Key pattern: `{tenant_id}/{doc_type}/{doc_id}/{filename}`

### 3.4 AI / ML libraries (ai-core)

| Package | Job | Key deps / models |
|---------|-----|-------------------|
| `rag_platform_parsing` | File → text/tables | Docling (optional extra), pypdf, Pillow, pytesseract |
| `rag_platform_chunking` | Text → chunks | LlamaIndex MarkdownNodeParser + SentenceSplitter |
| `rag_platform_embedding` | Text → vectors | sentence-transformers; default **`BAAI/bge-large-en-v1.5`** (1024-d) |
| `rag_platform_reranking` | Query+passages scoring | sentence-transformers CrossEncoder; default **`BAAI/bge-reranker-v2-m3`** |
| `rag_platform_llm_router` | Chat completion | LiteLLM; Groq / Gemini / OpenRouter / Ollama |

### 3.5 Pydantic

**Pydantic v2** models in `shared-libs/schemas` are the **canonical API contract**. Services must not redefine their own incompatible copies of User, Document, JWTClaims, etc.

Package name: `rag_platform_schemas`.

Modules:

| Module | Domain |
|--------|--------|
| `auth.py` | Roles, tenants/orgs, users, login, JWT claims, profile, passwords |
| `common.py` | `ErrorResponse`, `HealthResponse`, pagination helpers |
| `config.py` | Prompt configs + guardrail policies |
| `documents.py` | Doc types/statuses, document DTOs, transient parse |
| `retrieval.py` | Retrieve request/response + chunk shape |
| `orchestration.py` | Orchestrate generate, citations, extract-requirements |
| `chat.py` | Sessions, messages, feedback |

See §10 for model field lists.

### 3.6 Other notable libraries

| Concern | Library / approach |
|---------|-------------------|
| Password hashing | Used inside auth-service (bcrypt-style via passlib/helpers in `auth_service.py`) |
| JWT | Auth-service issues tokens; gateway + `rag_platform_auth_middleware` validates |
| HTTP client between services | httpx (orchestrator → retrieval, etc.) |
| Observability | OpenTelemetry hooks + structured logging (`rag_platform_observability`); local often `OTEL_SDK_DISABLED=true` |
| PII scrubbing | `rag_platform_pii` — regex and/or Presidio (`PII_SCRUB_MODE`) |

---

## 4. Repository layout (factual)

```text
rag-platform/
├── ai-core/
│   ├── parsing/
│   ├── chunking/
│   ├── embedding/
│   ├── reranking/
│   ├── llm_router/
│   ├── samples/
│   └── tests/
├── data/
│   ├── postgres/          # Alembic + init SQL
│   ├── qdrant/            # collection schema/bootstrap
│   └── redis/             # notes
├── docs/                  # architecture + module specs + THIS FILE
├── evals/
├── frontend/
│   ├── admin-portal/      # :3000
│   ├── user-portal/       # :3001
│   └── shared-ui/
├── infra/                 # docker, k8s, ci-cd, terraform
├── samples/demo/          # demo markdown knowledge files
├── scripts/               # start_local.ps1, stop_local.ps1
├── services/
│   ├── gateway/           # :8000
│   ├── auth-service/      # :8001
│   ├── admin-config-service/  # :8002
│   ├── ingestion-service/ # :8003
│   ├── retrieval-service/ # :8004
│   ├── llm-orchestrator-service/ # :8005
│   ├── chat-service/      # :8006
│   └── notification-service/    # STUB / README only — not started locally
├── shared-libs/
│   ├── schemas/
│   ├── auth-middleware/
│   ├── observability/
│   └── pii/
├── docker-compose.dev.yml
├── docker-compose.override.yml
├── .env.example
└── README.md
```

Each live FastAPI service generally follows clean architecture under `app/`:

```text
app/
├── api/             # routers
├── application/     # use-cases
├── domain/          # ORM / entities (where present)
└── infrastructure/  # DB, Redis, Qdrant, HTTP clients, Celery
```

---

## 5. Docker — exact local infra behavior

### 5.1 Start command (as used by scripts)

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.override.yml up -d
```

### 5.2 Postgres container details

- Image: `postgres:16-alpine`
- Env: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` (password **required**)
- Init mount: `./data/postgres/init` → `/docker-entrypoint-initdb.d` (read-only)
- Init SQL enables extensions: `uuid-ossp`, `pg_trgm`, `btree_gin`
- Healthcheck: `pg_isready`

### 5.3 Redis container details

- Image: `redis:7-alpine`
- Command: `redis-server --requirepass … --appendonly yes --appendfsync everysec`
- Healthcheck: `redis-cli -a … ping`

### 5.4 Qdrant container details

- Image: `qdrant/qdrant:v1.13.6`
- Storage volume: `/qdrant/storage`
- Optional config mount: `./data/qdrant/config`
- API key auth optional via env (commented in compose by default)
- Healthcheck: `curl` to `/healthz`

### 5.5 What Docker does **not** run in default local script

Auth, gateway, admin-config, ingestion, retrieval, orchestrator, chat, Next.js portals — all started as host processes by `scripts/start_local.ps1`.

---

## 6. PostgreSQL schema (migrations)

Migration directory: `data/postgres/alembic/versions/`

| Revision | File | Effect |
|----------|------|--------|
| 0001 | `0001_create_tenants_and_users.py` | Creates `tenants`, `users` |
| 0002 | `0002_create_prompt_configs_and_guardrail_policies.py` | Creates `prompt_configs`, `guardrail_policies` |
| 0003 | `0003_create_documents.py` | Creates `documents` |
| 0004 | `0004_create_chat_tables.py` | Creates `chat_sessions`, `chat_messages`, `feedback` |
| 0005 | `0005_enable_rls.py` | RLS + `app_current_tenant_id()` |
| 0006 | `0006_org_auth_nullable_tenant.py` | Nullable `users.tenant_id` for super_admin; `full_name`; tenant `updated_at`/`created_by` |
| 0007 | `0007_rls_super_admin_and_public_orgs.py` | RLS updates for super_admin + public org list |
| 0008 | `0008_user_profile_fields.py` | `users.phone`, `job_title`, `department`, `location` |

### 6.1 Table: `tenants` (organizations)

Core columns (from 0001 + 0006):

- `id` UUID PK
- `name` string
- `domain` string **unique**
- `is_active` bool
- `created_at` timestamptz
- Later: `updated_at`, `created_by`

### 6.2 Table: `users`

- `id` UUID PK
- `tenant_id` UUID FK → tenants (**nullable** after 0006 for super_admin)
- `email` string
- `password_hash` string
- `role` string (`admin` | `end_user` | `super_admin`)
- `is_active` bool
- `created_at` timestamptz
- `full_name`, `updated_at` (0006)
- `phone`, `job_title`, `department`, `location` (0008)
- Unique: `(tenant_id, email)` for org users; partial unique index for super_admin emails

### 6.3 Table: `documents`

- `id`, `tenant_id`, `filename`, `doc_type`, `status`
- `uploaded_by`, `storage_key`, `content_type`, `byte_size`
- `chunk_count`, `error_message`
- `created_at`, `updated_at`

**Doc types (enum in schemas):** `project`, `employee`, `policy`, `other`  
**Statuses:** `pending`, `processing`, `indexed`, `failed`, `deleted`

### 6.4 Config tables

- `prompt_configs` — versioned system prompts (“Rules”), one active per tenant
- `guardrail_policies` — versioned JSON policies, one active per tenant

### 6.5 Chat tables

- `chat_sessions`, `chat_messages`, `feedback`

### 6.6 RLS

Postgres RLS is enabled so queries can be constrained by tenant GUC (`set_tenant_guc` from auth middleware). Super-admin policies allow null-tenant users and public org listing as of migrations 0006–0007.

---

## 7. Redis — exact usages

| Use case | Mechanism | Key pattern / notes |
|----------|-----------|---------------------|
| Celery broker | Redis URL DB 0 | Same as `REDIS_URL` |
| Celery results | Redis URL | Same backend |
| JWT revoke | SET with TTL matching token life | `ragplatform:{tenant_id}:jwt_deny:{jti}` |
| Rate limit | Gateway middleware | `ragplatform:ratelimit:tenant:{id}` or `…:ip:{ip}`; default ~120/min (`GATEWAY_RATE_LIMIT_PER_MINUTE`) |

Auth health endpoint reports Redis connectivity.

**Not implemented in running code:** notification-service Redis streams (README only).

---

## 8. Qdrant — exact vector schema

| Property | Value |
|----------|--------|
| Collection | `document_chunks` |
| Dimensionality | 1024 |
| Metric | Cosine |
| Point ID | Deterministic UUID5 from `{doc_id}:{chunk_index}` |
| Payload | `tenant_id`, `doc_id`, `doc_type`, `chunk_index`, `section`, `page`, `text` |

Retrieval **always** filters by `tenant_id` from the JWT. Optional filter: `doc_type`.

Soft-delete document: delete Qdrant points for `(tenant_id, doc_id)`, delete object storage object, mark DB status `deleted`.

---

## 9. Microservices catalog

Gateway proxies client paths under `/api/v1/*` to backends. Clients should talk to **:8000**, not individual ports, in normal operation.

| Service | Port | Path | Responsibility |
|---------|------|------|----------------|
| Gateway | 8000 | `services/gateway` | JWT check (except public paths), rate limit, proxy |
| Auth | 8001 | `services/auth-service` | Register/login/logout, JWT, orgs/users, profile |
| Admin config | 8002 | `services/admin-config-service` | Prompt + guardrail versioning |
| Ingestion | 8003 | `services/ingestion-service` | Upload, index pipeline, list/view/download/delete docs |
| Retrieval | 8004 | `services/retrieval-service` | Hybrid search + rerank |
| LLM orchestrator | 8005 | `services/llm-orchestrator-service` | Retrieve → prompt → LLM → guardrails → citations |
| Chat | 8006 | `services/chat-service` | Sessions/messages/SSE; calls orchestrator |
| Notification | 8007 (planned) | `services/notification-service` | **STUB** — not started by `start_local.ps1` |

### 9.1 Gateway public paths (no Bearer required)

Typically includes:

- `GET /health`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/register`
- `GET /api/v1/organizations/public`
- `POST /api/v1/organizations/bootstrap-super-admin`

(Exact allowlist lives in `services/gateway/app/middleware/auth.py`.)

### 9.2 Auth-service key endpoints

| Method | Path (service prefix `/api/v1`) | Notes |
|--------|----------------------------------|-------|
| POST | `/auth/register` | End user into an organization |
| POST | `/auth/register-admin` | Admin registration (setup/authorized) |
| POST | `/auth/login` | Issues access + refresh tokens |
| POST | `/auth/logout` | Deny-lists current token in Redis |
| GET | `/auth/me` | Current user |
| PATCH | `/auth/me` | Update profile fields |
| POST | `/auth/me/change-password` | Self-service password change |
| POST | `/tenants` | Create tenant (setup-token header) |
| GET | `/organizations/public` | Org dropdown for login |
| POST | `/organizations/bootstrap-super-admin` | One-time super admin |
| CRUD | `/organizations…` | Super Admin org management |
| | `/organizations/me/users…` | Org Admin user management |
| | `/organizations/{org_id}/users…` | Super Admin managing users in an org |

### 9.3 Ingestion key endpoints

| Method | Path | Notes |
|--------|------|-------|
| POST | `/ingest/upload` | Admin; multipart file + `doc_type` |
| GET | `/ingest/documents` | List for tenant |
| GET | `/ingest/documents/{id}` | Metadata |
| GET | `/ingest/documents/{id}/content` | JSON text view for text/markdown |
| GET | `/ingest/documents/{id}/download` | Raw bytes |
| DELETE | `/ingest/documents/{id}` | Soft delete + vector cleanup |
| POST | `/ingest/transient-parse` | Sync parse+chunk preview (tender flow); not persisted |

Allowed upload suffixes: `.md`, `.markdown`, `.pdf`, `.docx`, `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`.

### 9.4 Retrieval

- `POST /retrieve/query` with body `RetrieveRequest`

### 9.5 Orchestrator

- `POST /orchestrate/generate`
- `POST /orchestrate/stream`
- `POST /orchestrate/extract-requirements`

### 9.6 Chat

- Session CRUD + `POST …/message` and streaming variants
- Feedback on messages

### 9.7 Admin config

- Prompt: create, list versions, activate
- Guardrails: create, list versions, activate (`policy_json` with `refuse_topics`, `required_disclaimer`, `blocked_phrases`)

---

## 10. Pydantic contracts (ground truth highlights)

### 10.1 `UserRole`

```text
admin | end_user | super_admin
```

### 10.2 `JWTClaims` (conceptual fields)

Issued payload includes:

- `sub` — user id
- `tenant_id` — org id or empty for super_admin
- `organization_id` — same as tenant_id when set
- `role`
- `jti` — token id for revoke
- `exp`, `iat`
- `type` — `access` | `refresh`

### 10.3 `User` API shape

Includes: `id`, `tenant_id`, `organization_id`, `email`, `full_name`, `phone`, `job_title`, `department`, `location`, `role`, `is_active`, `created_at`  
**Never** returns `password_hash`.

### 10.4 `ProfileUpdate`

Optional: `name`, `phone`, `job_title`, `department`, `location`

### 10.5 `ChangePasswordRequest`

`current_password`, `new_password` (min length 8; rejects trivial passwords like `password`)

### 10.6 `RetrieveRequest`

- `query` (1–4000 chars)
- `doc_type` optional
- `top_k` default **5** (1–20)
- `candidate_limit` default **20** (5–50)

### 10.7 `RetrieveResponse`

- `chunks: list[RetrievedChunk]`
- `insufficient_information: bool`
- `best_score`, `message` optional

### 10.8 Document enums

See §6.3.

---

## 11. Frontend map

### 11.1 Admin portal routes (`frontend/admin-portal`)

| Route | Who | Purpose |
|-------|-----|---------|
| `/login` | all admin roles | Org dropdown login; Super Admin checkbox |
| `/dashboard` | org admin | Summary cards |
| `/documents` | org admin | Upload, list, **View**, Download, Delete |
| `/config/rules` | org admin | System prompt versions + **Load sample** |
| `/config/guardrails` | org admin | Guardrail versions + **Load sample** |
| `/users` | org admin | Create/list users; reset password; delete |
| `/organizations` | super admin | Org list/create/disable |
| `/organizations/[orgId]` | super admin | Users inside an org |
| `/profile` | all admin roles | Personal/professional profile + change password |

### 11.2 User portal routes (`frontend/user-portal`)

| Route | Purpose |
|-------|---------|
| `/login`, `/register` | Org-scoped auth |
| `/chat`, `/chat/[id]` | RAG chat |
| `/compare` | Tender/compare flow (transient parse + extract) |
| `/history` | Past sessions |
| `/profile` | Profile + change password |

### 11.3 Shared UI

`@rag-platform/shared-ui` provides `createApiClient` (get/post/put/**patch**/delete/upload), buttons, upload zone, badges, etc.

LocalStorage token keys differ:

- Admin: `rag_admin_access_token`, `rag_admin_tenant_id`, …
- User: `rag_user_access_token`, `rag_user_tenant_id`, …

---

## 12. AI pipeline — full detail (core of the product)

AI logic is packaged under `ai-core/` and invoked by ingestion, retrieval, and orchestrator services.

```text
INDEX PATH:
  bytes → parse → chunk → embed → Qdrant upsert + Postgres status=indexed

QUERY PATH:
  question → embed query → hybrid retrieve → rerank → score threshold
         → (optional) assemble prompt + scrub PII + LLM router + guardrails
         → answer + citations  OR  insufficient_information
```

### 12.1 Layer 1 — Parsing (`ai-core/parsing`)

**Entry:** `parse(file_bytes, filename) -> ParsedDocument`

**Outputs:** raw text, pages, structured tables (`ParsedTable` with headers/rows/markdown), metadata including which parser ran.

| Input type | Pipeline |
|------------|----------|
| `.md` / `.markdown` | UTF-8 decode; extract GFM tables |
| Images `.png/.jpg/.jpeg/.tif/.tiff` | Pillow + **Tesseract OCR** → text |
| `.pdf` | **Docling** → markdown + tables; on failure **pypdf** page text; on failure OCR path |
| `.docx` | **Docling** → markdown + tables |

**Tables:** Preserved as structured objects when possible (critical so numbers aren’t mangled).

**Diagrams:** No dedicated vision-diagram model. Diagrams become whatever Docling/OCR emits as text/markdown. Do **not** claim CLIP/multimodal image embeddings for diagrams unless the code is extended later.

**Parser tag in metadata:** `markdown` | `docling` | `pypdf` | `tesseract`

### 12.2 Layer 2 — Chunking (`ai-core/chunking`)

**Entry:** `chunk(parsed_document, doc_id=…, tenant_id=…, chunk_size=1600, chunk_overlap=240)`

Design intent (~300–500 tokens, ~15% overlap) implemented as character sizes (~4 chars/token heuristic).

Behavior:

1. Protect tables with placeholders so splitters do not cut mid-row.
2. Markdown-aware split via LlamaIndex `MarkdownNodeParser`.
3. Further split oversized nodes with `SentenceSplitter`.
4. Restore tables; drop empty chunks; assign `chunk_index`.
5. Infer `section` from markdown headings; infer `page` when page list exists.

Each `Chunk` carries: `text`, `chunk_index`, `doc_id`, `tenant_id`, `section`, `page`, plus optional metadata flags like `contains_table` (metadata may not all be stored in Qdrant — payload fields listed in §8 are what retrieval sees).

### 12.3 Layer 3 — Embedding (`ai-core/embedding`)

| Mode | When | Behavior |
|------|------|----------|
| **Real** | `EMBEDDING_MODEL_NAME=BAAI/bge-large-en-v1.5` (or other ST model of dim 1024) | `SentenceTransformer.encode(..., normalize_embeddings=True)` → **1024-d** |
| **Fake** | `fake` / `stub` / `test` | Deterministic pseudo-vector length 1024 (for local demos without downloading BGE) |

**Critical consistency rule:** The **same** embedding model (or fake function) must embed **documents at index time** and **queries at retrieval time**.

Device: `EMBEDDING_DEVICE` (`cpu` or `cuda`).

### 12.4 Layer 4 — Index write (ingestion worker)

File: `services/ingestion-service/app/worker.py` task `ingestion.index_document`

Steps:

1. Load document row; set `processing`
2. Read bytes from object storage
3. `parse(...)`
4. Fail if no usable text/tables
5. `chunk(...)`
6. `embed_texts([chunk.text…])`
7. `qdrant_store.upsert_chunks(...)`
8. Set `indexed` + `chunk_count`
9. On error: `failed` + truncated `error_message`

Local scripts often run Celery **eager**, so indexing happens inside the API process immediately.

### 12.5 Layer 5 — Retrieval + reranking

File: `services/retrieval-service/app/application/retrieval_service.py`

**Hybrid search (not dense-only):**

1. Embed query → dense Qdrant search (limit ~`retrieval_dense_limit`, default 20), filtered by `tenant_id` (+ optional `doc_type`)
2. Lexical search on payload `text` (Qdrant MatchText when available; else BM25-lite over scrolled corpus)
3. **Reciprocal Rank Fusion (RRF)** with k=60 → candidate list
4. **Rerank** with `rag_platform_reranking.rerank` → top_k
5. If no candidates OR best rerank score **&lt; `RETRIEVAL_SCORE_THRESHOLD`** → `insufficient_information=True` and **empty chunks**

Defaults:

- Threshold in service config often **0.25**
- `start_local.ps1` sets **0.15** when reranker is fake (fake scores are weaker)

**Reranker models:**

| Mode | Model |
|------|--------|
| Real | `BAAI/bge-reranker-v2-m3` CrossEncoder |
| Fake | Lexical overlap heuristic score in ~[0,1] |

### 12.6 Layer 6 — Transient tender / compare path

User portal can upload a tender/spec for **transient** parse (not stored in Qdrant). Orchestrator `extract-requirements` asks the LLM for structured JSON (skills, stack, etc.), which then drives retrieval — rather than dumping the entire tender into chat as one blob.

### 12.7 Layer 7 — LLM orchestration + router

File: `services/llm-orchestrator-service/app/application/orchestrator.py`

Flow:

1. If chunks not provided → call retrieval
2. If insufficient → return fixed message; **provider/model = none**; **no LLM call**
3. Load active tenant system prompt (Rules) or default “answer only from context”
4. If any context chunk `doc_type == employee` → **`force_local=True`** → **Ollama only**
5. Assemble messages with numbered sources `[source N doc_id=… section=… page=…]`
6. Scrub PII for cloud paths (`rag_platform_pii`); skip scrub when force_local
7. `rag_platform_llm_router.generate(...)`
8. Apply tenant guardrail policy
9. Build citations (excerpt ~280 chars)

**LLM router chain (`LLM_ROUTER_MODE=litellm`):**

1. Groq — default model `groq/llama-3.3-70b-versatile` (needs `GROQ_API_KEY`)
2. Gemini — `gemini/gemini-1.5-pro`
3. OpenRouter — free Llama instruct variant
4. Ollama — `OLLAMA_MODEL` default `llama3.3:70b` at `OLLAMA_BASE_URL`

`LLM_ROUTER_MODE=fake` → stub answers offline.

**Note:** `.env.example` has `LLM_DEFAULT_MODEL`; the router settings primarily use provider-specific model fields (e.g. Groq model). Do not assume every env key is read by every service without checking that service’s `config.py`.

### 12.8 Layer 8 — Guardrails & PII

**Guardrails (tenant DB policy JSON):**

- `refuse_topics` — topics the assistant should refuse
- `blocked_phrases` — strings that must not appear / trigger refusal handling
- `required_disclaimer` — appended/required disclaimer text

Admin UI can **Load sample** policies aligned with Demo Corp leave/WFH/Phoenix docs, then Publish & activate.

**PII:** `PII_SCRUB_MODE` = `auto` | `regex` | `presidio` | `off`  
Local start default often `regex`.

**Sensitivity routing** (employee docs → Ollama only) is separate from and stronger than PII scrubbing.

### 12.9 What “detecting and storing into vector DB” means in this project

There is **no separate ML classifier** that labels “this is a table” after embedding. Detection is **parse-time**:

1. File extension + parser routing chooses Docling / OCR / markdown.
2. Tables are detected by Docling export or GFM table regex.
3. Text (+ restored table markdown) is chunked.
4. Each chunk string is embedded to 1024 floats.
5. Qdrant stores vector + text payload under the tenant.

Images are **OCR’d to text**, then embedded as text — not as image vectors.

---

## 13. End-to-end flows (canonical)

### 13.1 Document indexing (Admin)

```text
Admin Portal Documents
  → POST /api/v1/ingest/upload (JWT admin)
  → Gateway → Ingestion
  → Save file to object storage
  → Insert documents row status=pending
  → Enqueue / eagerly run index_document
  → parse → chunk → embed → Qdrant upsert
  → status=indexed (or failed)
  → Admin can View content / Download original / poll status
```

### 13.2 Chat Q&A (User)

```text
User Portal Chat
  → POST /api/v1/chat/sessions/{id}/message (JWT end_user)
  → Gateway → Chat service (persist user message)
  → Chat → Orchestrator generate/stream
  → Orchestrator → Retrieval query (tenant filter)
  → If insufficient: return that message (no LLM)
  → Else: Rules + context + PII scrub + LLM router + guardrails
  → Persist assistant message + citations
  → Stream/return to UI
```

### 13.3 Org Admin creates a user

```text
Admin Users page
  → POST /api/v1/organizations/me/users
  → Auth service creates user with tenant_id = admin’s org
```

### 13.4 Super Admin manages orgs

```text
Admin Organizations
  → CRUD /api/v1/organizations
  → Drill into /organizations/{id} for that org’s users
```

### 13.5 Profile / change password (all roles)

```text
Profile page (admin or user portal)
  → GET/PATCH /api/v1/auth/me
  → POST /api/v1/auth/me/change-password
```

Admin “Reset password” on Users page is **admin resetting another user**, not self-service change-password.

---

## 14. Multi-tenancy & security model

1. **JWT** carries org/tenant id + role.
2. **Gateway** rejects invalid/expired/deny-listed tokens (except public routes).
3. **Services** filter by tenant from claims.
4. **Postgres RLS** + `set_tenant_guc` reinforce isolation.
5. **Qdrant** payload filter on `tenant_id` on every retrieve.
6. **Employee doc_type** forces local LLM only.
7. **CORS** typically allows `http://localhost:3000` and `:3001`.
8. Passwords stored hashed; never returned in User DTO.

---

## 15. Environment variables

### 15.1 From `.env.example` (must exist conceptually)

Categories: Postgres, Redis/Celery, Qdrant, JWT/Auth backends, S3, LLM providers, embedding/reranker, Presidio/guardrails paths, OTEL/logging, service ports 8000–8007, frontend public URLs, `APP_ENV`/`DEBUG`/`CORS_ORIGINS`.

### 15.2 Important vars used in practice but not always in `.env.example`

| Variable | Typical local role |
|----------|-------------------|
| `SETUP_TOKEN` | Bootstrap tenants / super admin / register-admin |
| `CELERY_TASK_ALWAYS_EAGER` | `1` for in-process indexing |
| `PII_SCRUB_MODE` | `regex` / `auto` / … |
| `RETRIEVAL_SCORE_THRESHOLD` | Confidence cutoff |
| `OTEL_SDK_DISABLED` | `true` locally |
| `STORAGE_BACKEND` / `LOCAL_STORAGE_PATH` | File storage |
| `GATEWAY_RATE_LIMIT_PER_MINUTE` | Rate limit |

### 15.3 Local `start_local.ps1` defaults when unset

- `LLM_ROUTER_MODE=litellm`
- `CHAT_FAKE_ORCHESTRATOR=0`
- `EMBEDDING_MODEL_NAME=fake`
- `RERANKER_MODEL_NAME=fake`
- `RETRIEVAL_SCORE_THRESHOLD=0.15` if reranker is fake
- `PII_SCRUB_MODE=regex`
- `CELERY_TASK_ALWAYS_EAGER=1`
- `OTEL_SDK_DISABLED=true`
- Rewrites DB/Redis URLs to **127.0.0.1:15432** and **16379** when placeholders detected
- Forces `QDRANT_HOST=127.0.0.1`

### 15.4 Production-oriented embedding defaults (`.env.example`)

- `EMBEDDING_MODEL_NAME=BAAI/bge-large-en-v1.5`
- `RERANKER_MODEL_NAME=BAAI/bge-reranker-v2-m3`

**Do not confuse local demo fake models with production BGE models.** Both write/read 1024-d vectors into the same Qdrant collection schema, but vectors from fake vs BGE are **not interchangeable** — re-index if you switch embedding model family.

---

## 16. How to run locally (Windows)

Prerequisites: Docker Desktop, Python 3.11+, Node 20+.

1. Copy `.env.example` → `.env`; set passwords, `JWT_SECRET_KEY`, `GROQ_API_KEY` (no quotes around key), `SETUP_TOKEN`.
2. `pip install -e` shared-libs, ai-core, and services (see README).
3. `cd frontend && npm install`
4. Start Docker infra; wait healthy.
5. `alembic upgrade head` from `data/postgres` with `DATABASE_URL_SYNC` pointing at host **15432**.
6. `.\scripts\start_local.ps1`
7. Bootstrap super admin / create org + users as in README.
8. Admin: upload `samples/demo/*`; wait Indexed; load sample Rules/Guardrails; User: chat.

Stop APIs: `.\scripts\stop_local.ps1`  
`-All` also stops frontend node processes and docker compose stop.

Demo Super Admin (if bootstrapped as documented):

- Email: `superadmin@example.com`
- Password: `StrongPassword123!`

---

## 17. Sample demo knowledge

Under `samples/demo/`:

1. Leave & attendance policy (annual/sick/casual leave numbers, apply process)
2. Work-from-home guidelines (hybrid days, core hours, eligibility)
3. Project Phoenix overview (pilot hospitals, owners, PHI rules, budget)

Admin Rules/Guardrails “Load sample” buttons populate drafts aligned with these docs; they still require **Publish & activate**.

---

## 18. Explicit non-goals / stubs / pitfalls (anti-hallucination)

| Claim | Reality |
|-------|---------|
| Notification microservice is live | **False** for local start — README stub only |
| Gateway `/admin/*` and `/notify/*` | Often **501 stub** routes |
| Diagrams embedded as images in Qdrant | **False** — OCR/text only |
| Separate “table embedding model” | **False** — tables → markdown/text → same BGE/fake embedder |
| Always uses real BGE locally | **False** — `start_local.ps1` defaults embedding/reranker to **fake** |
| `AUTH_BACKEND=supabase/clerk` fully wired | Treat as **selector present**; verify service code before claiming full SSO |
| `LLM_DEFAULT_MODEL` always drives router | Prefer reading `llm_router` config / Groq model fields |
| Switching fake↔BGE without re-ingest | **Broken retrieval** — re-index documents |
| Super Admin manages Documents | Super Admin is redirected away from org document routes; docs are **org admin** scoped |
| Flattened PDF always perfect | Docling preferred; pypdf/OCR are fallbacks with lower fidelity |

---

## 19. Related docs inside the repo

| File | Contents |
|------|----------|
| `README.md` | Runbook, ports, demo login |
| `docs/ARCHITECTURE.md` | Module map + sequence diagrams |
| `docs/API_KEYS.md` | Where to get Groq/Gemini/etc. |
| `docs/modules/04-ai-pipeline-module.md` | Product intent for AI layers |
| `docs/modules/01`–`09` | Broader product module specs |
| This file | **Single ground-truth dump for LLM assistants and team onboarding** |

---

## 20. One-page cheat sheet

```text
UI: Admin :3000 | User :3001
API: Gateway :8000 → Auth 8001, Config 8002, Ingest 8003, Retrieve 8004, Orch 8005, Chat 8006
Data: Postgres 15432 | Redis 16379 | Qdrant 6333 (collection document_chunks, 1024-d cosine)
AI libs: parse(Docling/OCR) → chunk(LlamaIndex) → embed(BGE or fake) → store(Qdrant)
Query: hybrid(dense+lexical) → RRF → rerank(BGE or fake) → threshold → LLM(Groq→…→Ollama)
Org isolation: JWT organization_id/tenant_id + Postgres RLS + Qdrant payload filter
Roles: super_admin | admin | end_user
```

---

*End of knowledge base. When answering questions about this project, quote or paraphrase from this document. If asked for something not listed here, state that it is outside this knowledge base rather than inventing APIs, models, ports, or behaviors.*

**To run on a new machine:** follow [`SETUP_AND_RUN.md`](SETUP_AND_RUN.md) — `.\scripts\setup_local.ps1` → edit `.env` → `.\scripts\start_local.ps1` → `.\scripts\bootstrap_demo.ps1`.
