"""Fixtures for llm-orchestrator-service tests."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["LLM_ROUTER_MODE"] = "fake"
os.environ.pop("LLM_FAKE_FAIL_PRIMARY", None)

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.main import app
from rag_platform_schemas.auth import UserRole

TENANT_A = uuid.uuid4()


def make_token(*, role: UserRole, tenant_id: uuid.UUID) -> str:
    now = int(datetime.now(timezone.utc).timestamp())
    return jwt.encode(
        {
            "sub": str(uuid.uuid4()),
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


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def tenant_a_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {make_token(role=UserRole.END_USER, tenant_id=TENANT_A)}"
    }


@pytest.fixture
def project_chunks() -> list[dict]:
    return [
        {
            "text": (
                "Project Phoenix uses FastAPI, PostgreSQL 16, and Qdrant for the "
                "EHR migration staffing study."
            ),
            "doc_id": str(uuid.uuid4()),
            "doc_type": "project",
            "chunk_index": 0,
            "section": "Overview",
            "page": 1,
            "score": 0.91,
        }
    ]


@pytest.fixture
def employee_chunks() -> list[dict]:
    return [
        {
            "text": "Ava Chen is a senior FHIR engineer available Q3 for Project Phoenix.",
            "doc_id": str(uuid.uuid4()),
            "doc_type": "employee",
            "chunk_index": 0,
            "section": "Roster",
            "page": 1,
            "score": 0.88,
        }
    ]
