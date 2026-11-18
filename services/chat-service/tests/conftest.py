"""Fixtures for chat-service tests."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["CHAT_FAKE_ORCHESTRATOR"] = "1"
os.environ["LLM_ORCHESTRATOR_SERVICE_URL"] = "http://localhost:8005"

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.domain.models import Base
from app.infrastructure import database as db_mod
from app.infrastructure.database import get_db_session
from app.main import app
from rag_platform_schemas.auth import UserRole

# Shared in-memory SQLite so request session + stream session see the same data
engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False
)

# Point production session maker at the shared test engine (SSE persist path)
db_mod.engine = engine
db_mod.async_session_maker = TestingSessionLocal


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db_session] = override_get_db

TENANT_A = uuid.uuid4()
USER_A = uuid.uuid4()
USER_B = uuid.uuid4()
TENANT_B = uuid.uuid4()


def make_token(
    *,
    role: UserRole,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> str:
    uid = user_id or uuid.uuid4()
    now = int(datetime.now(timezone.utc).timestamp())
    return jwt.encode(
        {
            "sub": str(uid),
            "tenant_id": str(tenant_id),
            "role": role.value,
            "jti": str(uuid.uuid4()),
            "exp": now + 3600,
            "iat": now,
            "type": "access",
        },
        "test-secret-key",
        algorithm="HS256",
    )


@pytest.fixture(autouse=True)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def user_a_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {make_token(role=UserRole.END_USER, tenant_id=TENANT_A, user_id=USER_A)}"
    }


@pytest.fixture
def user_b_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {make_token(role=UserRole.END_USER, tenant_id=TENANT_B, user_id=USER_B)}"
    }
