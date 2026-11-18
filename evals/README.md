# Evaluation & Load Testing (Stage 11)

**Package:** `evals/` (`rag-platform-evals`)

## Purpose

- Per-tenant question/answer eval sets with **faithfulness**, answer relevancy,
  and context precision (offline heuristic; optional live API / RAGAS later).
- Load scripts for bulk ingestion, concurrent chat, and LLM fallback under stress.

## Quick start (offline — no services required)

```bash
cd evals
pip install -e ".[test]"
pytest -q
python -m rag_platform_evals.cli --dataset sample_healthcare.json
# writes evals/results/sample-healthcare-offline.json
```

## Live eval (gateway + orchestrator up)

```bash
set EVAL_API_BASE_URL=http://localhost:8000
set EVAL_JWT=<end_user_or_admin_jwt>
python -m rag_platform_evals.cli --dataset sample_healthcare.json --live
```

## Load tests

```bash
# Concurrent fake-router primary failure → secondary (no network)
pip install -e ../ai-core/llm_router
python -m rag_platform_evals.load.cli fallback --rounds 20

# Bulk ingest (needs running stack + admin JWT)
python -m rag_platform_evals.load.cli ingest --dir ../ai-core/samples --token %EVAL_JWT% --limit 100

# Concurrent chat
python -m rag_platform_evals.load.cli chat --token %EVAL_JWT% --concurrency 10
```

## Baseline

See [`BASELINE.md`](./BASELINE.md) — update after each demo-ready eval run.
