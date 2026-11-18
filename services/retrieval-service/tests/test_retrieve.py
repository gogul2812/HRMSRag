"""Stage 5 DoD tests for retrieval-service."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["service"] == "retrieval-service"


@pytest.mark.asyncio
async def test_relevant_query_returns_phoenix_chunk(client, tenant_a_headers):
    res = await client.post(
        "/api/v1/retrieve/query",
        headers=tenant_a_headers,
        json={"query": "What tech stack does Project Phoenix use for EHR migration?"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["insufficient_information"] is False
    assert body["chunks"]
    top = body["chunks"][0]
    assert "Phoenix" in top["text"] or "FastAPI" in top["text"] or "Qdrant" in top["text"]
    assert top["tenant_id"]
    assert top["doc_id"]
    assert body["best_score"] is not None
    assert body["best_score"] >= 0.25


@pytest.mark.asyncio
async def test_other_tenant_sees_nothing(client, tenant_b_headers):
    res = await client.post(
        "/api/v1/retrieve/query",
        headers=tenant_b_headers,
        json={"query": "What tech stack does Project Phoenix use for EHR migration?"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["chunks"] == []
    assert body["insufficient_information"] is True


@pytest.mark.asyncio
async def test_irrelevant_query_triggers_threshold(client, tenant_a_headers):
    res = await client.post(
        "/api/v1/retrieve/query",
        headers=tenant_a_headers,
        json={
            "query": "zzzz quantum underwater basket weaving regulations xyzzy",
        },
    )
    assert res.status_code == 200
    body = res.json()
    # Either no candidates or best score below threshold → insufficient
    assert body["insufficient_information"] is True
    assert body["chunks"] == []


@pytest.mark.asyncio
async def test_missing_token_rejected(client):
    res = await client.post(
        "/api/v1/retrieve/query",
        json={"query": "Project Phoenix"},
    )
    assert res.status_code in (401, 403)
