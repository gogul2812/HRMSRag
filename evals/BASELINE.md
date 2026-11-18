# Evaluation baseline (Stage 11 DoD)

Documented before client-facing demos. Re-run offline eval after any
`ai-core` chunking / embedding / reranking change; a drop in
`faithfulness_mean` should block demo readiness the same way a failing
unit test would.

## Current baseline — `sample-healthcare`

| Field | Value |
|---|---|
| Dataset | `evals/datasets/sample_healthcare.json` |
| Corpus | `ai-core/samples/sample_project.md` (Project Phoenix) |
| Mode | `offline` (grounded answers from dataset contexts) |
| Generated | 2026-07-20 |
| **faithfulness_mean** | **0.8973** |
| answer_relevancy_mean | 0.3710 |
| context_precision_mean | 1.0000 |
| Cases | 5 (including 1 insufficient-information control) |

Artifact: `evals/results/sample-healthcare-offline.json`

### How this number was produced

```bash
cd evals
python -m rag_platform_evals.cli --dataset sample_healthcare.json
```

Offline mode scores answers against ground-truth contexts with a token-overlap
faithfulness metric (RAGAS-compatible shape). For a live-stack score:

```bash
set EVAL_API_BASE_URL=http://localhost:8000
set EVAL_JWT=<jwt>
python -m rag_platform_evals.cli --dataset sample_healthcare.json --live
```

## Load-test baseline notes

| Scenario | Command | Expectation |
|---|---|---|
| Primary LLM fail → fallback | `python -m rag_platform_evals.load.cli fallback --rounds 20` | 0 failures |
| Bulk ingest (100 files) | `... load.cli ingest --dir ../ai-core/samples --limit 100` | Needs running stack |
| Concurrent chat | `... load.cli chat --concurrency 10` | Needs running stack |

Update this file whenever a new offline or live report is accepted as the
demo baseline.
