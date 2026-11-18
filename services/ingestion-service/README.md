# Ingestion Service

**Technology:** FastAPI, Celery, Redis, PostgreSQL, Qdrant, local/S3 object storage

## Purpose

Owns document ingestion:

1. Accept multipart upload → object storage + `documents` row (`pending`)
2. Celery worker runs `ai-core` parse → chunk → embed → Qdrant upsert
3. Updates `documents.status` to `indexed` or `failed` (with `error_message`)

## API

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/ingest/upload` | admin | Upload + queue indexing |
| `GET` | `/api/v1/ingest/documents` | admin | List tenant documents |
| `GET` | `/api/v1/ingest/documents/{id}` | admin | Status / metadata |
| `DELETE` | `/api/v1/ingest/documents/{id}` | admin | Soft-delete + drop vectors |
| `POST` | `/api/v1/ingest/transient-parse` | end_user+ | Sync parse (not persisted) |

OpenAPI: `http://localhost:8003/docs`

## Run locally

```bash
# Infra
docker compose -f docker-compose.dev.yml up -d
cd data/postgres && alembic upgrade head
python data/qdrant/schemas/document_chunks.py

# API
cd services/ingestion-service
pip install -e ../../ai-core/parsing -e ../../ai-core/chunking -e ../../ai-core/embedding
pip install -e ../../shared-libs/schemas -e ../../shared-libs/auth-middleware -e ../../shared-libs/observability
pip install -e ".[test]"
uvicorn app.main:app --reload --port 8003

# Worker (separate terminal; skip if CELERY_TASK_ALWAYS_EAGER=true)
celery -A app.worker.celery_app worker --loglevel=info
```

## Env

`DATABASE_URL`, `DATABASE_URL_SYNC`, `REDIS_URL`, `JWT_SECRET_KEY`,
`QDRANT_HOST`, `QDRANT_PORT`, `STORAGE_BACKEND` (`local`|`s3`),
`LOCAL_STORAGE_PATH`, `EMBEDDING_MODEL_NAME` (use `fake` for offline)

## Tests

```bash
cd services/ingestion-service
EMBEDDING_MODEL_NAME=fake CELERY_TASK_ALWAYS_EAGER=true pytest tests/ -v
```

## Docker

```bash
# From rag-platform/
docker build -f services/ingestion-service/Dockerfile -t rag-ingestion .
```
