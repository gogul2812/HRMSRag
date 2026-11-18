# Module 9 — Implementation Roadmap

> This module is written specifically to be handed to a coding agent
> (Claude Code, Cursor, etc.) alongside Modules 1–8. It defines build
> order and a definition of done for each stage. Do not skip ahead to a
> later stage until the current stage's definition of done is met —
> each stage is a working, testable checkpoint, not just a folder of code.

## How to use this module with a coding agent

Feed the agent Module 1 first, in full, as the shared context for every
subsequent instruction. Then work through the stages below **in order**,
pointing the agent at the specific module file relevant to that stage.
Each stage should end with something runnable, not just files created.

---

## Stage 0 — Repository scaffold

**Build:** the folder structure from Module 1, Section 4, as empty
directories with placeholder `README.md` files, plus root-level tooling:
`docker-compose.dev.yml`, `.env.example`, root `Makefile` or `justfile` with
common commands (`make up`, `make test`, `make migrate`).

**Definition of done:** `docker compose up` brings up empty
Postgres/Redis/Qdrant containers with no errors. Repo structure matches
Module 1 exactly.

---

## Stage 1 — `auth-service` + `gateway` (foundation, build first)

**Build:** per Module 3, Section "auth-service" and "gateway." Login,
JWT issuance, tenant + role claims, gateway routing skeleton (can 404 on
routes to services that don't exist yet).

**Definition of done:** can create a tenant, create an admin user and an
end-user for it, log in as each via the gateway, and receive a JWT whose
claims carry the correct `tenant_id` and `role`. A protected test route
correctly rejects a request with no token and a request with the wrong
role.

---

## Stage 2 — `admin-config-service`

**Build:** per Module 3 and Module 5's schema. CRUD for `prompt_configs`
and `guardrail_policies`, versioning + active-flag logic.

**Definition of done:** as an authenticated admin, create two versions of a
rules document for a tenant, mark one active, and confirm a GET for
"active config" returns the correct one. Confirm a second tenant's config
is completely invisible to the first tenant's admin.

---

## Stage 3 — `ai-core` as a standalone library (no service yet)

**Build:** per Module 4, Layers 1–3 only (parsing, chunking, embedding) as
plain Python functions/scripts, tested against 2–3 sample files (a `.md`
project doc, a `.pdf` with a table, a scanned image). No API, no database
yet — just `python run_pipeline.py sample.pdf` producing chunks and
vectors printed to console.

**Definition of done:** running the script on all three sample file types
produces sensible chunks (tables intact, no broken mid-row splits) and a
1024-dim vector per chunk. This is the single most important checkpoint in
the whole build — do not proceed to Stage 4 until this output looks
correct on manual inspection.

---

## Stage 4 — `ingestion-service`

**Build:** per Module 3 and Module 4, Layer 4. Wraps Stage 3's `ai-core`
functions behind a FastAPI upload endpoint + Celery worker, writes to
Qdrant (tagged per Module 5, Section 3) and updates the `documents` table.

**Definition of done:** upload the same 3 sample files through the real
API, watch `documents.status` move from `pending` → `indexed`, and confirm
the corresponding points exist in Qdrant with correct `tenant_id`/`doc_id`/
`doc_type` payloads. Upload a corrupted file and confirm status becomes
`failed` with a readable error, not a silent hang.

---

## Stage 5 — `retrieval-service`

**Build:** per Module 4, Layer 5. Hybrid search + rerank against the
vectors Stage 4 produced.

**Definition of done:** a query relevant to one of the 3 sample documents
returns that document's chunk in the top result, tenant-scoped (a query
from a different tenant's context returns nothing from this corpus). A
deliberately irrelevant query returns a low score that would trigger the
threshold cutoff.

---

## Stage 6 — `llm-orchestrator-service`

**Build:** per Module 4, Layers 6–8, and Module 3. Prompt assembly, the
litellm fallback chain, the sensitivity-routing rule, guardrail
application.

**Definition of done:** a command-line or `curl`-based test asks a real
question and gets a grounded, cited answer using Stage 5's retrieved
chunks. Force a failure of the primary LLM provider (invalid API key is
enough) and confirm the router falls through to the next provider
automatically. Upload a test document tagged `doc_type: employee`, ask a
question that retrieves it, and confirm the request goes to the local
Ollama model only.

---

## Stage 7 — `chat-service` + streaming

**Build:** per Module 3. Chat session/history persistence, SSE endpoint
wrapping Stage 6's orchestrator output.

**Definition of done:** a raw SSE client (or `curl -N`) connected to the
chat endpoint receives tokens incrementally, not all at once, and a second
call to the history endpoint shows the same conversation persisted.

---

## Stage 8 — Frontend: Admin Portal

**Build:** per Module 2. Document upload UI, rules editor, guardrail
config UI — wired to Stages 2 and 4's real APIs.

**Definition of done:** upload a real document through the UI and watch its
status update live; edit and publish a new rules version through the UI
and confirm (via Stage 6's test) that the new rules actually affect
answers.

---

## Stage 9 — Frontend: User Portal

**Build:** per Module 2. Streaming chat UI wired to Stage 7, citations
rendered, feedback buttons, and the tender-upload comparison flow wired to
Module 4 Layer 6 + Stage 5/6.

**Definition of done:** a full end-to-end manual test: log in as an end
user, ask a general question, get a cited streamed answer; upload a tender
PDF, get a feasibility/comparison answer referencing the right past
project or employee documents.

---

## Stage 10 — Security, guardrails, observability hardening

**Build:** per Module 7 and Module 6, Section 5. RLS policies in Postgres,
Presidio scrubbing, structured logging + tracing across all services,
Prometheus metrics.

**Definition of done:** the prompt-injection and PII test cases from
Module 8, Section 4 pass. A trace for a single chat request is visible
end-to-end across gateway → orchestrator → retrieval → LLM router in the
tracing UI.

---

## Stage 11 — Evaluation & load testing

**Build:** per Module 8. RAGAS test set per tenant, load test scripts for
bulk ingestion and concurrent chat.

**Definition of done:** a faithfulness score is produced for at least one
real tenant's document set, and a documented baseline number exists before
any client-facing demo.

---

## Stage 12 — Production infrastructure

**Build:** per Module 6. Kubernetes manifests, CI/CD pipelines per
service, staging and production environments.

**Definition of done:** a merge to `main` for any single service triggers
that service's pipeline only, deploys to staging automatically, and
production requires manual approval.

---

## Notes for the coding agent specifically

- Treat each stage's "Definition of done" as an acceptance test to run
  before moving on — if it doesn't pass, fix the current stage rather than
  patching it around from a later stage.
- Do not introduce a tenant-specific `if` branch anywhere in service code
  (e.g. `if tenant == "healthcare": ...`). Anything domain-specific belongs
  in `prompt_configs` or `guardrail_policies` data, per Module 1, Section 6.
  If a task seems to require a code branch per tenant, stop and flag it —
  that's a sign the config schema is missing a field, not a reason to add
  a branch.
- Reuse `ai-core` and `shared-libs` rather than reimplementing logic inside
  an individual service — if the same parsing/chunking/embedding/schema
  code appears to be needed in two services, it belongs in one of these
  shared packages instead.
