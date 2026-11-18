"""Stage 4 DoD tests for ingestion-service."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest
from qdrant_client.http import models as qm

from app.infrastructure import qdrant_store
from rag_platform_schemas.auth import UserRole
from tests.conftest import make_token


async def _wait_indexed(client, headers, doc_id: str, timeout_s: float = 20.0) -> dict:
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        res = await client.get(f"/api/v1/ingest/documents/{doc_id}", headers=headers)
        assert res.status_code == 200
        last = res.json()
        if last["status"] in ("indexed", "failed"):
            return last
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for index; last={last}")


@pytest.mark.asyncio
async def test_health(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["service"] == "ingestion-service"


@pytest.mark.asyncio
async def test_upload_three_samples_indexed_in_qdrant(
    client, admin_headers, tenant_id, samples_dir: Path
):
    import sys

    ai_core = samples_dir.parent
    if str(ai_core) not in sys.path:
        sys.path.insert(0, str(ai_core))
    from samples.generate_samples import write_pdf, write_scanned_png

    write_pdf()
    write_scanned_png()

    files = [
        (samples_dir / "sample_project.md", "project"),
        (samples_dir / "sample_table.pdf", "project"),
        (samples_dir / "sample_scanned.png", "employee"),
    ]

    for path, doc_type in files:
        assert path.is_file(), path
        with path.open("rb") as fh:
            res = await client.post(
                "/api/v1/ingest/upload",
                headers=admin_headers,
                files={"file": (path.name, fh, "application/octet-stream")},
                data={"doc_type": doc_type},
            )
        assert res.status_code == 202, res.text
        doc = res.json()["document"]
        assert doc["status"] == "pending"
        doc_id = doc["id"]

        final = await _wait_indexed(client, admin_headers, doc_id)
        assert final["status"] == "indexed", final.get("error_message")
        assert final["chunk_count"] and final["chunk_count"] > 0

        count = qdrant_store.count_points_for_doc(
            tenant_id=str(tenant_id), doc_id=doc_id
        )
        assert count == final["chunk_count"]


@pytest.mark.asyncio
async def test_qdrant_payload_tags(client, admin_headers, tenant_id, samples_dir: Path):
    path = samples_dir / "sample_project.md"
    with path.open("rb") as fh:
        res = await client.post(
            "/api/v1/ingest/upload",
            headers=admin_headers,
            files={"file": (path.name, fh, "text/markdown")},
            data={"doc_type": "project"},
        )
    doc_id = res.json()["document"]["id"]
    final = await _wait_indexed(client, admin_headers, doc_id)
    assert final["status"] == "indexed"

    q = qdrant_store.get_qdrant_client()
    points, _ = q.scroll(
        collection_name=qdrant_store.settings.qdrant_collection,
        scroll_filter=qm.Filter(
            must=[
                qm.FieldCondition(
                    key="tenant_id", match=qm.MatchValue(value=str(tenant_id))
                ),
                qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id)),
            ]
        ),
        limit=5,
        with_payload=True,
    )
    assert points
    for p in points:
        assert p.payload["tenant_id"] == str(tenant_id)
        assert p.payload["doc_id"] == doc_id
        assert p.payload["doc_type"] == "project"
        assert "chunk_index" in p.payload


@pytest.mark.asyncio
async def test_corrupt_or_empty_file_becomes_failed(client, admin_headers):
    res = await client.post(
        "/api/v1/ingest/upload",
        headers=admin_headers,
        files={"file": ("empty.md", b"   \n\t  ", "text/markdown")},
        data={"doc_type": "project"},
    )
    assert res.status_code == 202
    doc_id = res.json()["document"]["id"]
    final = await _wait_indexed(client, admin_headers, doc_id)
    assert final["status"] == "failed"
    assert final["error_message"]
    assert len(final["error_message"]) > 0


@pytest.mark.asyncio
async def test_end_user_cannot_upload(client, end_user_headers, samples_dir: Path):
    path = samples_dir / "sample_project.md"
    with path.open("rb") as fh:
        res = await client.post(
            "/api/v1/ingest/upload",
            headers=end_user_headers,
            files={"file": (path.name, fh, "text/markdown")},
            data={"doc_type": "project"},
        )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_tenant_isolation(client, tenant_id, samples_dir: Path):
    other_tenant = uuid.uuid4()
    headers_a = {
        "Authorization": f"Bearer {make_token(role=UserRole.ADMIN, tenant_id=tenant_id)}"
    }
    headers_b = {
        "Authorization": f"Bearer {make_token(role=UserRole.ADMIN, tenant_id=other_tenant)}"
    }

    path = samples_dir / "sample_project.md"
    with path.open("rb") as fh:
        res = await client.post(
            "/api/v1/ingest/upload",
            headers=headers_a,
            files={"file": (path.name, fh, "text/markdown")},
            data={"doc_type": "project"},
        )
    doc_id = res.json()["document"]["id"]
    await _wait_indexed(client, headers_a, doc_id)

    assert (
        await client.get(f"/api/v1/ingest/documents/{doc_id}", headers=headers_b)
    ).status_code == 404
    listed = await client.get("/api/v1/ingest/documents", headers=headers_b)
    assert listed.status_code == 200
    assert listed.json() == []
