"""Retrieval-domain Pydantic models."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class RetrieveRequest(BaseModel):
    query: Annotated[str, Field(min_length=1, max_length=4000)]
    doc_type: str | None = None
    top_k: Annotated[int, Field(default=5, ge=1, le=20)] = 5
    candidate_limit: Annotated[int, Field(default=20, ge=5, le=50)] = 20

    model_config = ConfigDict(str_strip_whitespace=True)


class RetrievedChunk(BaseModel):
    text: str
    score: float
    doc_id: str
    doc_type: str | None = None
    chunk_index: int | None = None
    section: str | None = None
    page: int | None = None
    tenant_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class RetrieveResponse(BaseModel):
    query: str
    tenant_id: str
    chunks: list[RetrievedChunk]
    insufficient_information: bool = False
    best_score: float | None = None
    message: str | None = None
