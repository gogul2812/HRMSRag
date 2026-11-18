# Module 8 — Testing & Evaluation

> Depends on: Module 3 (services), Module 4 (AI pipeline).

## 1. Per-service testing

- **Unit tests**: every service's business logic (FastAPI route handlers,
  `ai-core` functions) covered independently — `ai-core`'s parsing,
  chunking, and embedding functions are tested with small fixture files, not
  the full 100+ document corpus.
- **Contract tests**: since services communicate over REST, each service
  publishes its API schema (FastAPI's auto-generated OpenAPI spec); a
  contract test suite verifies that `retrieval-service`'s actual response
  shape matches what `llm-orchestrator-service` expects, catching breaking
  changes before deploy.
- **Integration tests**: a docker-compose-based test environment that
  brings up real Postgres/Qdrant/Redis instances (not mocks) and runs the
  full ingestion pipeline against a handful of sample documents, then
  queries it — this is the test that actually catches "the chunker changed
  and now retrieval returns nothing sensible."

## 2. RAG-specific evaluation (RAGAS)

- A per-tenant test set of question/expected-answer pairs, built from a
  sample of that tenant's real documents.
- Metrics tracked: **faithfulness** (does the answer only say what the
  retrieved context supports), **answer relevancy**, **context precision**
  (are the retrieved chunks actually the right ones).
- Run automatically in CI whenever `ai-core`'s chunking, embedding, or
  reranking logic changes — a drop in faithfulness score on any tenant's
  test set should block a deploy, the same way a failing unit test would.
- Also run manually before every client-facing demo (per the original
  workflow in the design document), to have a concrete number to open with.

## 3. Load testing

- `ingestion-service`: simulate a 100+ file bulk upload for one tenant and
  confirm the Celery queue drains without falling behind, and that it
  doesn't starve other tenants' ingestion jobs.
- `chat-service` / `llm-orchestrator-service`: simulate concurrent chat
  sessions across multiple tenants, confirming the LLM router's fallback
  behavior actually triggers correctly under a simulated rate-limit from
  the primary provider (this is worth testing deliberately, not just
  trusting the config — force a 429 from Groq in a test and confirm Gemini
  picks up the request).

## 4. Guardrail/security testing

- Prompt-injection style test cases (a malicious tender document containing
  hidden instructions) run against the pipeline to confirm the system
  prompt/rules still hold and the model doesn't follow instructions
  embedded in retrieved content.
- A dedicated test tenant with `doc_type: employee` documents, used to
  verify the sensitivity-routing rule actually forces local-only inference
  and never silently falls through to a cloud provider.
