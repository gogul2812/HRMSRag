# Retrieval Service

**Technology:** FastAPI, Qdrant, BGE embedding + bge-reranker-v2-m3

## Purpose

Tenant-scoped hybrid retrieval:

1. Embed query (`ai-core/embedding`)
2. Dense search + lexical/BM25-style fusion against Qdrant (`tenant_id` filter mandatory)
3. Rerank top candidates (`ai-core/reranking`) → top-k
4. Threshold cutoff → `insufficient_information` when best score is too low

## API

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/retrieve/query` | end_user / admin | Hybrid retrieve + rerank |

OpenAPI: http://localhost:8004/docs

## Run

```bash
cd services/retrieval-service
pip install -e ../../ai-core/embedding -e ../../ai-core/reranking
pip install -e ../../shared-libs/schemas -e ../../shared-libs/auth-middleware -e ../../shared-libs/observability
pip install -e ".[test]"
uvicorn app.main:app --reload --port 8004
```

## Env

`JWT_SECRET_KEY`, `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_COLLECTION`,
`EMBEDDING_MODEL_NAME`, `RERANKER_MODEL_NAME`, `RETRIEVAL_SCORE_THRESHOLD`

Use `fake` for both models in offline tests.

## Tests

```bash
EMBEDDING_MODEL_NAME=fake RERANKER_MODEL_NAME=fake pytest tests/ -v
```
