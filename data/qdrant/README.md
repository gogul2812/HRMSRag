# data/qdrant

**Technology:** Qdrant v1.9+

## Purpose

This directory contains collection schema definitions and initialisation
scripts for the Qdrant vector database.

### Design

One Qdrant collection is used for the entire platform: `document_chunks`.
Tenant isolation is enforced via **payload filtering** on `tenant_id` — every
vector point carries a `payload` with at minimum:

```json
{
  "tenant_id": "uuid",
  "doc_id": "uuid",
  "doc_type": "project_doc | employee | policy | ...",
  "chunk_index": 0,
  "source_page": 1,
  "heading_path": "Section > Subsection"
}
```

All queries to Qdrant include a `must` filter on `tenant_id`. A query from
Tenant A cannot return vectors belonging to Tenant B.

### Why one collection?

- Simpler operations — one index to back up, monitor, and optimise.
- Payload filtering in Qdrant is efficient (uses an index on the filter field).
- Onboarding a new tenant requires zero Qdrant administrative changes.

A per-tenant collection approach is supported by Qdrant but rejected here
because it would require administrative action every time a new tenant is added,
violating the "no new deployment, no new code" onboarding requirement.

### Directory structure (planned — Stage 4+)

```
qdrant/
├── README.md
├── config/
│   └── config.yaml          # Qdrant server config (mounted into container)
└── schemas/
    └── document_chunks.py   # Collection creation script (run once at bootstrap)
```

### Initialising the collection

```bash
# After `make up`:
python data/qdrant/schemas/document_chunks.py
```
