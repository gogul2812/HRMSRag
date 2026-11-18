# Admin Portal

**Technology:** Next.js 14, TypeScript, Tailwind CSS, `@rag-platform/shared-ui`

## Purpose

Tenant admin UI for document upload, rules versioning, and guardrail config.
Calls the **API Gateway** only (`NEXT_PUBLIC_API_BASE_URL`).

## Pages (Stage 8)

| Route | Purpose |
|---|---|
| `/login` | Admin login (`auth-service` via gateway) |
| `/dashboard` | Ingestion + active config overview |
| `/documents` | Multi-file upload + live status polling |
| `/config/rules` | Draft / publish / activate prompt versions + preview |
| `/config/guardrails` | Refusal topics, disclaimer, blocked phrases |
| `/users` | Placeholder (invite flow later) |

## Running locally

```bash
# from frontend/
npm install
cp admin-portal/.env.example admin-portal/.env.local
npm run dev:admin
# http://localhost:3000
```

Requires gateway (8000) + auth (8001) + admin-config (8002) + ingestion (8003).
For rules preview, also llm-orchestrator (8005) with `LLM_ROUTER_MODE=fake` OK.

## Definition of done

1. Upload a document on `/documents` and watch status move toward `indexed`.
2. Publish a rules version on `/config/rules` and activate it — Stage 6
   orchestrator will use the active prompt on subsequent generates.
