"""Qdrant vector store helpers (Module 5 §3 payload tags)."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Sequence

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.config import settings

logger = logging.getLogger(__name__)

VECTOR_SIZE = 1024


def get_qdrant_client() -> QdrantClient:
    api_key = settings.qdrant_api_key
    if api_key is not None and not str(api_key).strip():
        api_key = None
    kwargs = {
        "host": settings.qdrant_host,
        "port": settings.qdrant_port,
        "api_key": api_key,
    }
    try:
        return QdrantClient(**kwargs, check_compatibility=False)
    except TypeError:
        return QdrantClient(**kwargs)


def ensure_collection(client: QdrantClient | None = None) -> None:
    client = client or get_qdrant_client()
    name = settings.qdrant_collection
    existing = {c.name for c in client.get_collections().collections}
    if name in existing:
        return
    client.create_collection(
        collection_name=name,
        vectors_config=qm.VectorParams(size=VECTOR_SIZE, distance=qm.Distance.COSINE),
    )
    for field in ("tenant_id", "doc_id", "doc_type"):
        client.create_payload_index(
            collection_name=name,
            field_name=field,
            field_schema=qm.PayloadSchemaType.KEYWORD,
        )
    logger.info("Created Qdrant collection %s", name)


def upsert_chunks(
    *,
    tenant_id: str,
    doc_id: str,
    doc_type: str,
    texts: Sequence[str],
    vectors: Sequence[Sequence[float]],
    sections: Sequence[str | None],
    pages: Sequence[int | None],
    client: QdrantClient | None = None,
) -> int:
    if len(texts) != len(vectors):
        raise ValueError("texts/vectors length mismatch")
    client = client or get_qdrant_client()
    ensure_collection(client)

    points: list[qm.PointStruct] = []
    for i, (text, vector, section, page) in enumerate(
        zip(texts, vectors, sections, pages, strict=True)
    ):
        if len(vector) != VECTOR_SIZE:
            raise ValueError(f"Expected {VECTOR_SIZE}-dim vector, got {len(vector)}")
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{i}"))
        payload: dict[str, Any] = {
            "tenant_id": tenant_id,
            "doc_id": doc_id,
            "doc_type": doc_type,
            "chunk_index": i,
            "section": section,
            "page": page,
            "text": text,
        }
        points.append(qm.PointStruct(id=point_id, vector=list(vector), payload=payload))

    if points:
        client.upsert(collection_name=settings.qdrant_collection, points=points)
    logger.info(
        "Upserted %s points for doc_id=%s tenant_id=%s",
        len(points),
        doc_id,
        tenant_id,
    )
    return len(points)


def delete_document_points(
    *, tenant_id: str, doc_id: str, client: QdrantClient | None = None
) -> None:
    client = client or get_qdrant_client()
    try:
        client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[
                        qm.FieldCondition(
                            key="tenant_id", match=qm.MatchValue(value=tenant_id)
                        ),
                        qm.FieldCondition(
                            key="doc_id", match=qm.MatchValue(value=doc_id)
                        ),
                    ]
                )
            ),
        )
    except Exception as exc:
        logger.warning("Qdrant delete failed for doc_id=%s: %s", doc_id, exc)


def count_points_for_doc(
    *, tenant_id: str, doc_id: str, client: QdrantClient | None = None
) -> int:
    client = client or get_qdrant_client()
    result = client.count(
        collection_name=settings.qdrant_collection,
        count_filter=qm.Filter(
            must=[
                qm.FieldCondition(key="tenant_id", match=qm.MatchValue(value=tenant_id)),
                qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id)),
            ]
        ),
        exact=True,
    )
    return int(result.count)
