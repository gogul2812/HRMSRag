# Module 4 — AI Pipeline (`ai-core`)

> Depends on: Module 1 (stack decisions). Used by: `ingestion-service`,
> `retrieval-service`, `llm-orchestrator-service` (Module 3).

This module is a shared library, not a standalone service — every stage
below is a Python package under `ai-core/`, imported by whichever
microservice needs it, so the logic is written once.

## Layer 1 — Parsing (`ai-core/parsing`)

- **Tool**: Docling (primary), Tesseract OCR (fallback for scanned/image
  files).
- **Why**: Docling runs fully local, no API dependency, and extracts tables
  as real structured objects rather than flattened text — critical since a
  flattened table is one of the biggest sources of hallucinated figures.
  Tesseract handles the scanned intake forms that inevitably show up
  alongside clean digital files.
- **Interface**: `parse(file_bytes, filename) -> ParsedDocument` (text,
  tables, images with layout metadata).

## Layer 2 — Chunking (`ai-core/chunking`)

- **Tool**: LlamaIndex's recursive / header-aware text splitter.
- **Why**: ~300–500 tokens per chunk, ~15% overlap, and — the single most
  important rule — a table is never split mid-row. Markdown files (common
  in this platform's project/resource documents) are split along their own
  header structure so a chunk stays a coherent section, not an arbitrary
  slice.
- **Interface**: `chunk(parsed_document) -> list[Chunk]`, each chunk
  carrying `doc_id`, `tenant_id`, `section`, `page`.

## Layer 3 — Embedding (`ai-core/embedding`)

- **Model**: BGE-large-en-v1.5 (BAAI), served locally via
  `sentence-transformers`.
- **Why**: top-tier open-model retrieval accuracy, zero ongoing cost, and —
  critically for a platform holding HR/employee data — nothing is ever sent
  to a third-party API to be embedded. The same model version embeds both
  the stored corpus and every incoming query, indefinitely; this
  consistency is the actual requirement, not the raw model quality.
- **Interface**: `embed(text: str) -> vector[1024]`.

## Layer 4 — Storage (`ai-core` writes, via `ingestion-service`)

- **Database**: Qdrant, self-hosted.
- **Schema**: every point payload carries `tenant_id`, `doc_id`,
  `doc_type` (e.g. `project`, `employee`, `policy`), `section`, `page`.
- **Why Qdrant over Pinecone/FAISS/Chroma**: no vector-count ceiling as
  every tenant's corpus grows independently; native hybrid (dense + BM25)
  search, which matters because tech-stack/skill matching is often an exact
  keyword hit, not a semantic one; built-in metadata filtering is what
  makes hard tenant isolation possible at the query level, not just at the
  application layer.

## Layer 5 — Retrieval + Reranking (`ai-core/reranking`, called by
`retrieval-service`)

- **Search**: hybrid dense + BM25 against Qdrant, filtered by `tenant_id`
  (and `doc_type` when the caller knows it, e.g. only searching `employee`
  documents for a staffing question).
- **Rerank**: bge-reranker-v2-m3, narrowing the top-20 candidates to the
  top-5 that actually reach the LLM.
- **Threshold cutoff**: if the best-scoring chunk after reranking falls
  below a confidence threshold, the pipeline returns an explicit
  "insufficient information" result rather than forcing a guess — this is
  enforced here, not left to the LLM's discretion.

## Layer 6 — Requirement extraction (transient path, User Portal upload)

- When a user uploads a tender/spec document instead of asking a question
  directly, it's parsed with Layer 1's same tools, then a single LLM call
  (via Layer 7's router) extracts a structured JSON summary — required
  skills, tech stack, domain, timeline — rather than treating the whole
  document as free text. That JSON, not the raw document, becomes the query
  into Layer 5.

## Layer 7 — LLM Router (`ai-core/llm_router`)

- **Tool**: litellm, configured with a priority-ordered fallback chain:
  Groq (primary, fastest free tier) → Google Gemini (secondary) →
  OpenRouter free models (tertiary) → local Ollama (Llama 3.3 70B or
  Qwen2.5 72B — final fallback, never rate-limited or deprecated by any
  vendor).
- **Sensitivity routing rule**: before this chain is used at all, the
  orchestrator checks whether the retrieved context includes any
  `doc_type: employee` chunks. If so, the request is forced to the local
  Ollama model only — no cloud fallback attempt — since that call reasons
  directly over named individuals' records. This rule lives in the
  orchestrator, not buried in the router config, so it's auditable on its
  own.
- **Why a router instead of one model**: resilience to any single
  provider's rate limits, outages, or model deprecation is architectural,
  not a matter of picking a model expected to last forever.

## Layer 8 — Guardrails (applied around, not inside, the router call)

- The tenant's declarative policy (refusal topics, blocked phrases, required
  disclaimer) is applied to the LLM's answer *after* generation, not to the
  outgoing prompt — see `apply_guardrails()` in
  `llm-orchestrator-service/app/application/prompting.py`. It forces a
  refusal string if a refuse-topic is matched in the query or answer,
  regex-redacts blocked phrases, and appends the disclaimer if missing.
- Microsoft Presidio scrubs/masks PII in anything that is logged or that
  travels to a cloud LLM tier, as a second layer beneath the sensitivity
  routing rule above — not a replacement for it.

## Data flow summary through this module

```
raw file → [Layer 1: parse] → [Layer 2: chunk] → [Layer 3: embed]
         → [Layer 4: store in Qdrant, tagged]

user query → [Layer 5: hybrid search + rerank, tenant-scoped]
           → (if tender upload) [Layer 6: extract requirements first]
           → [Layer 7: sensitivity-routed LLM call, guardrails applied
              per Layer 8] → streamed, cited answer
```
