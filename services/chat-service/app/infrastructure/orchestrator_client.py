"""HTTP client for llm-orchestrator-service."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings


async def orchestrate_generate(
    *,
    query: str,
    token: str,
    chat_history: list[dict[str, str]] | None = None,
    doc_type: str | None = None,
) -> dict[str, Any]:
    if settings.chat_fake_orchestrator:
        return {
            "answer": f"[fake] Grounded answer about: {query[:80]}",
            "citations": [
                {
                    "doc_id": "00000000-0000-0000-0000-000000000001",
                    "chunk_index": 0,
                    "section": "Overview",
                    "page": 1,
                    "score": 0.9,
                    "excerpt": "Project Phoenix uses FastAPI.",
                }
            ],
            "provider": "fake-primary",
            "model": "fake-model",
            "forced_local": False,
            "insufficient_information": False,
            "attempts": ["fake-primary:ok"],
            "guardrails_applied": [],
            "metadata": {},
        }

    url = f"{settings.llm_orchestrator_service_url.rstrip('/')}/api/v1/orchestrate/generate"
    payload: dict[str, Any] = {
        "query": query,
        "chat_history": chat_history or [],
    }
    if doc_type:
        payload["doc_type"] = doc_type

    async with httpx.AsyncClient(timeout=120.0) as client:
        res = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        res.raise_for_status()
        return res.json()


async def orchestrate_stream(
    *,
    query: str,
    token: str,
    chat_history: list[dict[str, str]] | None = None,
    doc_type: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """
    Yields SSE-like dicts: {"event": "token"|"final", "data": ...}.
    Fake mode emits multiple small token chunks for DoD.
    """
    if settings.chat_fake_orchestrator:
        answer = f"[fake] Streamed grounded answer about: {query[:80]}"
        # Multiple incremental chunks (not one dump)
        step = max(8, len(answer) // 6)
        parts: list[str] = []
        for i in range(0, len(answer), step):
            chunk = answer[i : i + step]
            parts.append(chunk)
            yield {"event": "token", "data": {"token": chunk}}
        final = {
            "answer": "".join(parts),
            "citations": [
                {
                    "doc_id": "00000000-0000-0000-0000-000000000001",
                    "chunk_index": 0,
                    "section": "Overview",
                    "page": 1,
                    "score": 0.9,
                    "excerpt": "Project Phoenix uses FastAPI.",
                }
            ],
            "provider": "fake-primary",
            "model": "fake-model",
            "forced_local": False,
            "insufficient_information": False,
            "attempts": [],
            "guardrails_applied": [],
            "metadata": {},
        }
        yield {"event": "final", "data": final}
        return

    url = f"{settings.llm_orchestrator_service_url.rstrip('/')}/api/v1/orchestrate/stream"
    payload: dict[str, Any] = {
        "query": query,
        "chat_history": chat_history or [],
    }
    if doc_type:
        payload["doc_type"] = doc_type

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        ) as res:
            res.raise_for_status()
            event_name = "message"
            data_lines: list[str] = []
            async for line in res.aiter_lines():
                if line.startswith("event:"):
                    event_name = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
                elif line == "" and data_lines:
                    raw = "\n".join(data_lines)
                    data_lines = []
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        parsed = raw
                    yield {"event": event_name, "data": parsed}
                    event_name = "message"
            if data_lines:
                raw = "\n".join(data_lines)
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = raw
                yield {"event": event_name, "data": parsed}
