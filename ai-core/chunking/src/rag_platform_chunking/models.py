"""Chunk output contract (Module 4 Layer 2)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    text: str
    chunk_index: int
    doc_id: str
    tenant_id: str
    section: str | None = None
    page: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
