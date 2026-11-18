import os
import pytest
from httpx import AsyncClient, ASGITransport
import redis.asyncio as redis

os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"

from app.main import app

@pytest.fixture
async def client():
    # Start lifespan events
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
