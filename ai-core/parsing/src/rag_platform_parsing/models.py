"""Shared parsing output contracts (Module 4 Layer 1)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    filename: str
    content_type: str | None = None
    page_count: int = 0
    extra: dict[str, Any] = Field(default_factory=dict)


class ParsedTable(BaseModel):
    """Structured table — never flattened to a single text blob before chunking."""

    page: int | None = None
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    markdown: str = ""


class ParsedPage(BaseModel):
    page_number: int
    text: str = ""


class ParsedDocument(BaseModel):
    raw_text: str
    pages: list[ParsedPage] = Field(default_factory=list)
    tables: list[ParsedTable] = Field(default_factory=list)
    metadata: DocumentMetadata
