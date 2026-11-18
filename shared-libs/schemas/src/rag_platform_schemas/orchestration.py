"""Orchestration request/response models."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class ContextChunk(BaseModel):
    text: str
    doc_id: str
    doc_type: str | None = None
    chunk_index: int | None = None
    section: str | None = None
    page: int | None = None
    score: float | None = None


class OrchestrateRequest(BaseModel):
    query: Annotated[str, Field(min_length=1, max_length=8000)]
    # Optional pre-fetched chunks (tests / chat-service). If omitted, orchestrator
    # calls retrieval-service.
    chunks: list[ContextChunk] | None = None
    doc_type: str | None = None
    chat_history: list[dict[str, str]] = Field(default_factory=list)
    # Admin Portal rules preview — use draft text instead of active tenant prompt
    system_prompt_override: str | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class Citation(BaseModel):
    doc_id: str
    chunk_index: int | None = None
    section: str | None = None
    page: int | None = None
    score: float | None = None
    excerpt: str


class OrchestrateResponse(BaseModel):
    answer: str
    citations: list[Citation]
    provider: str
    model: str
    forced_local: bool
    attempts: list[str] = Field(default_factory=list)
    guardrails_applied: list[str] = Field(default_factory=list)
    insufficient_information: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractRequirementsRequest(BaseModel):
    """Layer 6 — tender/spec requirement extraction."""

    text: Annotated[str, Field(min_length=1, max_length=100_000)]
    filename: str | None = None


class ExtractRequirementsResponse(BaseModel):
    requirements: dict[str, Any]
    provider: str
    model: str
