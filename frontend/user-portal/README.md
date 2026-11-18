# User Portal

**Technology:** Next.js 14, TypeScript, Tailwind CSS, `@rag-platform/shared-ui`

## Purpose

End-user chat against the tenant knowledge base — streamed answers, citations,
feedback, and tender comparison (Layer 6 extract → retrieve → answer).

Calls the **API Gateway** only (`NEXT_PUBLIC_API_BASE_URL`).

## Pages (Stage 9)

| Route | Purpose |
|---|---|
| `/login` | End-user login |
| `/chat` | Streaming chat + sidebar + attach tender inline |
| `/chat/[id]` | Resume session |
| `/compare` | Dedicated tender upload → extract → compare stream |
| `/history` | List / open / soft-delete sessions |

## Running locally

```bash
# from frontend/
npm install
cp user-portal/.env.example user-portal/.env.local
npm run dev:user
# http://localhost:3001
```

Requires gateway + auth + chat + orchestrator (+ ingestion for attach/compare,
retrieval via orchestrator).

## Definition of done

1. Log in as end user → ask a question on `/chat` → streamed cited answer.
2. Upload a tender on `/compare` (or Attach in chat) → feasibility/comparison answer.
