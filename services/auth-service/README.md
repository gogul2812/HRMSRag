# Auth Service

**Technology:** FastAPI (Python 3.11+), PostgreSQL, JWT

## Purpose

The Auth Service handles all authentication and tenant/role management:

- User registration and login (username + password, delegated to Supabase Auth
  or local JWT depending on `AUTH_BACKEND` env var).
- JWT issuance: every token includes `sub` (user_id), `tenant_id`, `role`
  (`admin` | `user`), and standard `exp`/`iat` claims.
- Tenant CRUD (create, enable, disable — used by platform super-admins).
- User CRUD within a tenant (used by tenant admins).
- Token refresh and logout (token revocation via Redis deny-list).

The Gateway validates JWTs issued here on every inbound request; it calls the
Auth Service only when it cannot validate locally (i.e. for key rotation).

## Implementation module

Module 3 — `03-backend-microservices-module.md` → "auth-service"

## API (planned — Stage 1)

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Create a new user in a tenant |
| `POST` | `/auth/login` | Issue JWT |
| `POST` | `/auth/refresh` | Refresh an access token |
| `POST` | `/auth/logout` | Revoke token |
| `GET` | `/auth/me` | Whoami |
| `POST` | `/tenants` | Create tenant (super-admin only) |
| `GET` | `/tenants/{tenant_id}` | Get tenant info |

## Running locally (Stage 1+)

```bash
cd services/auth-service
cp ../../.env.example .env
python -m uvicorn app.main:app --reload --port 8001
```

## Environment variables

`POSTGRES_*`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`,
`REDIS_URL`, `AUTH_BACKEND`
