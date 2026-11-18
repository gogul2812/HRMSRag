import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from rag_platform_schemas.auth import (
    JWTClaims,
    RegisterRequest,
    TenantCreate,
    UserRole,
)


def test_tenant_create_valid():
    t = TenantCreate(name="Acme Corp", domain="acme-corp")
    assert t.name == "Acme Corp"
    assert t.domain == "acme-corp"


def test_tenant_create_invalid_domain():
    with pytest.raises(ValidationError):
        TenantCreate(name="Acme Corp", domain="Acme Corp!")  # invalid chars


def test_register_request_valid():
    r = RegisterRequest(
        email="test@example.com",
        password="SuperSecretPassword123!",
        tenant_id=uuid.uuid4(),
    )
    assert r.email == "test@example.com"
    assert r.role == UserRole.END_USER


def test_register_request_weak_password():
    with pytest.raises(ValidationError) as exc:
        RegisterRequest(
            email="test@example.com",
            password="password1",
            tenant_id=uuid.uuid4(),
        )
    assert "Password is too common" in str(exc.value)


def test_jwt_claims_valid():
    c = JWTClaims(
        sub=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        role=UserRole.ADMIN,
        jti=str(uuid.uuid4()),
        exp=int(datetime.now(timezone.utc).timestamp()) + 3600,
        iat=int(datetime.now(timezone.utc).timestamp()),
    )
    assert c.type == "access"
