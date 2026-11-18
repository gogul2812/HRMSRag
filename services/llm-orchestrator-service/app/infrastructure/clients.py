"""HTTP clients for admin-config and retrieval services."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


async def fetch_active_prompt(tenant_id: str, token: str) -> str | None:
    url = f"{settings.admin_config_service_url.rstrip('/')}/api/v1/config/prompt"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            if res.status_code == 200:
                return res.json().get("text")
    except Exception:
        return None
    return None


async def fetch_active_guardrails(tenant_id: str, token: str) -> dict[str, Any]:
    url = f"{settings.admin_config_service_url.rstrip('/')}/api/v1/config/guardrails"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            if res.status_code == 200:
                return res.json().get("policy_json") or {}
    except Exception:
        return {}
    return {}


async def fetch_retrieved_chunks(
    *, query: str, token: str, doc_type: str | None = None
) -> tuple[list[dict[str, Any]], bool]:
    url = f"{settings.retrieval_service_url.rstrip('/')}/api/v1/retrieve/query"
    payload: dict[str, Any] = {"query": query}
    if doc_type:
        payload["doc_type"] = doc_type
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
            if res.status_code != 200:
                return [], True
            body = res.json()
            return body.get("chunks") or [], bool(body.get("insufficient_information"))
    except Exception:
        return [], True
