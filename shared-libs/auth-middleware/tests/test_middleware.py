import os
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, Depends, Request
from fastapi.testclient import TestClient
from jose import jwt

# Set secret key BEFORE importing the middleware
os.environ["JWT_SECRET_KEY"] = "test-secret"
from rag_platform_auth_middleware.middleware import get_current_user, require_role, TenantContextMiddleware
from rag_platform_schemas.auth import JWTClaims, UserRole

app = FastAPI()
app.add_middleware(TenantContextMiddleware)

@app.get("/me")
async def read_me(claims: JWTClaims = Depends(get_current_user)):
    return {"user_id": claims.sub, "tenant_id": claims.tenant_id}

@app.get("/admin-only")
async def admin_route(claims: JWTClaims = Depends(require_role(UserRole.ADMIN))):
    return {"status": "ok"}

@app.get("/headers-check")
async def headers_check(request: Request):
    return {
        "tenant_id": getattr(request.state, "tenant_id", None),
        "user_id": getattr(request.state, "user_id", None),
        "role": getattr(request.state, "role", None),
    }

client = TestClient(app)

def make_token(role: UserRole = UserRole.END_USER, type: str = "access") -> str:
    payload = {
        "sub": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "role": role,
        "jti": str(uuid.uuid4()),
        "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "type": type,
    }
    return jwt.encode(payload, "test-secret", algorithm="HS256")

def test_get_current_user_valid():
    token = make_token()
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert "user_id" in response.json()
    assert "tenant_id" in response.json()

def test_get_current_user_missing():
    response = client.get("/me")
    assert response.status_code == 403  # HTTPBearer returns 403 if missing

def test_get_current_user_invalid_signature():
    token = make_token()
    # Break signature
    bad_token = token[:-5] + "aaaaa"
    response = client.get("/me", headers={"Authorization": f"Bearer {bad_token}"})
    assert response.status_code == 401

def test_require_role_admin_success():
    token = make_token(role=UserRole.ADMIN)
    response = client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

def test_require_role_admin_fails_for_end_user():
    token = make_token(role=UserRole.END_USER)
    response = client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403

def test_tenant_context_middleware_from_headers():
    response = client.get(
        "/headers-check", 
        headers={
            "X-Tenant-ID": "t-123", 
            "X-User-ID": "u-456",
            "X-Role": "admin"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "t-123"
    assert data["user_id"] == "u-456"
    assert data["role"] == "admin"
