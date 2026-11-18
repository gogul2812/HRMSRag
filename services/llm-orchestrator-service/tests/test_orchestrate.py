"""Stage 6 DoD tests for llm-orchestrator-service."""

from __future__ import annotations

import os

import pytest


@pytest.mark.asyncio
async def test_health(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["service"] == "llm-orchestrator-service"


@pytest.mark.asyncio
async def test_grounded_cited_answer_from_chunks(client, tenant_a_headers, project_chunks):
    """DoD: grounded, cited answer using retrieved chunks (fake LLM OK)."""
    res = await client.post(
        "/api/v1/orchestrate/generate",
        headers=tenant_a_headers,
        json={
            "query": "What tech stack does Project Phoenix use?",
            "chunks": project_chunks,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["insufficient_information"] is False
    assert body["answer"]
    assert "Phoenix" in body["answer"] or "Grounded" in body["answer"] or "context" in body["answer"].lower()
    assert body["citations"]
    assert body["citations"][0]["doc_id"] == project_chunks[0]["doc_id"]
    assert body["citations"][0]["excerpt"]
    assert body["forced_local"] is False
    assert body["provider"] in {"fake-primary", "fake-secondary", "ollama", "groq"}


@pytest.mark.asyncio
async def test_primary_failure_falls_through(
    client, tenant_a_headers, project_chunks, monkeypatch
):
    """DoD: forced primary failure → router falls through to next provider."""
    monkeypatch.setenv("LLM_FAKE_FAIL_PRIMARY", "1")
    # Reload router settings path reads os.environ at call time for fail flag
    res = await client.post(
        "/api/v1/orchestrate/generate",
        headers=tenant_a_headers,
        json={
            "query": "What tech stack does Project Phoenix use?",
            "chunks": project_chunks,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["provider"] == "fake-secondary"
    assert any("forced_failure" in a for a in body["attempts"])
    assert any(a.endswith(":ok") for a in body["attempts"])


@pytest.mark.asyncio
async def test_employee_chunks_force_local_ollama(
    client, tenant_a_headers, employee_chunks
):
    """DoD: employee doc_type → local Ollama only (forced_local=True)."""
    os.environ.pop("LLM_FAKE_FAIL_PRIMARY", None)
    res = await client.post(
        "/api/v1/orchestrate/generate",
        headers=tenant_a_headers,
        json={
            "query": "Who is available for FHIR work?",
            "chunks": employee_chunks,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["forced_local"] is True
    assert body["provider"] == "ollama"
    assert body["citations"]
    assert body["citations"][0]["doc_id"] == employee_chunks[0]["doc_id"]


@pytest.mark.asyncio
async def test_empty_chunks_insufficient(client, tenant_a_headers):
    res = await client.post(
        "/api/v1/orchestrate/generate",
        headers=tenant_a_headers,
        json={"query": "Anything?", "chunks": []},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["insufficient_information"] is True
    assert body["citations"] == []
    assert body["provider"] == "none"


@pytest.mark.asyncio
async def test_guardrails_disclaimer_applied(
    client, tenant_a_headers, project_chunks, monkeypatch
):
    async def fake_guardrails(tenant_id: str, token: str):
        return {"required_disclaimer": "— Internal use only."}

    monkeypatch.setattr(
        "app.infrastructure.clients.fetch_active_guardrails", fake_guardrails
    )
    res = await client.post(
        "/api/v1/orchestrate/generate",
        headers=tenant_a_headers,
        json={
            "query": "What tech stack does Project Phoenix use?",
            "chunks": project_chunks,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "Internal use only" in body["answer"]
    assert "required_disclaimer" in body["guardrails_applied"]


@pytest.mark.asyncio
async def test_extract_requirements(client, tenant_a_headers):
    res = await client.post(
        "/api/v1/orchestrate/extract-requirements",
        headers=tenant_a_headers,
        json={
            "text": (
                "We need Python FastAPI engineers for a healthcare EHR project "
                "using Postgres and Qdrant. Timeline is Q4."
            ),
            "filename": "tender.pdf",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "python" in [s.lower() for s in body["requirements"].get("skills", [])]
    assert body["requirements"].get("domain") == "healthcare"
    assert body["requirements"].get("timeline") == "Q4"


@pytest.mark.asyncio
async def test_missing_token_rejected(client, project_chunks):
    res = await client.post(
        "/api/v1/orchestrate/generate",
        json={"query": "hi", "chunks": project_chunks},
    )
    assert res.status_code in (401, 403)
