# Module 1 — Requirements & Project Structure

> Read this module first. Every other module assumes the structure, stack,
> and design principles defined here.

## 1. What this platform is

A production-grade, multi-tenant Retrieval-Augmented Generation (RAG)
chatbot platform, built as a set of independent microservices rather than a
single monolithic backend. It is used across multiple internal domains at
once (e.g. Healthcare projects, Clothing/Retail projects, HR/HRMS-style
employee and resource data, and any future domain), with each domain
isolated as its own tenant.

There are two portals, each with its own URL:

- **Admin Portal** (`admin.<company>.internal`) — sign in as an admin for a
  given tenant/domain. Upload documents (e.g. 100+ project `.md`/`.docx`
  files, resource and worker experience documents), and configure the AI
  agent: system rules, tone, refusal behavior, and guardrail policy. This is
  where the AI agent's behavior is programmed, without touching code.
- **User Portal** (`app.<company>.internal`) — sign in as an end user for
  that tenant. Ask general questions, or upload a document (e.g. a tender,
  RFP, spec sheet) and ask whether related content already exists in the
  tenant's knowledge base, with a grounded, cited answer either way.

## 2. Functional requirements

- Support 10+ concurrent tenants/domains, each with its own document set,
  rules, and guardrail policy — fully isolated from one another.
- Each tenant's admin can upload 100+ documents (mixed formats: `.md`,
  `.docx`, `.pdf`, scanned files) without any code change.
- Each tenant's admin can configure the AI agent's instructions/rules
  through a UI, versioned, with one active version at a time.
- End users can: (a) ask general questions answered from their tenant's
  knowledge base, and (b) upload a document and ask whether equivalent or
  related content already exists, receiving a comparison-style answer.
- Every answer must cite its source document(s).
- The system must degrade gracefully if any single AI provider is
  unavailable or deprecated.
- New tenants/domains must be addable via configuration and data only — no
  new deployment, no new code path.

## 3. Non-functional requirements

- **Microservice architecture** — independently deployable, independently
  scalable services, not a single FastAPI monolith.
- **Multi-tenancy** — hard data isolation between tenants at every data
  layer (relational DB, vector DB, object storage).
- **Resilience** — no single point of failure on any one LLM/embedding
  vendor.
- **Observability** — every service emits structured logs, metrics, and
  traces; every RAG answer is auditable end-to-end.
- **Security & compliance** — PII-aware by default, since HR/employee data
  is one of the domains in scope.
- **Horizontal scalability** — ingestion and retrieval must scale
  independently of each other (a large document upload burst must not slow
  down live chat).

## 4. Repository / folder structure

A monorepo is recommended for this team size, with clear service boundaries
so it can be split into polyrepos later without redesigning anything.

```
rag-platform/
├── frontend/
│   ├── admin-portal/              # Next.js app — admin-facing
│   ├── user-portal/                # Next.js app — end-user facing
│   └── shared-ui/                  # shared component library (design tokens, shadcn/ui wrapper)
│
├── services/
│   ├── gateway/                    # API gateway — single entry point, routes to services below
│   ├── auth-service/                # login, JWT issuing, tenant + role management
│   ├── admin-config-service/        # prompt/rules config, guardrail policy, tenant management
│   ├── ingestion-service/           # upload handling + orchestrates parse→chunk→embed→store
│   ├── retrieval-service/           # hybrid search + rerank against the vector DB
│   ├── llm-orchestrator-service/    # prompt assembly + LLM fallback router + streaming
│   ├── chat-service/                 # chat sessions/history, SSE endpoint for the User Portal
│   └── notification-service/         # ingestion status updates (websocket/polling), optional email
│
├── ai-core/                          # shared AI logic, imported as a library by the services above
│   ├── parsing/                       # Docling + Tesseract wrappers
│   ├── chunking/                       # LlamaIndex splitter configuration
│   ├── embedding/                       # BGE-large-en-v1.5 serving wrapper
│   ├── reranking/                       # bge-reranker-v2-m3 wrapper
│   └── llm_router/                       # litellm configuration, fallback chain definitions
│
├── shared-libs/
│   ├── schemas/                       # Pydantic models shared across services (single source of truth)
│   ├── auth-middleware/                # JWT validation, tenant-context injection, reused by every service
│   └── observability/                  # shared logging/tracing/metrics setup
│
├── data/
│   ├── postgres/                      # Alembic migrations
│   ├── qdrant/                         # collection schema definitions
│   └── redis/                          # queue/cache configuration
│
├── infra/
│   ├── docker/                        # one Dockerfile per service
│   ├── docker-compose/                 # local dev orchestration
│   ├── k8s/                            # Kubernetes manifests/Helm charts for production
│   ├── terraform/                       # cloud infrastructure as code
│   └── ci-cd/                           # GitHub Actions / GitLab CI pipelines, one per service
│
└── docs/
    └── modules/                        # this documentation set
```

**Why this structure**: every folder under `services/` is an independently
deployable unit with its own Dockerfile, its own database migrations (where
applicable), and its own CI/CD pipeline. `ai-core/` is a shared library, not
a service — it's imported by `ingestion-service` and `retrieval-service` so
the parsing/chunking/embedding logic is written once and used consistently
everywhere it's needed, rather than duplicated per service.

## 5. Complete technology stack (summary)

| Layer | Technology | Notes |
|---|---|---|
| Admin + User frontend | Next.js, TypeScript, Tailwind, shadcn/ui | Two separate apps, shared component library |
| API Gateway | Kong, or a lightweight FastAPI/Traefik gateway | Single entry point; handles routing, rate limiting, auth passthrough |
| Backend services | FastAPI (Python), one process per microservice | Async by default; matches team's Python strength |
| Inter-service communication | REST over HTTP (internal), Redis Streams or RabbitMQ for async events | Start with REST + a queue; add gRPC later only if latency demands it |
| Auth | Supabase Auth or Clerk, JWT-based | Tenant ID and role embedded in the token claims |
| Relational database | Postgres (one logical DB, schema-per-tenant or row-level security) | Metadata, users, rules, chat history |
| Vector database | Qdrant, self-hosted | Tagged by tenant/org ID, document type; supports hybrid search |
| Object storage | Cloudflare R2 / Supabase Storage / S3-compatible | Raw uploaded files |
| Async job queue | Celery + Redis (or RabbitMQ at larger scale) | Ingestion jobs, extraction jobs |
| Document parsing | Docling + Tesseract OCR | Text, tables, images, scanned documents |
| Chunking | LlamaIndex splitter (recursive / header-aware) | Table-aware, never splits a row |
| Embedding model | BGE-large-en-v1.5 (BAAI), local | Self-hosted, no data leaves the network |
| Reranker | bge-reranker-v2-m3, local | Narrows top-20 to top-5 before generation |
| LLM orchestration | litellm | Fallback chain: Groq → Gemini → OpenRouter → local Ollama |
| Local LLM (final fallback + sensitive queries) | Ollama running Llama 3.3 70B / Qwen2.5 72B | Never leaves the network; used for any query touching PII |
| Guardrails | Guardrails AI / NeMo Guardrails, Microsoft Presidio | Per-tenant policy, declarative |
| Containers | Docker | One image per service |
| Orchestration | Docker Compose (dev) → Kubernetes (production) | Path from POC to production scale |
| CI/CD | GitHub Actions | One pipeline per service, independent deploys |
| Observability | OpenTelemetry, Prometheus + Grafana, centralized logging (Loki/ELK) | Every service instrumented the same way |
| Evaluation | RAGAS | Faithfulness/relevancy/context-precision scoring per tenant |

Detailed reasoning for each of these choices (alternatives considered, why
this one) lives in Module 4 (AI stack) and Module 3 (backend/microservices);
this table is the quick-reference summary.

## 6. Multi-tenancy is the central design constraint

Every table, every vector payload, and every cache key carries a
`tenant_id`. This is not optional and not deferred — it is built in from the
very first migration, because:

- The Healthcare team's data must never be retrievable by a query scoped to
  the Clothing/Retail team, or vice versa.
- Each tenant's admin configures their own rules/guardrails independently —
  a healthcare tenant might mandate a "consult a professional" disclaimer,
  a retail tenant might not need one at all.
- Onboarding a new domain/team should be: create a tenant record, invite an
  admin, let them upload documents and configure rules. No new code, no new
  deployment.

See Module 5 for the concrete schema and vector-tagging strategy that
implements this.

## 7. What's covered in the modules that follow

- **Module 2** — everything inside `frontend/`: pages, components, the
  chat streaming UI, the admin rules editor, and how they call the gateway.
- **Module 3** — everything inside `services/`: each microservice's job,
  its API surface, and its dependencies on the others.
- **Module 4** — everything inside `ai-core/`: the exact model/tool for
  parsing, chunking, embedding, storage, retrieval, reranking, and
  generation, with the reasoning behind each choice.
- **Module 5** — everything inside `data/`: schema, migrations, and the
  tenant-isolation mechanics in both Postgres and Qdrant.
- **Module 6** — everything inside `infra/`: how this actually runs, from a
  developer's laptop to a Kubernetes cluster.
- **Module 7** — security and guardrails in depth, including how a
  domain-specific compliance need (e.g. healthcare) is configured without
  touching code.
- **Module 8** — how each layer is tested, including RAG-specific
  evaluation.
- **Module 9** — the order to actually build all of this in, with a
  definition of done for each module.
