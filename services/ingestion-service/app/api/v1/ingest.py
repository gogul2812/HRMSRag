import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import ingestion_service
from app.infrastructure.database import get_db_session
from rag_platform_auth_middleware import require_role
from rag_platform_observability import get_logger
from rag_platform_schemas.auth import JWTClaims, UserRole
from rag_platform_schemas.documents import (
    DocType,
    Document,
    DocumentUploadResponse,
    TransientParseResponse,
)


class DocumentContentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str | None = None
    text: str | None = None
    is_text: bool = False

router = APIRouter()
logger = get_logger(__name__)

AdminClaims = Annotated[JWTClaims, Depends(require_role(UserRole.ADMIN))]
# Transient parse is used by User Portal — allow end_user or admin
AnyUserClaims = Annotated[
    JWTClaims, Depends(require_role(UserRole.END_USER))
]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def _tenant_uuid(claims: JWTClaims) -> uuid.UUID:
    return uuid.UUID(str(claims.tenant_id))


def _user_uuid(claims: JWTClaims) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(claims.sub))
    except ValueError:
        return None


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document for async indexing",
)
async def upload_document(
    claims: AdminClaims,
    db: DbSession,
    file: UploadFile = File(...),
    doc_type: DocType = Form(DocType.PROJECT),
) -> DocumentUploadResponse:
    tenant_id = _tenant_uuid(claims)
    row = await ingestion_service.create_upload(
        db,
        tenant_id=tenant_id,
        uploaded_by=_user_uuid(claims),
        file=file,
        doc_type=doc_type,
    )
    logger.info(
        "document_upload_accepted",
        tenant_id=str(tenant_id),
        document_id=str(row.id),
        filename=row.filename,
        doc_type=row.doc_type,
    )
    return DocumentUploadResponse(document=row)


@router.get(
    "/documents",
    response_model=list[Document],
    summary="List documents for the caller's tenant",
)
async def list_documents(claims: AdminClaims, db: DbSession) -> list[Document]:
    tenant_id = _tenant_uuid(claims)
    rows = await ingestion_service.list_documents(db, tenant_id)
    return rows


@router.get(
    "/documents/{doc_id}",
    response_model=Document,
    summary="Get one document (status/metadata)",
)
async def get_document(
    doc_id: uuid.UUID, claims: AdminClaims, db: DbSession
) -> Document:
    row = await ingestion_service.get_document(db, _tenant_uuid(claims), doc_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return row


@router.get(
    "/documents/{doc_id}/content",
    response_model=DocumentContentResponse,
    summary="View document content (text/markdown) as JSON",
)
async def get_document_content(
    doc_id: uuid.UUID, claims: AdminClaims, db: DbSession
) -> DocumentContentResponse:
    row, data = await ingestion_service.get_document_bytes(
        db, _tenant_uuid(claims), doc_id
    )
    name = (row.filename or "").lower()
    ctype = (row.content_type or "").lower()
    is_text = (
        ctype.startswith("text/")
        or "markdown" in ctype
        or name.endswith((".md", ".txt", ".csv", ".json", ".yml", ".yaml", ".log"))
    )
    text: str | None = None
    if is_text:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
    return DocumentContentResponse(
        id=row.id,
        filename=row.filename,
        content_type=row.content_type,
        text=text,
        is_text=bool(text is not None),
    )


@router.get(
    "/documents/{doc_id}/download",
    summary="Download original document bytes",
)
async def download_document(
    doc_id: uuid.UUID, claims: AdminClaims, db: DbSession
) -> Response:
    row, data = await ingestion_service.get_document_bytes(
        db, _tenant_uuid(claims), doc_id
    )
    media = row.content_type or "application/octet-stream"
    return Response(
        content=data,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="{row.filename}"',
        },
    )


@router.delete(
    "/documents/{doc_id}",
    response_model=Document,
    summary="Soft-delete a document and its vectors",
)
async def delete_document(
    doc_id: uuid.UUID, claims: AdminClaims, db: DbSession
) -> Document:
    row = await ingestion_service.soft_delete_document(
        db, _tenant_uuid(claims), doc_id
    )
    logger.info(
        "document_deleted",
        tenant_id=str(row.tenant_id),
        document_id=str(row.id),
    )
    return row


@router.post(
    "/transient-parse",
    response_model=TransientParseResponse,
    summary="Synchronous parse+chunk (not persisted) for tender upload flow",
)
async def transient_parse(
    claims: AnyUserClaims,
    file: UploadFile = File(...),
) -> TransientParseResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    result = ingestion_service.transient_parse(data, file.filename or "upload.bin")
    logger.info(
        "transient_parse_done",
        tenant_id=str(claims.tenant_id),
        filename=result["filename"],
        chunks=result["chunk_count"],
    )
    return TransientParseResponse(**result)
