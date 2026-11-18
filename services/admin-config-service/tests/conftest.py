import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["JWT_ALGORITHM"] = "HS256"

import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.models import Base
from app.infrastructure.database import get_db_session
from app.main import app
from rag_platform_schemas.auth import UserRole

engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db_session] = override_get_db


def make_token(
    *,
    role: UserRole,
    tenant_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> str:
    tid = tenant_id or uuid.uuid4()
    uid = user_id or uuid.uuid4()
    payload = {
        "sub": str(uid),
        "tenant_id": str(tid),
        "role": role.value,
        "jti": str(uuid.uuid4()),
        "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, "test-secret-key", algorithm="HS256")


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
def tenant_a() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def tenant_b() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def admin_a_headers(tenant_a: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(role=UserRole.ADMIN, tenant_id=tenant_a)}"}


@pytest.fixture
def admin_b_headers(tenant_b: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(role=UserRole.ADMIN, tenant_id=tenant_b)}"}


@pytest.fixture
def end_user_a_headers(tenant_a: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(role=UserRole.END_USER, tenant_id=tenant_a)}"}
