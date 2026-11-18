"""Celery app + indexing task (parse → chunk → embed → Qdrant)."""

from __future__ import annotations

import logging
import os
import traceback
import uuid
from datetime import datetime, timezone

from celery import Celery
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker

# Ensure embedding settings are visible to ai-core before import
os.environ.setdefault(
    "EMBEDDING_MODEL_NAME",
    os.environ.get("EMBEDDING_MODEL_NAME", "fake"),
)

from app.config import settings
from app.domain.models import DocumentDB
from app.infrastructure import qdrant_store
from app.infrastructure.storage import get_object_storage

logger = logging.getLogger(__name__)

celery_app = Celery(
    "ingestion",
    broker=settings.broker_url,
    backend=settings.result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    worker_hijack_root_logger=False,
)

_sync_engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
SyncSession = sessionmaker(bind=_sync_engine, autocommit=False, autoflush=False)


def _set_status(
    session: Session,
    doc_id: uuid.UUID,
    status: str,
    *,
    error_message: str | None = None,
    chunk_count: int | None = None,
) -> None:
    values: dict = {
        "status": status,
        "updated_at": datetime.now(timezone.utc),
        # Clear any stale error from a prior failed attempt whenever a retry
        # doesn't fail again — "indexed" alongside an old TesseractNotFoundError
        # reads as broken even though the document is genuinely fine now.
        "error_message": error_message,
    }
    if chunk_count is not None:
        values["chunk_count"] = chunk_count
    session.execute(update(DocumentDB).where(DocumentDB.id == doc_id).values(**values))
    session.commit()


@celery_app.task(name="ingestion.index_document", bind=True, max_retries=2)
def index_document(self, document_id: str) -> dict:
    """
    Run the Stage 3 ai-core pipeline and persist vectors to Qdrant.
    Updates documents.status: processing → indexed | failed.
    """
    doc_uuid = uuid.UUID(document_id)
    with SyncSession() as session:
        doc = session.scalar(select(DocumentDB).where(DocumentDB.id == doc_uuid))
        if doc is None:
            logger.error("Document not found: %s", document_id)
            return {"ok": False, "error": "not_found"}

        tenant_id = str(doc.tenant_id)
        doc_id = str(doc.id)
        doc_type = doc.doc_type
        filename = doc.filename
        storage_key = doc.storage_key

        _set_status(session, doc_uuid, "processing")

        try:
            storage = get_object_storage()
            file_bytes = storage.get(storage_key)
            if not file_bytes:
                raise ValueError("Uploaded file is empty or unreadable")

            # Corrupt / non-parseable inputs should fail loudly
            from rag_platform_chunking import chunk
            from rag_platform_embedding import embed_texts
            from rag_platform_parsing import parse

            parsed = parse(file_bytes, filename)
            if not (parsed.raw_text or "").strip() and not parsed.tables:
                raise ValueError("Parse produced no usable text or tables")

            chunks = chunk(parsed, doc_id=doc_id, tenant_id=tenant_id)
            if not chunks:
                raise ValueError("Chunking produced zero chunks")

            vectors = embed_texts([c.text for c in chunks])
            qdrant_store.upsert_chunks(
                tenant_id=tenant_id,
                doc_id=doc_id,
                doc_type=doc_type,
                texts=[c.text for c in chunks],
                vectors=vectors,
                sections=[c.section for c in chunks],
                pages=[c.page for c in chunks],
            )
            _set_status(session, doc_uuid, "indexed", chunk_count=len(chunks))
            logger.info(
                "Indexed document %s tenant=%s chunks=%s",
                doc_id,
                tenant_id,
                len(chunks),
            )
            return {"ok": True, "document_id": doc_id, "chunks": len(chunks)}
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            logger.error(
                "Indexing failed for %s: %s\n%s",
                document_id,
                err,
                traceback.format_exc(),
            )
            _set_status(session, doc_uuid, "failed", error_message=err[:2000])
            return {"ok": False, "document_id": document_id, "error": err}
