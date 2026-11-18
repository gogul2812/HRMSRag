"""Ingestion application services — upload, list, delete, transient parse."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import DocumentDB
from app.infrastructure.storage import get_object_storage
from app.worker import index_document
from rag_platform_schemas.documents import DocType, DocumentStatus


ALLOWED_SUFFIXES = {".md", ".markdown", ".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


async def create_upload(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    uploaded_by: uuid.UUID | None,
    file: UploadFile,
    doc_type: DocType,
) -> DocumentDB:
    filename = file.filename or "upload.bin"
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(ALLOWED_SUFFIXES)}",
        )

    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file upload",
        )

    doc_id = uuid.uuid4()
    storage_key = f"{tenant_id}/{doc_type.value}/{doc_id}/{filename}"
    storage = get_object_storage()
    storage.put(storage_key, data, content_type=file.content_type)

    row = DocumentDB(
        id=doc_id,
        tenant_id=tenant_id,
        filename=filename,
        doc_type=doc_type.value,
        status=DocumentStatus.PENDING.value,
        uploaded_by=uploaded_by,
        storage_key=storage_key,
        content_type=file.content_type,
        byte_size=len(data),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    # Enqueue Celery job (eager in tests)
    index_document.delay(str(row.id))
    return row


async def list_documents(db: AsyncSession, tenant_id: uuid.UUID) -> list[DocumentDB]:
    result = await db.scalars(
        select(DocumentDB)
        .where(
            DocumentDB.tenant_id == tenant_id,
            DocumentDB.status != DocumentStatus.DELETED.value,
        )
        .order_by(DocumentDB.created_at.desc())
    )
    return list(result.all())


async def get_document(
    db: AsyncSession, tenant_id: uuid.UUID, doc_id: uuid.UUID
) -> DocumentDB | None:
    return await db.scalar(
        select(DocumentDB).where(
            DocumentDB.id == doc_id,
            DocumentDB.tenant_id == tenant_id,
            DocumentDB.status != DocumentStatus.DELETED.value,
        )
    )


async def get_document_bytes(
    db: AsyncSession, tenant_id: uuid.UUID, doc_id: uuid.UUID
) -> tuple[DocumentDB, bytes]:
    row = await get_document(db, tenant_id, doc_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    storage = get_object_storage()
    try:
        data = storage.get(row.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document file missing from storage") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to read document content") from exc
    return row, data


async def soft_delete_document(
    db: AsyncSession, tenant_id: uuid.UUID, doc_id: uuid.UUID
) -> DocumentDB:
    row = await get_document(db, tenant_id, doc_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")

    from app.infrastructure import qdrant_store

    qdrant_store.delete_document_points(tenant_id=str(tenant_id), doc_id=str(doc_id))
    storage = get_object_storage()
    try:
        storage.delete(row.storage_key)
    except Exception:
        pass

    row.status = DocumentStatus.DELETED.value
    row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)
    return row


def transient_parse(file_bytes: bytes, filename: str) -> dict:
    """Synchronous parse+chunk for tender upload — does not persist."""
    from rag_platform_chunking import chunk
    from rag_platform_parsing import parse

    parsed = parse(file_bytes, filename)
    chunks = chunk(
        parsed,
        doc_id="transient",
        tenant_id="transient",
    )
    preview_chunks = [c.text[:240] for c in chunks[:5]]
    return {
        "filename": filename,
        "text_preview": (parsed.raw_text or "")[:4000],
        "page_count": parsed.metadata.page_count,
        "table_count": len(parsed.tables),
        "chunk_count": len(chunks),
        "chunks_preview": preview_chunks,
    }
