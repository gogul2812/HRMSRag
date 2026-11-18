# shared-libs/auth-middleware

**Technology:** FastAPI, Python-JOSE / PyJWT, Python 3.11+

## Purpose

This package provides reusable FastAPI middleware and dependency functions for
JWT validation and tenant-context injection. Every microservice includes this
as a dependency — no service re-implements JWT validation on its own.

### What it provides

1. **`get_current_user` dependency** — a FastAPI `Depends()` function that:
   - Extracts the `Authorization: Bearer <token>` header.
   - Validates the JWT signature using `JWT_SECRET_KEY`.
   - Decodes claims: `sub` (user_id), `tenant_id`, `role`, `exp`.
   - Returns a `JWTClaims` object (from `shared-libs/schemas`).
   - Raises `401 Unauthorized` if the token is missing, expired, or invalid.

2. **`require_role` dependency factory** — wraps `get_current_user` and
   additionally enforces that the caller has a specific role:
   ```python
   @router.post("/upload")
   async def upload(claims: JWTClaims = Depends(require_role("admin"))):
       ...
   ```

3. **`TenantContextMiddleware`** — a Starlette middleware that sets
   `request.state.tenant_id` from validated claims, for use in lower layers.

### Why shared?

JWT validation must be identical across all services. A single package
guarantees they all use the same secret, the same algorithm, and the same
error responses. Rotating the secret or changing the algorithm is a one-line
change in one place.

## Usage

```python
from rag_platform_auth_middleware import get_current_user, require_role
from rag_platform_schemas.auth import JWTClaims
```

## Dependencies

`fastapi`, `python-jose[cryptography]`, `rag-platform-schemas`
(listed in `shared-libs/auth-middleware/pyproject.toml`)
