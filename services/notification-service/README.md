# Notification Service

**Technology:** FastAPI (Python 3.11+), Redis, WebSocket / polling

## Purpose

The Notification Service provides real-time status updates to the Admin Portal:

- Listens to Redis Streams/Pub-Sub for ingestion job events published by the
  `ingestion-service` Celery worker (`pending → processing → indexed / failed`).
- Exposes a WebSocket or long-polling endpoint that the Admin Portal subscribes
  to in order to display live document ingestion progress.
- Optionally sends email notifications (e.g. "your 50-document batch has
  finished indexing") if an SMTP provider is configured.

The notification-service is **optional** in early stages — the Admin Portal
can poll `GET /ingest/documents/{doc_id}` on the Ingestion Service directly
before this service is built.

## Implementation module

Module 3 — `03-backend-microservices-module.md` → "notification-service"

## API (planned — Stage 4+)

| Method | Path | Description |
|---|---|---|
| `WS` | `/notify/ws/{tenant_id}` | WebSocket channel for live ingestion events |
| `GET` | `/notify/events/{tenant_id}` | SSE alternative to WebSocket |

## Running locally (Stage 4+)

```bash
cd services/notification-service
cp ../../.env.example .env
python -m uvicorn app.main:app --reload --port 8007
```

## Environment variables

`REDIS_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`,
`SMTP_HOST` (optional), `SMTP_PORT` (optional), `SMTP_USER` (optional),
`SMTP_PASSWORD` (optional)
