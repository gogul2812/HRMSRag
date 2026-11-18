# Module 2 — Frontend (Admin Portal & User Portal)

> Depends on: Module 1 (folder structure, stack). Feeds into: Module 3 (the
> API contracts these portals call).

## 1. Two separate apps, one shared library

```
frontend/
├── admin-portal/       # separate deployable Next.js app
├── user-portal/         # separate deployable Next.js app
└── shared-ui/            # npm workspace package — shared components, design tokens, API client
```

They are deployed separately (separate URLs, separate CI/CD pipelines) so
that an admin-only outage or deploy never affects end-user chat, and vice
versa. They share `shared-ui` so buttons, theming, and the API client
(fetch wrapper with auth headers, tenant context) aren't written twice.

## 2. Admin Portal — pages and responsibilities

| Page/route | Responsibility | Calls |
|---|---|---|
| `/login` | Admin authentication | `auth-service` |
| `/tenants` (super-admin only) | Create/manage tenants (Healthcare, Retail, etc.) | `admin-config-service` |
| `/documents` | Upload documents, view processing status (pending/indexed/failed), retry failed docs, delete | `ingestion-service` |
| `/rules` | Editor for the active system prompt/rules text, version history, activate a version | `admin-config-service` |
| `/guardrails` | Configure PII handling, refusal topics, required disclaimers per tenant | `admin-config-service` |
| `/analytics` | Queries per day, thumbs-down rate, unanswered-query rate, per-tenant | `chat-service` (aggregated) |
| `/users` | Invite/manage end users and their roles within the tenant | `auth-service` |

**Document upload UX detail**: drag-and-drop or bulk multi-file upload,
since a tenant may upload 100+ files at once. Each file shows a live status
chip (queued → parsing → chunking → embedding → indexed / failed) driven by
polling or a websocket connection to `notification-service`.

**Rules editor UX detail**: plain-text area with a live "preview" button
that runs a test question through the current draft rules before
publishing — this is what lets an admin sanity-check "will this actually
make the bot refuse competitor questions?" before it goes live.

## 3. User Portal — pages and responsibilities

| Page/route | Responsibility | Calls |
|---|---|---|
| `/login` | End-user authentication | `auth-service` |
| `/chat` | Main chat interface — streaming responses, citations, chat history sidebar | `chat-service` (SSE) |
| `/chat` (with attachment) | Upload a tender/spec document inline in the chat, ask "does this already exist / how do we compare" | `chat-service` → `ingestion-service` (transient parse) → `llm-orchestrator-service` |
| `/history` | Past conversations | `chat-service` |

**Chat UX detail**: standard streaming chat (token-by-token via
Server-Sent Events), each assistant message renders its citations as
clickable chips under the message (document name + page), and a
thumbs-up/thumbs-down control per message that posts to `chat-service`'s
feedback endpoint.

**File-in-chat UX detail**: an attachment button in the message composer;
once uploaded, the UI shows a "Comparing against your knowledge base…"
loading state while the requirement-extraction + matching pipeline runs
(Module 4, Layers 4–6), then renders the answer like any other message.

## 4. Cross-cutting frontend concerns

- **Auth/tenant context**: every API call from either portal includes the
  JWT (from `auth-service`), which carries `tenant_id` and `role`. Neither
  portal ever needs to pass a tenant ID manually — it's derived from the
  logged-in session.
- **Theming per tenant**: `shared-ui` exposes a theme provider driven by a
  config object (logo, colors, product name) fetched once at login, so a
  Healthcare tenant and a Retail tenant can look different without a
  separate frontend build.
- **Error states**: both portals must handle "insufficient information"
  responses (Module 4, Layer 6 threshold cutoff) as a distinct, clearly
  styled message type — not rendered identically to a normal answer.
- **Streaming client**: a small shared hook (`useChatStream`) in
  `shared-ui` wraps the SSE connection, retry-on-disconnect, and
  token-by-token rendering, used identically by both portals wherever chat
  UI is needed (the User Portal's main chat, and the Admin Portal's rules
  "preview" feature).
