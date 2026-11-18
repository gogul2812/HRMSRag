"""Fixtures for retrieval-service tests."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["EMBEDDING_MODEL_NAME"] = "fake"
os.environ["RERANKER_MODEL_NAME"] = "fake"
os.environ["RETRIEVAL_SCORE_THRESHOLD"] = "0.25"
os.environ["QDRANT_HOST"] = "localhost"
os.environ["QDRANT_PORT"] = "6333"

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.infrastructure import qdrant_client as qc_mod
from app.main import app
from rag_platform_embedding import embed_texts
from rag_platform_schemas.auth import UserRole

_QDRANT = QdrantClient(":memory:")
COLLECTION = "document_chunks"


def _init_collection() -> None:
    existing = {c.name for c in _QDRANT.get_collections().collections}
    if COLLECTION in existing:
        return
    _QDRANT.create_collection(
        collection_name=COLLECTION,
        vectors_config=qm.VectorParams(size=1024, distance=qm.Distance.COSINE),
    )


_init_collection()

# Patch the symbol used by the application layer (not only the infrastructure module).
import app.application.retrieval_service as retrieval_mod

retrieval_mod.get_qdrant_client = lambda: _QDRANT  # type: ignore[assignment]
qc_mod.get_qdrant_client = lambda: _QDRANT  # type: ignore[assignment]


TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()
DOC_A = str(uuid.uuid4())


def _seed_corpus() -> None:
    """Index a Project Phoenix-like chunk for tenant A only."""
    texts = [
        "Project Phoenix uses FastAPI, PostgreSQL 16, and Qdrant for the EHR migration staffing study.",
        "Team roster includes Ava Chen (HL7 / FHIR) and Marcus Lee (ETL / Postgres).",
        "Retail supplier matrix lists Northwind Textiles with a 14 day lead time.",
    ]
    vectors = embed_texts(texts)
    points = []
    for i, (text, vector) in enumerate(zip(texts, vectors, strict=True)):
        points.append(
            qm.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{DOC_A}:{i}")),
                vector=vector,
                payload={
                    "tenant_id": str(TENANT_A),
                    "doc_id": DOC_A,
                    "doc_type": "project",
                    "chunk_index": i,
                    "section": "Overview" if i == 0 else "Team",
                    "page": 1,
                    "text": text,
                },
            )
        )
    _QDRANT.upsert(collection_name=COLLECTION, points=points)


_seed_corpus()


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
def tenant_b_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {make_token(role=UserRole.END_USER, tenant_id=TENANT_B)}"
    }
