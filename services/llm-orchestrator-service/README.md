# LLM Orchestrator Service

**Technology:** FastAPI (Python 3.11+), litellm (`ai-core/llm_router`), declarative guardrails

## Purpose

The LLM Orchestrator Service is responsible for:

1. **Prompt assembly** — combines the tenant's active system prompt (from
   `admin-config-service`) with the user's question and the retrieved chunks
   (from `retrieval-service`) into a structured prompt.
2. **Sensitivity routing** — if retrieved chunks contain documents tagged
   `doc_type: employee`, routes the request exclusively to the local Ollama
   model (data never leaves the network).
3. **LLM fallback chain** — uses `ai-core/llm_router` (litellm) with a
   configurable fallback: Groq → Gemini → OpenRouter → local Ollama. If the
   primary provider fails, the next one is tried transparently.
4. **Guardrail application** — applies the tenant's active guardrail policy
   (loaded from `admin-config-service`) to the response before returning it,
   and scrubs PII in logs (Presidio stand-in).
5. **Streaming** — streams LLM output tokens back to the caller via
   server-sent events (SSE).
6. **Requirement extraction (Layer 6)** — extracts structured JSON from
   tender/spec text for downstream retrieval.

## Implementation module

Module 3 — `03-backend-microservices-module.md` → "llm-orchestrator-service"
Module 4 — `04-ai-pipeline-module.md` → Layers 6–8
Module 9 — Stage 6

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/orchestrate/generate` | Assemble prompt, call LLM, apply guardrails, return answer + citations |
| `POST` | `/api/v1/orchestrate/stream` | Same as above, streamed via SSE |
| `POST` | `/api/v1/orchestrate/extract-requirements` | Layer 6 structured extraction |
| `GET` | `/health` | Liveness |

Request body may include optional `chunks` (skips the retrieval-service call —
useful for tests and for `chat-service` later).

## Running locally

```bash
cd services/llm-orchestrator-service
# from repo root for editable deps:
pip install -e ../../shared-libs/schemas -e ../../shared-libs/auth-middleware \
  -e ../../shared-libs/observability -e ../../ai-core/llm_router
pip install -e ".[test]"
set LLM_ROUTER_MODE=fake
set JWT_SECRET_KEY=...
python -m uvicorn app.main:app --reload --port 8005
```

## Tests

```bash
set LLM_ROUTER_MODE=fake
pytest -q
```

## Environment variables

`JWT_SECRET_KEY`, `LLM_ROUTER_MODE` (`fake` | `litellm`),
`GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`,
`OLLAMA_BASE_URL`, `OLLAMA_MODEL`,
`ADMIN_CONFIG_SERVICE_URL`, `RETRIEVAL_SERVICE_URL`,
`LLM_FAKE_FAIL_PRIMARY` / `LLM_FORCE_PRIMARY_FAIL` (DoD fallback tests)
