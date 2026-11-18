import pytest

@pytest.mark.asyncio
async def test_health_check(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_stub_route_returns_501(client):
    # Pass a valid token so middleware doesn't block it
    import uuid
    from datetime import datetime, timezone
    from jose import jwt
    
    payload = {
        "sub": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "role": "admin",
        "jti": str(uuid.uuid4()),
        "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,
    }
    token = jwt.encode(payload, "test-secret-key", algorithm="HS256")
    
    # notify remains stubbed (Stage 8+); config/ingest are live proxies now
    res = await client.get("/api/v1/notify/status", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 501
    assert "Not Implemented" in res.json()["detail"]
