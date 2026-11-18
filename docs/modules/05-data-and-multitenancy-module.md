# Module 5 — Data Model & Multi-Tenancy

> Depends on: Module 1 (principle). Used by: every service in Module 3.

## 1. Postgres schema

| Table | Owner service | Key columns |
|---|---|---|
| `tenants` | auth-service | `id`, `name`, `domain` (e.g. "Healthcare", "Retail"), `theme_config` |
| `users` | auth-service | `id`, `tenant_id`, `role` (`admin` \| `end_user`), `email` |
| `documents` | ingestion-service | `id`, `tenant_id`, `filename`, `doc_type`, `status`, `uploaded_by` |
| `prompt_configs` | admin-config-service | `id`, `tenant_id`, `version`, `text`, `is_active` |
| `guardrail_policies` | admin-config-service | `id`, `tenant_id`, `policy_json`, `is_active` |
| `chat_sessions` | chat-service | `id`, `tenant_id`, `user_id`, `created_at` |
| `chat_messages` | chat-service | `id`, `session_id`, `role`, `content`, `citations_json` |
| `feedback` | chat-service | `id`, `message_id`, `rating` |

Every table without exception carries `tenant_id`, including ones that will
only ever have one tenant's data in the near term. This is non-negotiable —
retrofitting tenant isolation onto a table later is a migration that
touches every query that ever read it.

## 2. Tenant isolation strategy (Postgres)

Two viable approaches — pick one and apply it consistently:

- **Row-level security (RLS)**: Postgres policies that filter every query
  by `tenant_id` automatically based on the connection's session variable,
  set by the service on every request. Recommended for this platform —
  isolation is enforced by the database itself, not just application code,
  so a bug in one service can't leak another tenant's rows.
- **Schema-per-tenant**: a separate Postgres schema per tenant. Stronger
  isolation, more operational overhead (migrations must run per schema).
  Consider this only if a specific tenant (e.g. a healthcare client with a
  strict compliance requirement) needs physically separated storage.

Start with RLS; it's the lower-overhead option and satisfies the isolation
requirement for the vast majority of tenants.

## 3. Vector DB (Qdrant) tagging strategy

Every point payload:

```json
{
  "tenant_id": "healthcare-01",
  "doc_id": "proj-0417",
  "doc_type": "project",
  "section": "Tech Stack",
  "page": 3
}
```

- Every retrieval query filters on `tenant_id` as a mandatory condition —
  never optional, never inferred from the query text.
- `doc_type` lets a query scope itself further (e.g. only `employee`
  documents for a staffing question, only `project` documents for a
  feasibility question).
- For a tenant with an especially strict isolation requirement, use a
  **separate Qdrant collection per tenant** instead of a shared collection
  with a tenant filter — more operational overhead, but physically
  separates the data. Same tagging scheme applies within each collection.

## 4. Object storage layout

```
s3://rag-platform-docs/
  ├── healthcare-01/
  │   ├── projects/
  │   └── employees/
  ├── retail-02/
  │   ├── projects/
  │   └── employees/
  └── <tenant_id>/...
```

Tenant ID as the top-level prefix, mirrored from the database structure —
this makes a full data-export or data-deletion request for one tenant a
single prefix operation, which matters for any compliance conversation.

## 5. Caching

- The active `prompt_configs` and `guardrail_policies` row per tenant is
  cached in Redis (keyed by `tenant_id`), invalidated on update — this is
  read on every single chat request by `llm-orchestrator-service`, so it
  must not hit Postgres each time.
