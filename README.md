# RAG Platform — Enterprise Multi-Tenant HRMS Chatbot

A production-grade, **multi-tenant Retrieval-Augmented Generation (RAG)** chatbot
platform built as a set of independent FastAPI microservices. Internal domains
(Healthcare, Retail, HR/HRMS, …) run side-by-side, each isolated as its own tenant
with **row-level security on every table**, per-tenant vector payloads, and
tenant-scoped cache keys.

## ✨ Highlights

- **Microservices** — 7 FastAPI services behind a single gateway (JWT auth, rate limiting, health checks).
- **RAG pipeline** — upload → parse → chunk → embed → hybrid search → rerank → grounded LLM answer with citations.
- **Multi-tenancy** — isolation enforced at the database (row-level security), vector store, and cache layers.
- **LLM routing** — Groq → Gemini → OpenRouter → local Ollama with automatic fallback.
- **Guardrails & PII** — prompt-level guardrail policies and PII scrubbing before cloud LLM calls.
- **Observability** — structured JSON logs, Prometheus metrics, OpenTelemetry tracing.
- **Frontends** — Next.js admin portal (:3000) and user chat portal (:3001).
- **Evals** — offline evaluation harness with retrieval/answer quality metrics.

## 📁 Repository structure

```text
HRMSRag/
├── services/                     # FastAPI microservices (each a src/ package)
│   ├── gateway/                  #   :8000  single API entry, proxy
│   ├── auth-service/             #   :8001  login, JWT, tenants & users
│   ├── admin-config-service/     #   :8002  system prompts + guardrail policies
│   ├── ingestion-service/        #   :8003  upload → parse → chunk → embed
│   ├── retrieval-service/        #   :8004  hybrid search + rerank
│   ├── llm-orchestrator-service/ #   :8005  RAG prompt + LLM + guardrails
│   └── chat-service/             #   :8006  sessions / messages / SSE
├── shared-libs/                  # Reusable libraries (editable installs)
│   ├── schemas/                  # shared Pydantic models
│   ├── auth-middleware/          # JWT validation + tenant context
│   ├── observability/            # logs / metrics / traces
│   └── pii/                      # PII scrubbing
├── ai-core/                      # AI pipeline packages (no HTTP)
│   ├── parsing/                  # file → text
│   ├── chunking/                 # text → chunks
│   ├── embedding/                # chunks → vectors
│   ├── reranking/                # rank passages for a query
│   └── llm_router/               # Groq → Gemini → OpenRouter → Ollama
├── frontend/                     # Next.js npm workspaces
│   ├── admin-portal/             # :3000  admin app
│   ├── user-portal/              # :3001  user chat app
│   └── shared-ui/                # shared React components
├── data/                         # Postgres Alembic migrations, Qdrant, Redis
├── evals/                        # offline RAG evaluation harness
├── infra/                        # Docker, Kubernetes, Terraform, CI/CD
├── scripts/                      # PowerShell helpers for local dev
├── samples/demo/                 # demo documents to upload
├── docs/                         # architecture, runbooks, module specs
├── .env.example                  # env template — copy to .env
├── docker-compose.dev.yml        # Postgres + Redis + Qdrant
├── Makefile                      # up / down / migrate / test / lint
└── requirements.txt              # all Python deps (editable installs)
```

Every Python package uses the `src/` layout (`<pkg>/src/rag_platform_*/`) and is
installed **editable** from the root `requirements.txt`, so imports work across the
monorepo with no path hacks.

## ✅ Prerequisites

| Tool | Version |
|---|---|
| Docker Desktop | 24+ (must be running) |
| Docker Compose | v2.20+ |
| Python | 3.11+ (3.13 OK) |
| Node.js | 20+ |

## 🚀 Installation

### Windows (recommended)

Open PowerShell in the folder that contains `docker-compose.dev.yml`:

```powershell
# Allow scripts for this window only
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 1) One-time setup: venv + Python deps + npm install + Docker images
.\scripts\setup_local.ps1

# 2) Create your environment file and edit it
copy .env.example .env
#    → set GROQ_API_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD, JWT_SECRET_KEY
#      (full guide: docs/API_KEYS.md)

# 3) Start everything: Docker infra + all APIs + both portals
.\scripts\start_local.ps1

# 4) First run only: create demo accounts
.\scripts\bootstrap_demo.ps1
```

| App | URL |
|---|---|
| Admin portal | http://localhost:3000 |
| User portal | http://localhost:3001 |
| API gateway health | http://localhost:8000/health |

Stop everything:

```powershell
.\scripts\stop_local.ps1
```

### Manual install (any OS)

```powershell
# Python environment + deps
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Linux/macOS: source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt

# Frontend deps
cd frontend && npm install && cd ..

# Infrastructure (Postgres :15432, Redis :16379, Qdrant :6333)
docker compose -f docker-compose.dev.yml -f docker-compose.override.yml up -d

# Database migrations
$env:DATABASE_URL_SYNC = "postgresql://raguser:<POSTGRES_PASSWORD>@127.0.0.1:15432/ragplatform"
cd data\postgres
python -m alembic upgrade head
cd ..\..
```

### macOS / Linux (Make)

```bash
cp .env.example .env        # fill in values
make up                     # start Postgres + Redis + Qdrant
make migrate                # run Alembic migrations
# then start each service with uvicorn, e.g.:
# uvicorn app.main:app --app-dir services/gateway --port 8000 --reload
```

## 🧪 Usage examples

**Start / stop the stack**

```powershell
.\scripts\start_local.ps1
.\scripts\stop_local.ps1
docker compose -f docker-compose.dev.yml down
```

**Health check**

```bash
curl http://localhost:8000/health
```

**Bootstrap a tenant + users (manual)**

```bash
# create a tenant (copy the returned id)
curl -X POST http://localhost:8001/api/v1/tenants \
  -H "setup-token: local-setup-token" \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo Corp","domain":"demo"}'

# register an admin and a user with that tenant id
curl -X POST http://localhost:8001/api/v1/auth/register-admin \
  -H "setup-token: local-setup-token" -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"StrongPassword123!","tenant_id":"<TENANT_ID>","role":"admin"}'

curl -X POST http://localhost:8001/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"StrongPassword123!","tenant_id":"<TENANT_ID>"}'
```

**Upload documents and chat**

1. Admin portal → **Documents** → upload files from `samples/demo/`.
2. Wait until each file shows **Indexed**.
3. User portal → **Chat** → ask, e.g., *"How many annual leave days do we get?"*

More sample questions: [`samples/demo/README.md`](samples/demo/README.md).

**Demo accounts**

| Portal | Email | Password |
|---|---|---|
| Admin — Super Admin | `superadmin@example.com` | `StrongPassword123!` |
| Admin — Demo Corp | `admin@example.com` | `StrongPassword123!` |
| User | `user@example.com` | `StrongPassword123!` |

> Demo-only credentials — change them outside local development.

**Make targets**

```text
make up        start infrastructure containers
make down      stop containers (volumes preserved)
make migrate   run Alembic migrations
make test      run all service unit tests
make lint      ruff lint across services/ ai-core/ shared-libs/ data/
make format    ruff format across the same
make ps        container status
make shell-db  psql inside the Postgres container
```

## 🔐 Multi-tenancy

Every table, every Qdrant payload, and every cache key carries a
`tenant_id`/`organization_id`. Onboarding a new domain = create a tenant record +
invite an admin — **no new code, no new deployment**.

## 🛡️ Security

- `.env`, `.env.local`, `*.bak` and other secret-bearing files are git-ignored — **never commit them**.
- New API keys must come from environment variables or a secrets manager, never from source code.
- Kubernetes secrets: `infra/k8s/base/secrets.example.yaml` (populate via External Secrets / sealed-secrets — see `infra/k8s/README.md`).

## 📚 Documentation

| Doc | Purpose |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Modules, ports, sequence diagrams |
| [docs/SETUP_AND_RUN.md](docs/SETUP_AND_RUN.md) | Step-by-step local setup |
| [docs/API_KEYS.md](docs/API_KEYS.md) | LLM provider keys setup |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | Operations / troubleshooting |
| [docs/PROJECT_KNOWLEDGE_BASE.md](docs/PROJECT_KNOWLEDGE_BASE.md) | Ground-truth technical dump |
| [docs/modules/](docs/modules/) | Full product specs (01–09) |

## 🤝 Contributing

1. Fork the repo and create a feature branch.
2. Run `make lint` and `make test` locally before opening a PR.
3. Follow the conventions in `docs/modules/AI_DEVELOPMENT_RULES.md`.