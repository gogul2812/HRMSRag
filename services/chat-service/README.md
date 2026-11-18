# Chat Service

**Technology:** FastAPI (Python 3.11+), PostgreSQL, Server-Sent Events (SSE)

## Purpose

The Chat Service owns the conversational layer:

- **Session management** — creates and stores chat sessions per user + tenant.
- **Message persistence** — every user message and assistant reply is stored in
  Postgres with timestamps and source citations. All rows carry `tenant_id`.
- **SSE endpoint** — the User Portal connects to
  `POST /api/v1/chat/sessions/{session_id}/stream`. The Chat Service calls
  `llm-orchestrator-service` and proxies its token stream as SSE events.
- **History endpoint** — returns full message history for a given session,
  including citations.
- **Feedback** — thumbs up/down on assistant messages.

The Chat Service does **not** perform retrieval or LLM calls itself — it
orchestrates by calling `llm-orchestrator-service` (which calls retrieval).

## Implementation module

Module 3 — `03-backend-microservices-module.md` → "chat-service"
Module 9 — Stage 7

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/chat/sessions` | Start a new chat session |
| `GET` | `/api/v1/chat/sessions` | List sessions for the caller |
| `GET` | `/api/v1/chat/sessions/{session_id}` | Session + full message history |
| `POST` | `/api/v1/chat/sessions/{session_id}/message` | Send message (non-streaming) |
| `POST` | `/api/v1/chat/sessions/{session_id}/stream` | Send message; stream answer via SSE |
| `DELETE` | `/api/v1/chat/sessions/{session_id}` | Soft-delete a session |
| `POST` | `/api/v1/chat/messages/{message_id}/feedback` | Thumbs up/down |
| `GET` | `/health` | Liveness |

## Running locally

```bash
cd services/chat-service
# apply migration 0004 first
export CHAT_FAKE_ORCHESTRATOR=1   # offline / without orchestrator
python -m uvicorn app.main:app --reload --port 8006
```

## Tests

```bash
export CHAT_FAKE_ORCHESTRATOR=1
pytest -q
```

## Environment variables

`DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`,
`LLM_ORCHESTRATOR_SERVICE_URL`, `CHAT_FAKE_ORCHESTRATOR`
