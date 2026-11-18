import pytest

@pytest.mark.asyncio
async def test_auth_middleware_blocks_no_token(client):
    # /api/v1/admin/config is protected
    res = await client.get("/api/v1/admin/config")
    assert res.status_code == 401
    assert "Not authenticated" in res.json()["detail"]

@pytest.mark.asyncio
async def test_auth_middleware_allows_public_routes(client):
    res = await client.get("/health")
    assert res.status_code == 200
    
    # We can't easily test the proxy to auth-service without mocking httpx, 
    # but we can verify it doesn't return 401 locally
    # It will likely return 502 Bad Gateway since auth-service isn't running in tests
    res2 = await client.post("/api/v1/auth/login", json={})
    assert res2.status_code == 502
