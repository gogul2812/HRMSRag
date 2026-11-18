# RAG Platform — Enterprise Multi-Tenant HRMS

A production-grade, multi-tenant Retrieval-Augmented Generation (RAG) chatbot
platform built as a set of independent microservices. It is used across multiple
internal domains simultaneously (Healthcare, Clothing/Retail, HR/HRMS, and any
future domain), with each domain isolated as its own tenant.

> **New machine / teammate?** Follow **[`docs/SETUP_AND_RUN.md`](docs/SETUP_AND_RUN.md)**  
> Commands: `setup_local.ps1` -> edit `.env` -> `start_local.ps1` -> `bootstrap_demo.ps1`  
> Always `cd` into the folder that contains `docker-compose.dev.yml` (inner `rag-platform`).

## Prerequisites

| Tool | Version |
|---|---|
| Docker Desktop | 24+ (must be running) |
| Docker Compose | v2.20+ |
| Python | 3.11+ (3.13 OK) |
| Node.js | 20+ |

---

## Quick start (Windows — recommended)

Open **PowerShell** in the `rag-platform` folder:

```powershell
# Allow scripts for this window only
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 1) First time on this PC (venv + requirements.txt + npm + Docker + migrations)
.\scripts\setup_local.ps1

# 2) Edit .env — set GROQ_API_KEY and CHANGE_ME passwords (see docs/API_KEYS.md)

# 3) Start APIs + Admin (:3000) + User (:3001)
.\scripts\start_local.ps1

# 4) Create demo Super Admin / Demo Corp / admin / user (first time only)
.\scripts\bootstrap_demo.ps1
```

| App | URL |
|---|---|
| Admin portal | http://localhost:3000 |
| User portal | http://localhost:3001 |
| API gateway health | http://localhost:8000/health |

**Stop APIs:** `.\scripts\stop_local.ps1`

Python deps live in root [`requirements.txt`](requirements.txt) (editable installs of all services + ai-core + shared-libs).

---

## How to run (Windows — PowerShell) detailed

Open PowerShell in the `rag-platform` folder for every step.

### A) First time on a machine (one-time setup)

Prefer: `.\scripts\setup_local.ps1` (does steps 1–5 below).

**1. Environment file**

```powershell
copy .env.example .env
```

Edit `.env` and set at least:

```env
GROQ_API_KEY=gsk_your_key_here
LLM_ROUTER_MODE=litellm
CHAT_FAKE_ORCHESTRATOR=0
POSTGRES_PASSWORD=your_strong_password
REDIS_PASSWORD=your_redis_password
JWT_SECRET_KEY=any_long_random_string
SETUP_TOKEN=local-setup-token
```

Do **not** wrap the Groq key in quotes. Full key guide: [`docs/API_KEYS.md`](docs/API_KEYS.md).

**2. Install Python packages**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
```

**3. Install frontend dependencies**

```powershell
cd frontend
npm install
cd ..
```

**4. Start Docker infra (Postgres, Redis, Qdrant)**

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.override.yml up -d
```

Wait until containers are healthy (`docker compose … ps`). Host ports:

| Service | Host port |
|---|---|
| Postgres | **15432** |
| Redis | **16379** |
| Qdrant | **6333** |

**5. Run database migrations**

```powershell
# Use the same POSTGRES_PASSWORD as in .env
$env:DATABASE_URL_SYNC = "postgresql://raguser:<POSTGRES_PASSWORD>@127.0.0.1:15432/ragplatform"
cd data\postgres
python -m alembic upgrade head
cd ..\..
```

---

### B) Start the app (every day)

```powershell
cd <path>\rag-platform
.\scripts\start_local.ps1
```

This starts Docker (if needed), all API services, and both portals. It uses `.venv\Scripts\python.exe` when present.

| App | URL |
|---|---|
| Admin portal | http://localhost:3000 |
| User portal | http://localhost:3001 |
| API gateway health | http://localhost:8000/health |

**Stop API services:**

```powershell
.\scripts\stop_local.ps1
```

---

### C) First-time login (only if DB is empty)

Prefer: `.\scripts\bootstrap_demo.ps1`

If you already have the demo tenant on this machine, skip to **D**.

```powershell
# 1) Create tenant (copy the returned id)
curl.exe -X POST http://localhost:8001/api/v1/tenants `
  -H "setup-token: local-setup-token" `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"Demo Corp\",\"domain\":\"demo\"}"

# 2) Register admin (paste tenant id)
curl.exe -X POST http://localhost:8001/api/v1/auth/register-admin `
  -H "setup-token: local-setup-token" `
  -H "Content-Type: application/json" `
  -d "{\"email\":\"admin@example.com\",\"password\":\"StrongPassword123!\",\"tenant_id\":\"PASTE_TENANT_ID\",\"role\":\"admin\"}"

# 3) Register end user (same tenant id)
curl.exe -X POST http://localhost:8001/api/v1/auth/register `
  -H "Content-Type: application/json" `
  -d "{\"email\":\"user@example.com\",\"password\":\"StrongPassword123!\",\"tenant_id\":\"PASTE_TENANT_ID\"}"
```

### D) Demo credentials (this machine)

**Organization login (User / Org Admin portals)** — pick organization from dropdown (no Tenant ID):

| Field | Value |
|---|---|
| Organization | Demo Corp (or any org you create) |
| Admin | `admin@example.com` / `StrongPassword123!` (existing Demo Corp admin) |
| User | `user@example.com` / `StrongPassword123!` |

**Platform Super Admin** (Admin portal → check “Platform Super Admin”):

| Field | Value |
|---|---|
| Email | `superadmin@example.com` |
| Password | `StrongPassword123!` |

Bootstrap Super Admin once (if missing):

```powershell
curl.exe -X POST http://localhost:8000/api/v1/organizations/bootstrap-super-admin `
  -H "setup-token: local-setup-token" `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"Platform Super Admin\",\"email\":\"superadmin@example.com\",\"password\":\"StrongPassword123!\"}"
```

Use SETUP_TOKEN from your `.env` if it differs.

Auth model: Organization dropdown → JWT carries `organization_id` (same isolation as former `tenant_id` in data stores). See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

### E) Upload docs and chat

1. Admin portal → **Documents** → upload files from `samples/demo/`
2. Wait until each file shows **Indexed**
3. User portal → **Chat** → ask e.g. *How many annual leave days do we get?*

More sample questions: [`samples/demo/README.md`](samples/demo/README.md).

---

## Copying to another laptop

1. Zip `rag-platform` (omit `frontend/node_modules`, `.venv`, `logs`).
2. On the new PC: install Docker / Python / Node.
3. Follow **[`docs/SETUP_AND_RUN.md`](docs/SETUP_AND_RUN.md)** (`setup_local.ps1` → edit `.env` → `start_local.ps1` → `bootstrap_demo.ps1`).
4. Fresh Docker volumes mean empty DB + empty Qdrant → bootstrap users and re-upload demo docs.

---

## Architecture (modules & submodules)

**Full write-up with diagrams:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

**Complete ground-truth dump for team / LLM assistants (ports, Docker, Redis, Pydantic, AI pipeline, flows):** [`docs/PROJECT_KNOWLEDGE_BASE.md`](docs/PROJECT_KNOWLEDGE_BASE.md)

**New laptop / teammate setup:** [`docs/SETUP_AND_RUN.md`](docs/SETUP_AND_RUN.md)

### High-level layout

```text
Admin :3000 ──┐                    ┌─ Auth :8001
              ├──► Gateway :8000 ──┼─ Admin-config :8002
User  :3001 ──┘                    ├─ Ingestion :8003 ──► Celery ──► Qdrant
                                   ├─ Retrieval :8004 ◄─────────────┘
                                   ├─ Orchestrator :8005 ──► LLM (Groq…)
                                   └─ Chat :8006 ──► Orchestrator

Postgres (metadata) · Redis (jobs) · Qdrant (vectors)
```

### Modules

| Module | Path | What it is |
|---|---|---|
| **Frontend** | `frontend/` | Next.js apps |
| **Services** | `services/` | FastAPI microservices |
| **AI Core** | `ai-core/` | Shared AI libraries (not HTTP) |
| **Shared libs** | `shared-libs/` | Schemas, JWT, logging, PII |
| **Data** | `data/` | Alembic + Qdrant setup |
| **Infra** | `infra/` | Docker / K8s / CI |
| **Scripts** | `scripts/` | `start_local.ps1` / `stop_local.ps1` |
| **Samples** | `samples/demo/` | Demo docs to upload |
| **Docs** | `docs/` | Specs + architecture |

### Frontend submodules

| Submodule | Port | Job |
|---|---|---|
| `admin-portal` | 3000 | Upload docs, rules, guardrails, users |
| `user-portal` | 3001 | Chat, compare, history |
| `shared-ui` | — | Shared UI package |

### Backend service submodules

| Service | Port | Job |
|---|---|---|
| `gateway` | 8000 | Single API entry; proxies to others |
| `auth-service` | 8001 | Login, JWT, tenants/users |
| `admin-config-service` | 8002 | System prompts + guardrail policies |
| `ingestion-service` | 8003 | Upload → parse → chunk → embed → Qdrant |
| `retrieval-service` | 8004 | Hybrid search + rerank |
| `llm-orchestrator-service` | 8005 | RAG prompt + LLM + guardrails |
| `chat-service` | 8006 | Sessions / messages / SSE |
| `notification-service` | — | Stub (not fully wired) |

Typical service folder: `app/api` → `app/application` → `app/domain` → `app/infrastructure`.

### AI Core submodules (pipeline)

| Layer | Package | Job |
|---|---|---|
| 1 | `ai-core/parsing` | File → text |
| 2 | `ai-core/chunking` | Text → chunks |
| 3 | `ai-core/embedding` | Chunks → vectors |
| 5 | `ai-core/reranking` | Rank passages for a query |
| 7 | `ai-core/llm_router` | Groq → Gemini → OpenRouter → Ollama |

### Shared library submodules

| Package | Job |
|---|---|
| `shared-libs/schemas` | Shared Pydantic models |
| `shared-libs/auth-middleware` | JWT + tenant context |
| `shared-libs/observability` | Logs / metrics / traces |
| `shared-libs/pii` | Scrub sensitive data before cloud LLM |

### Main flows (short)

1. **Upload:** Admin → Gateway → Ingestion → Celery (parse/chunk/embed) → Qdrant + Postgres  
2. **Chat:** User → Gateway → Chat → Orchestrator → Retrieval (+ Admin-config) → LLM → answer with citations  

### Documentation index

| Doc | Purpose |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Modules, ports, sequence diagrams |
| [`docs/API_KEYS.md`](docs/API_KEYS.md) | Groq / Gemini / OpenRouter keys |
| [`docs/modules/`](docs/modules/) | Full product specs (01–09) |
| [`samples/demo/README.md`](samples/demo/README.md) | Demo login + test questions |
## Multi-Tenancy

Every table, every vector payload, and every cache key carries a `tenant_id`.
This is non-negotiable — built in from the very first migration. A new
domain/tenant is onboarded by: creating a tenant record, inviting an admin, and
letting them upload documents and configure rules. No new code, no new
deployment.

## Key Contacts

See individual service `README.md` files for ownership and runbook information.
