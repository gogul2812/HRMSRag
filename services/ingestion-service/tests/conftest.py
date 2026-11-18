"""Test fixtures for ingestion-service."""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Env BEFORE importing app / worker / settings
_TMP = tempfile.mkdtemp(prefix="ingest_test_")
_DB_PATH = Path(_TMP) / "test.db"
_STORAGE = Path(_TMP) / "storage"
_STORAGE.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_PATH.as_posix()}"
os.environ["DATABASE_URL_SYNC"] = f"sqlite:///{_DB_PATH.as_posix()}"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_PATH"] = str(_STORAGE)
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["EMBEDDING_MODEL_NAME"] = "fake"
os.environ["QDRANT_HOST"] = "localhost"
os.environ["QDRANT_PORT"] = "6333"

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt
from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.models import Base
from app.infrastructure import qdrant_store
from app.infrastructure.database import get_db_session
from app.main import app
from rag_platform_schemas.auth import UserRole

# Shared in-memory Qdrant for the whole test session
_QDRANT = QdrantClient(":memory:")
qdrant_store.ensure_collection(_QDRANT)


def _patched_client():
    return _QDRANT


qdrant_store.get_qdrant_client = _patched_client  # type: ignore[assignment]

engine = create_async_engine(
    os.environ["DATABASE_URL"],
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db_session] = override_get_db


def make_token(*, role: UserRole, tenant_id: uuid.UUID | None = None) -> str:
    tid = tenant_id or uuid.uuid4()
    now = int(datetime.now(timezone.utc).timestamp())
    return jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "tenant_id": str(tid),
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
def tenant_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def admin_headers(tenant_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(role=UserRole.ADMIN, tenant_id=tenant_id)}"}


@pytest.fixture
def end_user_headers(tenant_id: uuid.UUID) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {make_token(role=UserRole.END_USER, tenant_id=tenant_id)}"
    }


@pytest.fixture
def samples_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "ai-core" / "samples"
