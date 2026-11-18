"""Document-domain Pydantic models (owned by ingestion-service)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class DocType(StrEnum):
    PROJECT = "project"
    EMPLOYEE = "employee"
    POLICY = "policy"
    OTHER = "other"


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETED = "deleted"


class Document(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    filename: str
    doc_type: DocType
    status: DocumentStatus
    uploaded_by: uuid.UUID | None = None
    storage_key: str
    content_type: str | None = None
    byte_size: int | None = None
    chunk_count: int | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(BaseModel):
    """Returned immediately after upload is accepted."""

    document: Document
    message: str = "Upload accepted; indexing queued."


class TransientParseResponse(BaseModel):
    """Synchronous parse for User Portal tender flow — not persisted."""

    filename: str
    text_preview: Annotated[str, Field(max_length=4000)]
    page_count: int
    table_count: int
    chunk_count: int
    chunks_preview: list[str]
