"""RankedResult model for Layer 5 reranking."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RankedResult(BaseModel):
    text: str
    original_index: int
    score: float = Field(description="Higher = more relevant")
