# shared-libs/schemas

**Technology:** Pydantic v2, Python 3.11+

## Purpose

This package is the **single source of truth** for all Pydantic models shared
across more than one microservice. Every service imports its request/response
types from here. No service defines its own duplicate version of a model that
exists here.

### Why centralise schemas?

- Prevents schema drift: if `Document` gains a new field, all services that
  use it get the update in one PR.
- Makes inter-service HTTP contracts explicit and type-safe.
- Makes it easy to generate OpenAPI-compatible JSON schemas from one place.

### Package contents (planned — Stage 1+)

```
schemas/
├── src/
│   └── rag_platform_schemas/
│       ├── __init__.py
│       ├── auth.py          # User, Tenant, JWTClaims, LoginRequest, TokenResponse
│       ├── documents.py     # Document, DocumentStatus, Chunk, ParsedPage, ParsedTable
│       ├── config.py        # PromptConfig, GuardrailPolicy, TenantSettings
│       ├── retrieval.py     # RetrievalRequest, RetrievedChunk, RetrievalResponse
│       ├── chat.py          # ChatSession, ChatMessage, Citation
│       └── common.py        # PaginatedResponse, ErrorResponse, HealthResponse
├── pyproject.toml
└── tests/
```

## Usage (from any service)

```python
from rag_platform_schemas.documents import Document, DocumentStatus
from rag_platform_schemas.auth import JWTClaims
```

## Dependencies

`pydantic>=2.0`
(listed in `shared-libs/schemas/pyproject.toml`)
