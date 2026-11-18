# Operator runbook — day-to-day start/stop/audit

This covers what you need to actually run and check on the platform now that
Docling, async ingestion, real embeddings, and the faithfulness check are wired
in. For first-time machine setup, see `docs/SETUP_AND_RUN.md` instead.

## Start / stop

```powershell
cd C:\Users\gogulnath\Downloads\rag-platform
.\scripts\start_local.ps1     # starts Docker infra, all 7 API services, the
                               # ingestion worker, and both frontends
.\scripts\stop_local.ps1      # stops API services + the worker (frontends and
                               # Docker keep running)
.\scripts\stop_local.ps1 -All # also stops frontends and Docker containers
```

`start_local.ps1` is safe to re-run any time — it skips anything already
healthy and only starts what's missing.

**First upload after a fresh start is slow (10-60s)** — that's the embedding
model loading into memory once. Every upload after that is fast.

## URLs and demo logins

| What | URL |
|---|---|
| Admin portal | http://localhost:3000 |
| User portal | http://localhost:3001 |
| Gateway health | http://localhost:8000/health |

| Role | Login |
|---|---|
| Platform Super Admin | `superadmin@example.com` / `StrongPassword123!` (check "Platform Super Admin", no org) |
| Demo Corp admin | `admin@example.com` / `StrongPassword123!`, org "Demo Corp" |
| Demo Corp user | `user@example.com` / `StrongPassword123!`, org "Demo Corp" |

## Where to look when something's wrong

All logs live in `logs\local\`. One `.out.log` + `.err.log` pair per service:

| Symptom | Check this log |
|---|---|
| Upload stuck on "Pending"/"Processing" | `ingestion-worker.err.log` — the actual parse/embed error lands here, not in ingestion-service's own log |
| Document shows "Failed" | Same file, or `GET /api/v1/ingest/documents/{id}` — the `error_message` field has the exception |
| Chat gives no answer / errors | `llm-orchestrator-service.err.log` — shows which provider was tried and why each failed (`attempts` field in the response too) |
| Login/org issues | `auth-service.err.log` |
| Search returns nothing relevant | `retrieval-service.err.log`, or just call `/api/v1/retrieve/query` directly (see below) to see raw scores |
| Frontend blank/broken | `admin-portal.err.log` / `user-portal.err.log`, plus the browser's own devtools console |

Quick health check of every service at once:
```bash
for p in 8000 8001 8002 8003 8004 8005 8006; do
  curl -s -o /dev/null -w "port $p -> %{http_code}\n" http://localhost:$p/health
done
```

## Auditing a specific document's pipeline

1. **Upload status**: `GET /api/v1/ingest/documents` (admin token) — `status`
   is `pending` → `processing` → `indexed` or `failed`, with `chunk_count` and
   `error_message`.
2. **What got embedded**: query Qdrant directly to see the actual stored text
   and metadata for a tenant:
   ```python
   from qdrant_client import QdrantClient
   from qdrant_client.http import models as qm
   c = QdrantClient(host="127.0.0.1", port=6333, check_compatibility=False)
   pts, _ = c.scroll(
       collection_name="document_chunks",
       scroll_filter=qm.Filter(must=[qm.FieldCondition(key="tenant_id", match=qm.MatchValue(value="<tenant-uuid>"))]),
       limit=20, with_payload=True,
   )
   for p in pts: print(p.payload.get("text")[:120])
   ```
3. **What a query actually retrieves**: `POST /api/v1/retrieve/query` with
   `{"query": "..."}` and an end-user token — shows every candidate chunk with
   its rerank `score` and the `best_score` vs the 0.25 threshold, before any
   LLM is even called. This is the single best tool for "why didn't it find
   my document" questions.
4. **Was the final answer grounded**: every chat/generate response includes
   `metadata.grounded` (`true`/`false`) and, if `false`, `guardrails_applied`
   contains `"faithfulness_flagged"` and the answer itself gets an inline note
   naming what wasn't supported.
5. **Which Rules/Guardrails were active**: Admin portal → Rules / Guardrails
   pages show version history with timestamps — useful for "why did the model
   say that" after the fact.

## Known limits worth knowing before you demo this

- **Groq (primary LLM provider) is network-blocked** in this environment —
  every chat request currently falls through to OpenRouter automatically.
  Harmless, just slightly slower per request. If you fix Groq network access
  later, no code change is needed, it'll just start winning again.
- **Reranker score threshold (0.25) is a real tuning knob, not carved in
  stone.** Very obliquely-phrased questions can score just under it even when
  a document does answer them. If you see false "insufficient information"
  answers with real users, that's the first thing to revisit — set
  `RETRIEVAL_SCORE_THRESHOLD` in `.env` (services read it directly, no code
  change needed).
- **Not literally load-tested at 10,000 documents.** The architecture (async
  worker, batched embedding, tuned Qdrant index) is sound for that scale;
  validated with a representative mixed-format batch, not the full volume.
- **OCR needs the Tesseract binary on this machine specifically** (separate
  from the Python package) — already installed and on `start_local.ps1`'s
  PATH now. The Docker image for production already has this baked in via
  `apt-get install tesseract-ocr`, nothing to do there.
