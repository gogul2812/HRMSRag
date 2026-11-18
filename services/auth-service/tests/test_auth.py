import pytest

@pytest.mark.asyncio
async def test_health_check(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_create_tenant_and_register_user(client):
    # 1. Create tenant
    res = await client.post(
        "/api/v1/tenants", 
        json={"name": "Test Tenant", "domain": "test-domain"},
        headers={"setup-token": "test-setup"}
    )
    assert res.status_code == 201
    tenant_id = res.json()["id"]

    # 2. Register User
    res2 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@test.com",
            "password": "StrongPassword123!",
            "tenant_id": tenant_id,
            "role": "end_user"
        }
    )
    assert res2.status_code == 201
    assert res2.json()["email"] == "user@test.com"

    # 3. Login
    res3 = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "user@test.com",
            "password": "StrongPassword123!",
            "tenant_id": tenant_id
        }
    )
    assert res3.status_code == 200
    assert "access_token" in res3.json()

@pytest.mark.asyncio
async def test_public_register_forces_end_user(client):
    from sqlalchemy import select
    from app.domain.models import UserDB
    from tests.conftest import TestingSessionLocal

    # Create tenant
    res = await client.post(
        "/api/v1/tenants", 
        json={"name": "Test Tenant 2", "domain": "test-domain-2"},
        headers={"setup-token": "test-setup"}
    )
    tenant_id = res.json()["id"]

    # Register User attempting to be admin
    res2 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "hacker@test.com",
            "password": "StrongPassword123!",
            "tenant_id": tenant_id,
            "role": "admin"
        }
    )
    assert res2.status_code == 201
    assert res2.json()["role"] == "end_user"  # Must be forced to end_user

    # Prove privilege escalation was blocked in the database, not only in the response body
    async with TestingSessionLocal() as session:
        user = await session.scalar(
            select(UserDB).where(UserDB.email == "hacker@test.com")
        )
        assert user is not None
        assert user.role == "end_user"

@pytest.mark.asyncio
async def test_admin_register_requires_auth(client):
    res = await client.post(
        "/api/v1/tenants", 
        json={"name": "Test Tenant 3", "domain": "test-domain-3"},
        headers={"setup-token": "test-setup"}
    )
    tenant_id = res.json()["id"]

    # Fails without setup-token or auth
    res2 = await client.post(
        "/api/v1/auth/register-admin",
        json={
            "email": "admin@test.com",
            "password": "StrongPassword123!",
            "tenant_id": tenant_id,
            "role": "admin"
        }
    )
    assert res2.status_code == 403

    # Succeeds with setup-token
    res3 = await client.post(
        "/api/v1/auth/register-admin",
        json={
            "email": "admin@test.com",
            "password": "StrongPassword123!",
            "tenant_id": tenant_id,
            "role": "admin"
        },
        headers={"setup-token": "test-setup"}
    )
    assert res3.status_code == 201
    assert res3.json()["role"] == "admin"

@pytest.mark.asyncio
async def test_end_user_cannot_access_admin_route(client):
    res = await client.post(
        "/api/v1/tenants", 
        json={"name": "Test Tenant 4", "domain": "test-domain-4"},
        headers={"setup-token": "test-setup"}
    )
    tenant_id = res.json()["id"]
    
    # 1. Register an end user
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "user4@test.com",
            "password": "StrongPassword123!",
            "tenant_id": tenant_id
        }
    )
    
    # 2. Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "user4@test.com", "password": "StrongPassword123!", "tenant_id": tenant_id}
    )
    token = login_res.json()["access_token"]
    
    # We will test the gateway middleware in the gateway service, but let's test a local protected route here
    # We will add a temporary dummy endpoint to test the require_role logic
    from app.main import app
    from fastapi import Depends
    from rag_platform_auth_middleware import require_role
    from rag_platform_schemas.auth import UserRole
    
    @app.get("/api/v1/dummy-admin-route")
    async def dummy_admin_route(claims = Depends(require_role(UserRole.ADMIN))):
        return {"status": "ok"}
        
    res_admin = await client.get("/api/v1/dummy-admin-route", headers={"Authorization": f"Bearer {token}"})
    assert res_admin.status_code == 403
