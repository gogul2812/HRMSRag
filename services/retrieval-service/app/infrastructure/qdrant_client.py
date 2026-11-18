"""Qdrant client helpers for retrieval."""

from __future__ import annotations

from qdrant_client import QdrantClient

from app.config import settings


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
